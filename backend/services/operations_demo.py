from __future__ import annotations

from datetime import UTC, datetime, timedelta

from backend.models.operations import CommonMessage
from backend.services.operations_pipeline import OperationsPipeline


def seed_operations_demo(pipeline: OperationsPipeline) -> int:
    # Once a live connector is configured, do not mix synthetic rows into the
    # operations queue. Existing demo rows remain preserved for comparison.
    if not pipeline.settings.operations_demo_mode or pipeline.settings.discord_bot_token or pipeline.settings.telegram_bot_token:
        return 0
    if pipeline.store.summary().messages_analyzed:
        return 0
    now = datetime.now(UTC)
    samples = [
        ("demo-safe-1", "Mình thích phần giải thích này, cảm ơn team!", "general"),
        ("demo-disagree-1", "Mình không đồng ý, bạn check lại nguồn giúp nhé.", "general"),
        ("demo-teasing-1", "Game này hơi khó đó haha, nhưng vui phết 😂", "gaming"),
        ("demo-harass-1", "Mày vô dụng thế thì nghỉ nhóm đi.", "general"),
        ("demo-threat-1", "Ra ngoài gặp tao là biết, tao sẽ tìm ra mày.", "general"),
        ("demo-spam-1", "Click link nhận tiền miễn phí ngay, chỉ còn 5 phút!", "general"),
    ]
    for index, (message_id, text, channel) in enumerate(samples):
        message = CommonMessage(message_id=message_id, platform="demo", community_id="demo-community", channel_id=channel, thread_key=f"demo-thread-{index // 2}", author_id=f"demo-user-{index}", text=text, timestamp=now + timedelta(seconds=index))
        pipeline.analyze(message)
    return len(samples)
