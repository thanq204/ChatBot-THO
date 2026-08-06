"""LLM-assisted semantic extraction for uploaded community documents."""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, Field

from src.config import Settings, get_settings


class ExtractedDocument(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1, max_length=10000)
    tags: list[str] = Field(default_factory=list, max_length=20)
    dataset: str = Field(default="general", min_length=1, max_length=80)
    kind: Literal["knowledge", "policy"] = "knowledge"
    category: str = Field(default="other", max_length=50)
    action: Literal["allow", "warn", "hide", "hold_for_review"] = "hold_for_review"
    trigger_terms: list[str] = Field(default_factory=list, max_length=30)


class ExtractionBatch(BaseModel):
    items: list[ExtractedDocument] = Field(default_factory=list, max_length=50)


class SemanticExtractionError(RuntimeError):
    pass


class SemanticDocumentExtractor:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    @property
    def available(self) -> bool:
        return self.settings.knowledge_extraction_enabled and bool(self.settings.openai_api_key)

    def extract(self, rows: list[dict[str, object]]) -> list[dict[str, object]]:
        if not self.available:
            raise SemanticExtractionError("semantic extraction is disabled or OPENAI_API_KEY is missing")
        if not rows:
            return []
        if len(rows) > 50:
            raise SemanticExtractionError("semantic extraction limit is 50 records per import")
        compact_rows = []
        for index, row in enumerate(rows, 1):
            compact_rows.append({
                "index": index,
                "document_id": row.get("document_id") or row.get("id"),
                "policy_id": row.get("policy_id") or row.get("policyId"),
                "title": row.get("title") or row.get("name") or row.get("tieu_de"),
                "content": row.get("body") or row.get("content") or row.get("text") or row.get("description") or row.get("noi_dung"),
                "metadata": {key: row[key] for key in ("tags", "tag", "dataset", "collection", "namespace", "type", "kind", "category", "action", "decision", "trigger_terms", "terms", "keywords") if key in row},
            })
        prompt = (
            "You are a document ingestion agent for a community operations assistant. "
            "Extract each input row into a clean canonical knowledge or moderation policy record. "
            "Keep the factual meaning; do not invent rules, dates, names, or numbers. "
            "Choose dataset names such as community_rules, channel_policy, events, league_of_legends, or general. "
            "Use kind=policy only when the text actually defines a rule or moderation action. "
            "For ordinary reference information use kind=knowledge and action=hold_for_review. "
            "Preserve explicit IDs and explicit metadata from the input whenever present. "
            "Return exactly one output item per input row, in the same order.\n\n"
            f"INPUT ROWS:\n{json.dumps(compact_rows, ensure_ascii=False, default=str)}"
        )
        try:
            from langchain_openai import ChatOpenAI

            llm = ChatOpenAI(
                model=self.settings.knowledge_extraction_model,
                api_key=self.settings.openai_api_key,
                temperature=self.settings.knowledge_extraction_temperature,
                max_tokens=6000,
            )
            try:
                structured = llm.with_structured_output(ExtractionBatch, method="json_schema")
            except TypeError:
                structured = llm.with_structured_output(ExtractionBatch)
            result = structured.invoke(prompt)
            if isinstance(result, dict):
                result = ExtractionBatch.model_validate(result)
            if not isinstance(result, ExtractionBatch) or len(result.items) != len(compact_rows):
                raise ValueError("LLM returned a different number of records")
            output: list[dict[str, object]] = []
            for original, extracted in zip(rows, result.items):
                item = extracted.model_dump()
                for key in ("document_id", "policy_id"):
                    explicit = original.get(key) or original.get("id" if key == "document_id" else "policyId")
                    if explicit:
                        item[key] = explicit
                for key in ("dataset", "collection", "namespace", "tags", "tag", "category", "action", "decision", "trigger_terms", "terms", "keywords", "type", "kind"):
                    if original.get(key) is not None:
                        target_key = {"collection": "dataset", "namespace": "dataset", "tag": "tags", "decision": "action", "terms": "trigger_terms", "keywords": "trigger_terms", "type": "kind"}.get(key, key)
                        item[target_key] = original[key]
                output.append(item)
            return output
        except Exception as exc:
            raise SemanticExtractionError(str(exc)) from exc
