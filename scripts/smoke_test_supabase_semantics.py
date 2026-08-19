"""End-to-end FAQ semantic smoke test using synthetic, disposable records."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.models.operations import CommonMessage, MessageDecision
from backend.services.operations_store import OperationsStore


PREFIX = "codex-semantic-smoke-20260819"


def allowed() -> MessageDecision:
    return MessageDecision(
        decision="allow",
        category="safe",
        severity="low",
        risk_score=0,
        confidence=1,
        explanation="synthetic smoke test",
        model_used="test",
    )


def main() -> int:
    store = OperationsStore()
    questions = [
        "Làm sao đăng ký môn học cho học kỳ tới?",
        "Em muốn đăng ký học phần kỳ sau thì làm thế nào?",
        "Quy trình thêm môn vào lịch học kỳ mới là gì?",
    ]
    message_ids: list[str] = []
    cluster_ids: set[str] = set()
    try:
        for index, text in enumerate(questions, 1):
            message = CommonMessage(
                message_id=f"{PREFIX}-{index}",
                platform="discord",
                community_id=PREFIX,
                channel_id="test",
                author_id="synthetic-member",
                text=text,
                timestamp=datetime.now(UTC),
            )
            message_ids.append(message.message_id)
            store.save_message(message, allowed(), None)
            store.record_member_question(message)

        with store._connect() as db:
            marks = ",".join("?" for _ in message_ids)
            rows = db.execute(
                f"""SELECT DISTINCT member.cluster_id
                FROM faq_topic_members member
                JOIN operations_faq_questions question ON question.question_id=member.question_id
                WHERE question.message_id IN ({marks})""",
                message_ids,
            ).fetchall()
            cluster_ids = {str(row["cluster_id"]) for row in rows}
            counts = db.execute(
                f"""SELECT cluster.cluster_id, cluster.question_count
                FROM faq_topic_clusters cluster WHERE cluster.cluster_id IN (
                    SELECT member.cluster_id FROM faq_topic_members member
                    JOIN operations_faq_questions question ON question.question_id=member.question_id
                    WHERE question.message_id IN ({marks})
                )""",
                message_ids,
            ).fetchall()
            diagnostics = db.execute(
                f"""SELECT cluster.topic_label, member.similarity_score, member.llm_verified
                FROM faq_topic_members member
                JOIN faq_topic_clusters cluster ON cluster.cluster_id=member.cluster_id
                JOIN operations_faq_questions question ON question.question_id=member.question_id
                WHERE question.message_id IN ({marks}) ORDER BY question.created_at""",
                message_ids,
            ).fetchall()
        print("diagnostics=" + repr([(round(float(row[1]), 4), bool(row[2])) for row in diagnostics]))
        if len(cluster_ids) != 1:
            raise AssertionError(f"Expected one semantic topic, got {len(cluster_ids)}")
        if int(counts[0]["question_count"]) < 3:
            raise AssertionError("Semantic topic did not count all three questions")
        print("semantic_cluster_count=1")
        print("semantic_question_count=3")
        print("top10_endpoint_rows=" + str(len(store.list_faq_top_topics())))
        return 0
    finally:
        with store._connect() as db:
            for cluster_id in cluster_ids:
                db.execute("DELETE FROM operations_faq_suggestions WHERE suggestion_id=?", (cluster_id,))
                db.execute("DELETE FROM faq_topic_clusters WHERE cluster_id=?", (cluster_id,))
            if message_ids:
                marks = ",".join("?" for _ in message_ids)
                db.execute(f"DELETE FROM operations_faq_questions WHERE message_id IN ({marks})", message_ids)
                db.execute(f"DELETE FROM operations_messages WHERE message_id IN ({marks})", message_ids)
            db.execute(
                "DELETE FROM community_members WHERE platform='discord' AND community_id=? AND platform_user_id='synthetic-member'",
                (PREFIX,),
            )


if __name__ == "__main__":
    raise SystemExit(main())
