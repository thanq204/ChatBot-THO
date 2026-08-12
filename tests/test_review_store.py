import pytest

from backend.config import Settings
from backend.models.moderation import AdminDecisionRequest, MemberSubmission
from backend.services.moderation import ModerationEngine
from backend.services.review_store import ReviewStore


@pytest.mark.asyncio
async def test_admin_decision_removes_pending_case_and_creates_audit_log(tmp_path):
    store = ReviewStore(f"sqlite:///{tmp_path / 'reviews.db'}")
    submission = MemberSubmission(user_id="U005", channel="project", text="Làm ăn kiểu này thì nghỉ luôn đi.")
    result = await ModerationEngine(Settings(moderation_mode="mock")).moderate(submission)
    review = store.create_review(submission, result)

    assert len(store.list_pending()) == 1
    decided = store.decide(review.review_id, AdminDecisionRequest(action="warn", admin_note="Need civil tone", reviewer="Admin A"))

    assert decided.status == "reviewed"
    assert decided.admin_action == "warn"
    assert store.list_pending() == []
    audits = store.list_audit_logs()
    assert len(audits) == 1
    assert audits[0].content == submission.text
    assert audits[0].admin_action == "warn"


@pytest.mark.asyncio
async def test_review_cannot_be_decided_twice(tmp_path):
    store = ReviewStore(f"sqlite:///{tmp_path / 'reviews.db'}")
    submission = MemberSubmission(user_id="U005", text="Làm ăn kiểu này thì nghỉ luôn đi.")
    review = store.create_review(submission, await ModerationEngine(Settings(moderation_mode="mock")).moderate(submission))
    store.decide(review.review_id, AdminDecisionRequest(action="allow"))

    with pytest.raises(ValueError, match="already been decided"):
        store.decide(review.review_id, AdminDecisionRequest(action="hide"))
