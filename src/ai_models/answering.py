"""Response labels and citations for FAQ, extractive RAG and LLM-grounded RAG."""

from __future__ import annotations

import re

from .contracts import AnswerEnvelope, Citation, FlowName, GenerationMode, QuestionDecision


class AnswerComposer:
    """Build a transport-neutral answer that always cites successful RAG."""

    _LABELS = {
        GenerationMode.FAQ: "FAQ đã duyệt",
        GenerationMode.EXTRACTIVE: "RAG",
        GenerationMode.GROUNDED_LLM: "RAG + LLM",
        GenerationMode.ABSTAIN: "Không đủ nguồn",
    }

    def compose(self, answer: str, decision: QuestionDecision, *, model_used: str) -> AnswerEnvelope:
        label = self._LABELS[decision.generation.mode]
        citations: tuple[Citation, ...] = ()

        if decision.flow is FlowName.LLM_RAG and decision.generation.mode is not GenerationMode.ABSTAIN:
            if not decision.ranked_candidates:
                raise ValueError("A successful RAG answer requires at least one ranked source")
            source = decision.ranked_candidates[0].candidate
            citation = Citation(
                source_id=source.source_id,
                title=source.title,
                excerpt=self._excerpt(source.text),
                source_type=source.source_type,
                source_url=self._source_url(source.metadata),
            )
            citations = (citation,)
            if decision.generation.mode is GenerationMode.EXTRACTIVE:
                display_text = f"[{label}]\n{answer.strip()}\n\nTrích từ tài liệu: {citation.title} ({citation.source_id})"
            else:
                display_text = (
                    f"[{label}]\n{answer.strip()}\n\n"
                    f"Nguồn: {citation.title} ({citation.source_id})\n"
                    f"Trích: “{citation.excerpt}”"
                )
        elif decision.generation.mode is GenerationMode.FAQ and decision.faq_match:
            faq = decision.faq_match.faq
            citation = Citation(faq.faq_id, faq.question, faq.answer, "faq")
            citations = (citation,)
            display_text = f"[{label}]\n{answer.strip()}\n\nNguồn: FAQ {faq.faq_id} do Admin/Mod duyệt"
        else:
            display_text = f"[{label}]\n{answer.strip()}"

        return AnswerEnvelope(
            answer=answer.strip(),
            display_text=display_text,
            answer_mode=decision.generation.mode,
            model_used=model_used,
            citations=citations,
        )

    @staticmethod
    def _excerpt(text: str, limit: int = 420) -> str:
        cleaned = " ".join(text.split())
        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", cleaned) if part.strip()]
        excerpt = " ".join(sentences[:2]) if sentences else cleaned
        return excerpt[:limit].rstrip()

    @staticmethod
    def _source_url(metadata: object) -> str | None:
        if not hasattr(metadata, "get"):
            return None
        value = metadata.get("source_url")
        return str(value) if value else None
