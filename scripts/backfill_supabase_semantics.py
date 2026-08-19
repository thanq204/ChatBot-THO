"""Backfill cloud embeddings, semantic FAQ clusters, and missing RAG chunks."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.models.operations import FAQUpsertRequest, KnowledgeDocumentRequest
from backend.services.operations_store import OperationsStore, _vector_literal


def main() -> int:
    store = OperationsStore()
    counts = {"faq_embeddings": 0, "question_clusters": 0, "moderation_embeddings": 0, "knowledge_repaired": 0}

    for faq in store.list_faqs():
        with store._connect() as db:
            exists = db.execute(
                "SELECT 1 FROM operations_faq_embeddings WHERE faq_id=?", (faq.faq_id,)
            ).fetchone()
        if exists:
            continue
        store.upsert_faq(
            faq.faq_id,
            FAQUpsertRequest(
                question=faq.question,
                answer=faq.answer,
                tags=faq.tags,
                active=faq.active,
            ),
        )
        counts["faq_embeddings"] += 1

    with store._connect() as db:
        questions = db.execute(
            """SELECT q.* FROM operations_faq_questions q
            LEFT JOIN faq_topic_members m ON m.question_id=q.question_id
            WHERE m.question_id IS NULL ORDER BY q.created_at"""
        ).fetchall()
    for question in questions:
        model, vector = store._semantic_embedding(question["question"])
        with store._connect() as db:
            db.execute(
                """INSERT INTO faq_question_embeddings
                (question_id, text_hash, model, embedding, created_at)
                VALUES (?, ?, ?, ?::vector, ?)
                ON CONFLICT(question_id) DO UPDATE SET text_hash=excluded.text_hash,
                model=excluded.model, embedding=excluded.embedding""",
                (
                    question["question_id"],
                    store._embedding_hash(question["question"]),
                    model,
                    _vector_literal(vector),
                    question["created_at"],
                ),
            )
        store._cluster_member_question(
            question["question_id"],
            question["question"],
            question["normalized_question"],
            model,
            vector,
        )
        counts["question_clusters"] += 1

    with store._connect() as db:
        marks = db.execute(
            """SELECT m.* FROM operations_moderation_marks m
            LEFT JOIN operations_moderation_embeddings e ON e.mark_id=m.mark_id
            WHERE e.mark_id IS NULL"""
        ).fetchall()
    for mark in marks:
        model, vector = store._semantic_embedding(mark["text"])
        with store._connect() as db:
            db.execute(
                """INSERT INTO operations_moderation_embeddings
                (mark_id, text_hash, model, vector_json, updated_at)
                VALUES (?, ?, ?, ?::vector, ?)
                ON CONFLICT(mark_id) DO UPDATE SET text_hash=excluded.text_hash,
                model=excluded.model, vector_json=excluded.vector_json, updated_at=excluded.updated_at""",
                (
                    mark["mark_id"],
                    store._embedding_hash(mark["text"]),
                    model,
                    _vector_literal(vector),
                    mark["updated_at"],
                ),
            )
        counts["moderation_embeddings"] += 1

    with store._connect() as db:
        missing_documents = db.execute(
            """SELECT d.* FROM knowledge_documents d
            WHERE NOT EXISTS (
                SELECT 1 FROM knowledge_sections s WHERE s.document_id=d.document_id
            ) ORDER BY d.document_id"""
        ).fetchall()
    for document in missing_documents:
        tags = document["tags"] if isinstance(document["tags"], list) else []
        store.upsert_knowledge(
            document["document_id"],
            KnowledgeDocumentRequest(
                title=document["title"],
                body=document["body"],
                tags=tags,
                dataset=document["dataset"],
                active=bool(document["active"]),
            ),
            import_id=document["import_id"],
            source_file=document["source_file"],
        )
        counts["knowledge_repaired"] += 1

    print(counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
