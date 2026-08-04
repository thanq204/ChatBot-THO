"""Safe YouTube read connector and offline dataset adapter.

Public mode only reads public video/comment data. Write operations are deliberately
represented as simulated actions elsewhere until the owner completes OAuth.
"""

from __future__ import annotations

import hashlib
from html import unescape
import json
import re
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests

from src.config import Settings, get_settings
from src.models.community import ConversationMessage, ConversationThread
from src.services.community_store import CommunityStore


class YouTubeConfigurationError(ValueError):
    pass


class YouTubeConnector:
    def __init__(self, store: CommunityStore | None = None, settings: Settings | None = None, session: Any = None) -> None:
        self.settings = settings or get_settings()
        self.store = store or CommunityStore(settings=self.settings)
        self.session = session or requests.Session()

    @staticmethod
    def parse_video_id(value: str) -> str:
        value = value.strip()
        if re.fullmatch(r"[A-Za-z0-9_-]{11}", value):
            return value
        parsed = urlparse(value)
        host = parsed.netloc.lower().split(":")[0]
        if host in {"youtu.be", "www.youtu.be"}:
            candidate = parsed.path.strip("/").split("/")[0]
        elif "youtube.com" in host:
            if parsed.path == "/watch":
                candidate = parse_qs(parsed.query).get("v", [""])[0]
            else:
                parts = [part for part in parsed.path.split("/") if part]
                candidate = parts[1] if len(parts) >= 2 and parts[0] in {"shorts", "embed", "live"} else ""
        else:
            candidate = ""
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate or ""):
            raise YouTubeConfigurationError("Không nhận diện được YouTube Video ID. Hãy dán link watch/shorts/youtu.be hoặc ID 11 ký tự.")
        return candidate

    def sync_video(self, value: str, max_results: int | None = None, fetch_limit: int | None = None, persist_threads: bool = True) -> dict[str, Any]:
        started = time.perf_counter()
        video_id = self.parse_video_id(value)
        limit = max_results or self.settings.youtube_max_results_per_sync
        scan_limit = fetch_limit or limit
        if self.settings.youtube_data_mode == "imported_dataset":
            title, threads = self._load_dataset(video_id)
        else:
            title, threads = self._fetch_public(video_id, scan_limit)
        if persist_threads:
            for thread in threads[: self.settings.youtube_max_threads_per_analysis]:
                self.store.upsert_thread(thread)
        self.store.save_youtube_snapshot(video_id, title, threads)
        new_comments = sum(1 for thread in threads for message in thread.messages if not message.parent_message_id)
        new_replies = sum(1 for thread in threads for message in thread.messages if message.parent_message_id)
        return {
            "video_id": video_id,
            "video_title": title,
            "threads": threads,
            "new_comments": new_comments,
            "new_replies": new_replies,
            "total_threads": len(threads),
            "analyzed_threads": sum(1 for thread in threads if thread.analysis),
            "errors": [],
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "source_mode": self.settings.youtube_data_mode,
            "action_mode": self.settings.youtube_action_mode,
        }

    def save_snapshot(self, video_id: str, title: str, threads: list[ConversationThread]) -> Path:
        root = Path(self.settings.youtube_dataset_path)
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"{video_id}.json"
        payload = {"video_id": video_id, "title": title, "threads": [thread.model_dump(mode="json") for thread in threads]}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def _fetch_public(self, video_id: str, limit: int) -> tuple[str, list[ConversationThread]]:
        if not self.settings.youtube_allow_public_read:
            raise YouTubeConfigurationError("Public read mode đang bị tắt trong cấu hình.")
        if not self.settings.youtube_api_key:
            raise YouTubeConfigurationError("Thiếu YOUTUBE_API_KEY. Hoặc chuyển YOUTUBE_DATA_MODE=imported_dataset để demo offline.")
        video = self._get("videos", {"part": "snippet,statistics,status", "id": video_id})
        items = video.get("items") or []
        if not items:
            raise YouTubeConfigurationError("Không tìm thấy video hoặc video không cho phép truy cập public.")
        snippet = items[0].get("snippet", {})
        title = snippet.get("title") or video_id
        threads: list[ConversationThread] = []
        token = None
        while len(threads) < limit:
            params = {"part": "snippet,replies", "videoId": video_id, "maxResults": min(100, limit - len(threads))}
            if token:
                params["pageToken"] = token
            response = self._get("commentThreads", params)
            for item in response.get("items", []):
                thread = self._normalize_thread(item, video_id, title)
                total = int(item.get("snippet", {}).get("totalReplyCount", 0))
                replies = item.get("replies", {}).get("comments", [])
                if total > len(replies):
                    parent_id = thread.messages[0].message_id if thread.messages else ""
                    replies = self._fetch_missing_replies(parent_id, replies)
                thread.messages.extend(self._normalize_reply(reply, video_id) for reply in replies if reply.get("id"))
                threads.append(thread)
            token = response.get("nextPageToken")
            if not token or not response.get("items"):
                break
        return title, threads[:limit]

    def _get(self, resource: str, params: dict[str, Any]) -> dict[str, Any]:
        query = {**params, "key": self.settings.youtube_api_key}
        response = self.session.get(f"https://www.googleapis.com/youtube/v3/{resource}", params=query, timeout=20)
        if response.status_code >= 400:
            detail = "YouTube API request failed"
            try:
                detail = response.json().get("error", {}).get("message", detail)
            except (ValueError, AttributeError):
                pass
            raise YouTubeConfigurationError(f"YouTube API: {detail}")
        return response.json()

    def _fetch_missing_replies(self, parent_id: str, existing: list[dict[str, Any]]) -> list[dict[str, Any]]:
        token = None
        collected = list(existing)
        while True:
            params: dict[str, Any] = {"part": "snippet", "parentId": parent_id, "maxResults": 100}
            if token:
                params["pageToken"] = token
            data = self._get("comments", params)
            collected.extend(item for item in data.get("items", []) if item.get("id") not in {x.get("id") for x in collected})
            token = data.get("nextPageToken")
            if not token:
                return collected

    def _normalize_thread(self, item: dict[str, Any], video_id: str, title: str) -> ConversationThread:
        snippet = item.get("snippet", {})
        top = snippet.get("topLevelComment", {})
        comment = self._normalize_comment(top, video_id)
        now = datetime.now(UTC)
        return ConversationThread(
            thread_id=f"yt-{item.get('id') or comment.message_id}", platform="youtube", community_id="youtube",
            channel_id=snippet.get("channelId") or "unknown-channel", video_id=video_id, video_title=title,
            content_url=f"https://www.youtube.com/watch?v={video_id}&lc={comment.message_id}", messages=[comment],
            source_mode=self.settings.youtube_data_mode, action_mode=self.settings.youtube_action_mode,
            imported_at=now, expires_at=now + timedelta(days=self.settings.youtube_data_retention_days),
        )

    def _normalize_reply(self, item: dict[str, Any], video_id: str) -> ConversationMessage:
        return self._normalize_comment(item, video_id)

    @staticmethod
    def _normalize_comment(item: dict[str, Any], video_id: str) -> ConversationMessage:
        snippet = item.get("snippet", {})
        author = snippet.get("authorDisplayName") or "anonymous"
        author_id = "USER-" + hashlib.sha256(author.encode("utf-8")).hexdigest()[:10].upper()
        timestamp = snippet.get("publishedAt") or snippet.get("updatedAt") or datetime.now(UTC).isoformat()
        raw_text = snippet.get("textOriginal") or snippet.get("textDisplay") or ""
        plain_text = re.sub(r"<br\s*/?>", "\n", raw_text, flags=re.I)
        plain_text = re.sub(r"<[^>]+>", "", plain_text)
        plain_text = unescape(plain_text).strip()
        return ConversationMessage(
            message_id=item.get("id") or f"local-{hashlib.sha256((author + timestamp).encode()).hexdigest()[:12]}",
            parent_message_id=snippet.get("parentId"), author_id=author_id,
            text=plain_text,
            timestamp=timestamp, like_count=int(snippet.get("likeCount", 0) or 0),
            source_url=f"https://www.youtube.com/watch?v={video_id}&lc={item.get('id', '')}",
        )

    def _load_dataset(self, video_id: str) -> tuple[str, list[ConversationThread]]:
        path = Path(self.settings.youtube_dataset_path) / f"{video_id}.json"
        if not path.exists():
            path = Path(self.settings.youtube_dataset_path) / "demo.json"
        if not path.exists():
            return self._builtin_demo(video_id)
        payload = json.loads(path.read_text(encoding="utf-8"))
        title = payload.get("title") or video_id
        threads = [ConversationThread.model_validate(item) for item in payload.get("threads", [])]
        return title, threads

    @staticmethod
    def _builtin_demo(video_id: str) -> tuple[str, list[ConversationThread]]:
        now = datetime.now(UTC)
        examples = [
            ("healthy", "Mình thích phần giải thích trong video, cảm ơn team!", "Cảm ơn bạn, rất vui vì nó hữu ích."),
            ("tense", "Mình nghĩ dữ kiện này sai, bạn kiểm tra lại nhé!", "Bạn đọc không kỹ thì có."),
            ("escalating", "Đừng có nói kiểu đó, mày vô dụng!", "Im đi, tao sẽ tìm ra mày."),
        ]
        threads = []
        for index, (_, first, second) in enumerate(examples, 1):
            messages = [
                ConversationMessage(message_id=f"demo-{index}-1", author_id=f"USER-DEMO-{index}A", text=first, timestamp=now),
                ConversationMessage(message_id=f"demo-{index}-2", parent_message_id=f"demo-{index}-1", author_id=f"USER-DEMO-{index}B", text=second, timestamp=now + timedelta(minutes=1)),
            ]
            threads.append(ConversationThread(
                thread_id=f"yt-demo-{index}", platform="youtube", community_id="youtube", channel_id="demo-channel",
                video_id=video_id, video_title="Community Health Demo Video", content_url=f"https://youtu.be/{video_id}",
                messages=messages, source_mode="imported_dataset", action_mode="simulated", imported_at=now,
            ))
        return "Community Health Demo Video", threads
