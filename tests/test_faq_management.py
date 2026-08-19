from datetime import UTC, datetime

from backend.config import Settings
from backend.models.operations import CommonMessage, FAQUpsertRequest
from backend.services.operations_store import OperationsStore


def member_question(message_id: str, text: str) -> CommonMessage:
    return CommonMessage(
        message_id=message_id,
        platform="discord",
        community_id="community-1",
        channel_id="questions",
        author_id="member-1",
        text=text,
        timestamp=datetime.now(UTC),
    )


def test_approved_topic_leaves_top_10_and_enters_faq_history(tmp_path) -> None:
    store = OperationsStore(Settings(database_url=f"sqlite:///{tmp_path / 'faq.db'}"))
    question = "Làm sao để đăng ký môn học?"

    for index in range(3):
        store.record_unanswered_question(member_question(f"question-{index}", question))

    topic = store.list_faq_top_topics()[0]
    faq_id = "FAQ-COURSE-REGISTRATION"
    store.upsert_faq(
        faq_id,
        FAQUpsertRequest(
            question=topic.representative_question,
            answer="Đăng ký trên hệ thống đào tạo trong thời gian nhà trường thông báo.",
            tags=["course", "registration"],
        ),
    )
    store.set_faq_suggestion_status(topic.cluster_id, "approved")
    store.link_faq_topic(topic.cluster_id, faq_id)

    assert store.list_faq_top_topics() == []
    history = store.list_faqs()
    created = next(item for item in history if item.faq_id == faq_id)
    assert created.active is True


def test_faq_history_edit_updates_same_record_and_can_pause_it(tmp_path) -> None:
    store = OperationsStore(Settings(database_url=f"sqlite:///{tmp_path / 'faq.db'}"))
    faq_id = "FAQ-STUDY-SCHEDULE"
    store.upsert_faq(
        faq_id,
        FAQUpsertRequest(question="Lịch học ở đâu?", answer="Xem trong kênh lịch học."),
    )

    store.upsert_faq(
        faq_id,
        FAQUpsertRequest(
            question="Tôi xem lịch học ở đâu?",
            answer="Xem lịch mới nhất trong kênh #lịch-học.",
            tags=["schedule"],
            active=False,
        ),
    )

    history = store.list_faqs()
    updated = next(item for item in history if item.faq_id == faq_id)
    assert updated.question == "Tôi xem lịch học ở đâu?"
    assert updated.answer == "Xem lịch mới nhất trong kênh #lịch-học."
    assert updated.active is False
    assert store.find_faq("Tôi xem lịch học ở đâu?") is None
