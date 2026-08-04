"""Small deterministic demo set used by the local dashboard."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.models.community import ConversationMessage, ConversationThread
from src.services.community_store import CommunityStore
from src.services.conversation_analysis import ConversationAnalysisService


def seed_demo(store: CommunityStore, service: ConversationAnalysisService) -> None:
    now = datetime.now(UTC)
    cases = [
        ("DEMO-HEALTHY", "healthy", ["Mình thích phần giải thích trong video, cảm ơn team!", "Cảm ơn bạn, rất vui vì nó hữu ích."]),
        ("DEMO-DISAGREEMENT", "disagreement", ["Mình nghĩ dữ kiện này sai, bạn kiểm tra lại nhé.", "Bạn có nguồn nào để đối chiếu không?"]),
        ("DEMO-TENSE", "tense", ["Mình nghĩ dữ kiện này sai!", "Bạn đọc không kỹ thì có!"]),
        ("DEMO-ESCALATING", "escalating", ["Đừng có nói kiểu đó, mày vô dụng!", "Im đi, tao sẽ tìm ra mày."]),
        ("DEMO-AMBIGUOUS", "ambiguous", ["Cứ thử đăng địa chỉ lên xem sao.", "Ý bạn là muốn kiểm chứng hay đang đe doạ vậy?"]),
        ("DEMO-RESOLVING", "resolving", ["Mình không đồng ý với kết luận này.", "Xin lỗi, mình diễn đạt hơi gắt. Mình cùng kiểm tra lại nguồn nhé."]),
    ]
    existing = {thread.thread_id for thread in store.list_threads()}
    for thread_id, _, texts in cases:
        if thread_id in existing:
            continue
        messages = [
            ConversationMessage(message_id=f"{thread_id}-1", author_id="USER-A", text=texts[0], timestamp=now),
            ConversationMessage(message_id=f"{thread_id}-2", parent_message_id=f"{thread_id}-1", author_id="USER-B", text=texts[1], timestamp=now + timedelta(minutes=1)),
        ]
        thread = ConversationThread(
            thread_id=thread_id, platform="youtube", community_id="demo-community", channel_id="demo-channel",
            video_id="demo-video", video_title="Community Health Demo", content_url="https://youtu.be/demo-video",
            messages=messages, source_mode="imported_dataset", action_mode="simulated", imported_at=now,
        )
        analysis = service.analyze(thread)
        store.upsert_thread(thread.model_copy(update={"analysis": analysis, "last_analyzed_at": now}))
        store.save_intervention(thread_id, service.recommend(thread, analysis))
