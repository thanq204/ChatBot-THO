"""Composition root for the model-only community AI pipeline."""

from __future__ import annotations

from collections.abc import Iterable

from .answering import AnswerComposer
from .contracts import (
    AnswerEnvelope,
    FAQEntry,
    FlowName,
    GenerationDecision,
    GenerationMode,
    ModerationMemoryMatch,
    QuestionDecision,
    RetrievalCandidate,
    RoutingPlan,
    Vector,
)
from .faq import SemanticFAQMatcher
from .moderation_memory import ModerationMemoryIndex
from .retrieval import GenerationRouter, RelevanceGate, SemanticReranker
from .routing import InputRouter


class CommunityAIPipeline:
    """Pure decision logic; persistence, network and UI stay in adapters."""

    def __init__(
        self,
        *,
        input_router: InputRouter | None = None,
        faq_matcher: SemanticFAQMatcher | None = None,
        reranker: SemanticReranker | None = None,
        relevance_gate: RelevanceGate | None = None,
        generation_router: GenerationRouter | None = None,
        moderation_memory: ModerationMemoryIndex | None = None,
        answer_composer: AnswerComposer | None = None,
    ) -> None:
        self.input_router = input_router or InputRouter()
        self.faq_matcher = faq_matcher or SemanticFAQMatcher()
        self.reranker = reranker or SemanticReranker()
        self.relevance_gate = relevance_gate or RelevanceGate()
        self.generation_router = generation_router or GenerationRouter()
        self.moderation_memory = moderation_memory or ModerationMemoryIndex()
        self.answer_composer = answer_composer or AnswerComposer()

    def route_input(
        self,
        text: str,
        *,
        bot_mentioned: bool,
        private_chat: bool = False,
        bot_username: str | None = None,
    ) -> RoutingPlan:
        return self.input_router.plan(
            text,
            bot_mentioned=bot_mentioned,
            private_chat=private_chat,
            bot_username=bot_username,
        )

    def check_moderation_memory(
        self,
        text: str,
        embedding: Vector,
        *,
        category: str | None = None,
    ) -> ModerationMemoryMatch:
        return self.moderation_memory.match(text, embedding, category=category)

    def decide_question(
        self,
        question: str,
        query_embedding: Vector,
        faqs: Iterable[FAQEntry],
        candidates: Iterable[RetrievalCandidate],
        *,
        llm_enabled: bool,
    ) -> QuestionDecision:
        faq_match = self.faq_matcher.match(question, query_embedding, faqs)
        if faq_match:
            return QuestionDecision(
                flow=FlowName.FAQ,
                faq_match=faq_match,
                generation=GenerationDecision(GenerationMode.FAQ, False, "approved-semantic-faq-match"),
            )

        ranked = self.reranker.rank(question, candidates)
        relevance = self.relevance_gate.evaluate(ranked)
        generation = self.generation_router.decide(relevance, ranked, llm_enabled=llm_enabled)
        return QuestionDecision(
            flow=FlowName.LLM_RAG,
            generation=generation,
            ranked_candidates=ranked,
            relevance=relevance,
            should_record_unanswered=generation.mode is GenerationMode.ABSTAIN,
        )

    def compose_answer(
        self,
        answer: str,
        decision: QuestionDecision,
        *,
        model_used: str,
    ) -> AnswerEnvelope:
        return self.answer_composer.compose(answer, decision, model_used=model_used)
