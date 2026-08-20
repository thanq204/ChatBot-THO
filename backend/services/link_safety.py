"""Deterministic URL normalization and transparent spam/scam signals."""

from __future__ import annotations

import hashlib
import ipaddress
import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_URL_PATTERN = re.compile(r"(?i)\b(?:https?://|hxxps?://|www\.)[^\s<>\"]+")
_TRAILING_PUNCTUATION = ".,;:!?)]}'\""
_TRACKING_PARAMETERS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "ref_src",
}
_SHORTENERS = {
    "bit.ly",
    "cutt.ly",
    "goo.gl",
    "is.gd",
    "ow.ly",
    "rebrand.ly",
    "shorturl.at",
    "tiny.cc",
    "tinyurl.com",
    "t.ly",
}
_SUSPICIOUS_TLDS = {"click", "country", "gq", "kim", "loan", "men", "mom", "rest", "top", "work", "zip"}


@dataclass(frozen=True)
class SpamAssessment:
    risk_score: float
    label: str
    evidence: tuple[str, ...]
    urls: tuple[str, ...]

    @property
    def suspicious(self) -> bool:
        return self.risk_score >= 0.55


def _fold(value: str) -> str:
    value = value.lower().replace("đ", "d")
    value = unicodedata.normalize("NFD", value)
    return "".join(char for char in value if unicodedata.category(char) != "Mn")


def extract_urls(text: str) -> list[str]:
    """Return normalized, de-duplicated URLs without making hxxp text clickable."""
    urls: list[str] = []
    for match in _URL_PATTERN.finditer(text):
        raw = match.group(0).rstrip(_TRAILING_PUNCTUATION)
        normalized = canonicalize_url(raw)
        if normalized and normalized not in urls:
            urls.append(normalized)
    return urls


def canonicalize_url(value: str) -> str:
    value = value.strip().rstrip(_TRAILING_PUNCTUATION)
    value = re.sub(r"(?i)^hxxp", "http", value)
    if value.lower().startswith("www."):
        value = "https://" + value
    try:
        parts = urlsplit(value)
        host = (parts.hostname or "").rstrip(".").lower()
        if not host:
            return ""
        try:
            host = host.encode("idna").decode("ascii")
        except UnicodeError:
            return ""
        port = parts.port
        netloc = host
        if port and not ((parts.scheme.lower() == "http" and port == 80) or (parts.scheme.lower() == "https" and port == 443)):
            netloc = f"{host}:{port}"
        path = re.sub(r"/{2,}", "/", parts.path or "/")
        if path != "/":
            path = path.rstrip("/")
        query = [
            (key, item)
            for key, item in parse_qsl(parts.query, keep_blank_values=True)
            if not key.lower().startswith("utm_") and key.lower() not in _TRACKING_PARAMETERS
        ]
        return urlunsplit((parts.scheme.lower() or "https", netloc, path, urlencode(sorted(query)), ""))
    except (TypeError, ValueError):
        return ""


def url_hash(url: str) -> str:
    return hashlib.sha256(canonicalize_url(url).encode("utf-8")).hexdigest()


def assess_spam(
    text: str,
    *,
    recent_texts: list[str] | tuple[str, ...] = (),
    blocked_urls: list[str] | tuple[str, ...] = (),
    repeat_threshold: int = 3,
) -> SpamAssessment:
    """Score explainable spam/scam signals; an ordinary single URL stays safe."""
    folded = _fold(text)
    urls = extract_urls(text)
    blocked = {canonicalize_url(url) for url in blocked_urls}
    evidence: list[str] = []
    scores: list[tuple[float, str]] = []

    matched_blocked = [url for url in urls if url in blocked]
    if matched_blocked:
        evidence.append(f"link đã bị cộng đồng chặn: {matched_blocked[0]}")
        scores.append((1.0, "blocked_link"))

    if len(urls) >= 3:
        evidence.append(f"chứa {len(urls)} đường link trong một tin nhắn")
        scores.append((0.88, "link_burst"))

    mention_count = len(re.findall(r"<@!?\d+>|@everyone|@here", text, re.I))
    if mention_count >= 5:
        evidence.append(f"tag hàng loạt {mention_count} người/nhóm")
        scores.append((0.84, "mention_burst"))

    credential = bool(re.search(r"\b(otp|mat khau|password|dang nhap|xac minh tai khoan|seed phrase|private key|ma xac nhan)\b", folded))
    money = bool(re.search(r"\b(nhan tien|trung thuong|chuyen khoan|hoan tien|qua tang|mien phi|loi nhuan|dau tu|vi dien tu)\b", folded))
    urgency = bool(re.search(r"\b(ngay bay gio|lap tuc|chi con|het han|khan cap|trong \d+ phut)\b", folded))
    call_to_action = bool(re.search(r"\b(bam vao|click|truy cap|mo link|quet ma|dien thong tin|gui ma)\b", folded))

    suspicious_host = False
    for url in urls:
        parts = urlsplit(url)
        host = parts.hostname or ""
        reasons: list[str] = []
        try:
            ipaddress.ip_address(host)
            reasons.append("domain là địa chỉ IP")
        except ValueError:
            pass
        if host.startswith("xn--") or ".xn--" in host:
            reasons.append("domain dùng punycode dễ giả mạo")
        if host in _SHORTENERS:
            reasons.append("dịch vụ rút gọn che đích đến")
        if host.count(".") >= 4:
            reasons.append("quá nhiều subdomain")
        if host.rsplit(".", 1)[-1] in _SUSPICIOUS_TLDS:
            reasons.append("đuôi domain rủi ro cao")
        if reasons:
            suspicious_host = True
            evidence.append(f"{host}: {', '.join(reasons)}")

    if urls and credential and (call_to_action or urgency):
        evidence.append("yêu cầu đăng nhập/OTP kèm lời thúc giục qua link")
        scores.append((0.96, "credential_phishing"))
    elif urls and money and (call_to_action or urgency):
        evidence.append("hứa hẹn tiền/quà kèm lời thúc giục qua link")
        scores.append((0.93, "financial_scam"))
    elif urls and suspicious_host and (credential or money or call_to_action):
        evidence.append("domain đáng ngờ đi kèm lời kêu gọi hành động")
        scores.append((0.90, "suspicious_link"))
    elif suspicious_host:
        scores.append((0.72, "suspicious_domain"))

    normalized = re.sub(r"\s+", " ", folded).strip()
    repeat_count = 1 + sum(re.sub(r"\s+", " ", _fold(item)).strip() == normalized for item in recent_texts)
    if normalized and repeat_count >= repeat_threshold:
        evidence.append(f"lặp cùng nội dung {repeat_count} lần trong cửa sổ gần")
        scores.append((0.91, "repeated_message"))

    if len(text) >= 12 and len(set(folded.split())) <= 2:
        evidence.append("lặp từ bất thường trong cùng tin nhắn")
        scores.append((0.64, "word_repetition"))

    if not scores:
        return SpamAssessment(0.0, "no_spam_signal", (), tuple(urls))
    risk, label = max(scores, key=lambda item: item[0])
    return SpamAssessment(risk, label, tuple(dict.fromkeys(evidence))[:6], tuple(urls))
