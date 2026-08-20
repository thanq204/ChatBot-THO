"""Backfill cloud embeddings, semantic FAQ clusters, and missing RAG chunks."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.models.operations import FAQUpsertRequest, KnowledgeDocumentRequest
from backend.services.operations_store import OperationsStore, _vector_literal
from backend.services.question_intent import is_reusable_faq_question, normalize_intent_text


def _legacy_main() -> int:
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


def _json_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
            return [str(item) for item in decoded] if isinstance(decoded, list) else []
        except json.JSONDecodeError:
            return []
    return []


def _obvious_benign_game_case(text: str) -> bool:
    normalized = normalize_intent_text(text)
    game_context = re.search(
        r"(?:lien quan|lien minh|vao rung|di rung|jungl|rank|combat)",
        normalized,
    )
    role_action = re.search(
        r"(?:giet|danh|chem).{0,30}(?:di rung|tuong|team|dich)",
        normalized,
    )
    explicit_threat = re.search(
        r"(?:tao|bo|me).{0,20}(?:se|gio).{0,20}(?:may|m\b|ban)",
        normalized,
    )
    return bool(game_context and role_action and not explicit_threat)


def _upsert_vector(
    store: OperationsStore,
    table: str,
    id_column: str,
    vector_column: str,
    row_id: str,
    text: str,
    model: str,
    vector: list[float],
    updated_at,
) -> None:
    with store._connect() as db:
        db.execute(
            f"""INSERT INTO {table}
            ({id_column}, text_hash, model, {vector_column}, dimensions, embedding_version, updated_at)
            VALUES (?, ?, ?, ?::vector, ?, 1, ?)
            ON CONFLICT({id_column}) DO UPDATE SET text_hash=excluded.text_hash,
            model=excluded.model, {vector_column}=excluded.{vector_column},
            dimensions=excluded.dimensions, embedding_version=excluded.embedding_version,
            updated_at=excluded.updated_at""",
            (
                row_id,
                store._embedding_hash(text),
                model,
                _vector_literal(vector),
                len(vector),
                updated_at,
            ),
        )


def _repair_question_analytics(store: OperationsStore, apply: bool, counts: dict[str, int]) -> None:
    with store._connect() as db:
        questions = db.execute(
            """SELECT q.*, m.cluster_id FROM operations_faq_questions q
            LEFT JOIN faq_topic_members m ON m.question_id=q.question_id
            ORDER BY q.created_at"""
        ).fetchall()

    eligible_orphans = []
    excluded_question_ids: set[str] = set()
    for question in questions:
        text = str(question["question"])
        if not is_reusable_faq_question(text):
            counts["faq_questions_excluded"] += 1
            excluded_question_ids.add(str(question["question_id"]))
            if apply:
                with store._connect() as db:
                    db.execute(
                        "UPDATE operations_faq_questions SET outcome_stage='excluded_non_faq' WHERE question_id=?",
                        (question["question_id"],),
                    )
            continue
        if question["cluster_id"]:
            continue
        counts["faq_questions_clustered"] += 1
        eligible_orphans.append(question)

    with store._connect() as db:
        cluster_rows = db.execute(
            """SELECT c.cluster_id, m.question_id
            FROM faq_topic_clusters c
            LEFT JOIN faq_topic_members m ON m.cluster_id=c.cluster_id
            WHERE c.status='open'"""
        ).fetchall()
    cluster_members: dict[str, list[str]] = {}
    for row in cluster_rows:
        cluster_id = str(row["cluster_id"])
        cluster_members.setdefault(cluster_id, [])
        if row["question_id"]:
            cluster_members[cluster_id].append(str(row["question_id"]))
    empty_clusters = [
        cluster_id
        for cluster_id, members in cluster_members.items()
        if not members or all(question_id in excluded_question_ids for question_id in members)
    ]
    counts["faq_clusters_dismissed"] += len(empty_clusters)
    if apply:
        for cluster_id in empty_clusters:
            with store._connect() as db:
                db.execute(
                    "UPDATE faq_topic_clusters SET status='dismissed', question_count=0, updated_at=NOW() WHERE cluster_id=?",
                    (cluster_id,),
                )
                db.execute(
                    "UPDATE operations_faq_suggestions SET status='dismissed', question_count=0, updated_at=NOW() WHERE suggestion_id=?",
                    (cluster_id,),
                )

    if not apply:
        return
    for question in eligible_orphans:
        text = str(question["question"])
        model, vector = store._semantic_embedding(text)
        with store._connect() as db:
            db.execute(
                """INSERT INTO faq_question_embeddings
                (question_id, text_hash, model, embedding, dimensions, embedding_version, created_at)
                VALUES (?, ?, ?, ?::vector, ?, 1, ?)
                ON CONFLICT(question_id) DO UPDATE SET text_hash=excluded.text_hash,
                model=excluded.model, embedding=excluded.embedding,
                dimensions=excluded.dimensions, embedding_version=excluded.embedding_version""",
                (
                    question["question_id"],
                    store._embedding_hash(text),
                    model,
                    _vector_literal(vector),
                    len(vector),
                    question["created_at"],
                ),
            )
        store._cluster_member_question(
            str(question["question_id"]),
            text,
            str(question["normalized_question"]),
            model,
            vector,
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Write changes; default is dry-run.")
    args = parser.parse_args()
    store = OperationsStore()
    if not store.is_postgres:
        print("Refusing to backfill: runtime is not connected to PostgreSQL/Supabase.")
        return 2

    counts = {
        "faq_embeddings": 0,
        "faq_questions_excluded": 0,
        "faq_questions_clustered": 0,
        "faq_clusters_dismissed": 0,
        "moderation_embeddings": 0,
        "moderation_marks_quarantined": 0,
        "policy_embeddings": 0,
        "knowledge_reindexed": 0,
    }
    target_model = store.settings.openai_embedding_model
    dimensions = store.settings.openai_embedding_dimensions

    with store._connect() as db:
        faqs = db.execute(
            """SELECT f.* FROM operations_faqs f
            LEFT JOIN operations_faq_embeddings e ON e.faq_id=f.faq_id
            WHERE e.faq_id IS NULL OR e.model<>? OR e.dimensions<>?""",
            (target_model, dimensions),
        ).fetchall()
    counts["faq_embeddings"] = len(faqs)
    if args.apply:
        for faq in faqs:
            store.upsert_faq(
                str(faq["faq_id"]),
                FAQUpsertRequest(
                    question=str(faq["question"]),
                    answer=str(faq["answer"]),
                    tags=_json_list(faq["tags_json"]),
                    active=bool(faq["active"]),
                ),
            )

    _repair_question_analytics(store, args.apply, counts)

    with store._connect() as db:
        marks = db.execute(
            """SELECT m.*, e.model embedding_model, e.dimensions embedding_dimensions
            FROM operations_moderation_marks m
            LEFT JOIN operations_moderation_embeddings e ON e.mark_id=m.mark_id
            WHERE m.active=TRUE"""
        ).fetchall()
    for mark in marks:
        if _obvious_benign_game_case(str(mark["text"])):
            counts["moderation_marks_quarantined"] += 1
            if args.apply:
                with store._connect() as db:
                    db.execute("UPDATE operations_moderation_marks SET active=FALSE, updated_at=NOW() WHERE mark_id=?", (mark["mark_id"],))
            continue
        if mark["embedding_model"] == target_model and int(mark["embedding_dimensions"] or 0) == dimensions:
            continue
        counts["moderation_embeddings"] += 1
        if args.apply:
            model, vector = store._moderation_embedding(str(mark["text"]))
            _upsert_vector(store, "operations_moderation_embeddings", "mark_id", "vector_json", str(mark["mark_id"]), str(mark["text"]), model, vector, mark["updated_at"])

    with store._connect() as db:
        policies = db.execute(
            """SELECT p.* FROM operations_policies p
            LEFT JOIN operations_policy_embeddings e ON e.policy_id=p.policy_id
            WHERE p.active=TRUE AND (e.policy_id IS NULL OR e.model<>? OR e.dimensions<>?)""",
            (target_model, dimensions),
        ).fetchall()
    counts["policy_embeddings"] = len(policies)
    if args.apply:
        for policy in policies:
            policy_text = "\n".join([str(policy["name"]), str(policy["description"]), str(policy["category"]), *_json_list(policy["trigger_terms_json"])])
            model, vector = store._semantic_embedding(policy_text)
            _upsert_vector(store, "operations_policy_embeddings", "policy_id", "embedding", str(policy["policy_id"]), policy_text, model, vector, policy["updated_at"])

    with store._connect() as db:
        documents = db.execute(
            """SELECT DISTINCT d.* FROM knowledge_documents d
            LEFT JOIN knowledge_sections s ON s.document_id=d.document_id
            LEFT JOIN knowledge_section_embeddings e ON e.chunk_id=s.chunk_id
            WHERE s.chunk_id IS NULL OR e.chunk_id IS NULL OR e.model<>? OR e.dimensions<>?
            ORDER BY d.document_id""",
            (target_model, dimensions),
        ).fetchall()
    counts["knowledge_reindexed"] = len(documents)
    if args.apply:
        for document in documents:
            store.upsert_knowledge(
                str(document["document_id"]),
                KnowledgeDocumentRequest(
                    title=str(document["title"]),
                    body=str(document["body"]),
                    tags=_json_list(document["tags"]),
                    dataset=str(document["dataset"]),
                    active=bool(document["active"]),
                ),
                import_id=document.get("import_id"),
                source_file=document.get("source_file"),
            )

    print(json.dumps({"mode": "applied" if args.apply else "dry-run", **counts}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
