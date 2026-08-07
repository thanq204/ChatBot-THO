"""Multi-agent LangGraph workflow for message moderation.

Each specialist has one narrow responsibility and writes a typed result into
the shared graph state. A deterministic safety gate remains outside the LLM
decision so high-risk content cannot be auto-approved by a single model.
"""

from __future__ import annotations

from typing import TypedDict, cast

from langgraph.graph import END, StateGraph

from backend.models.moderation import (
    ContextAgentOutput,
    GeminiModerationOutput,
    MemberSubmission,
    PolicyAgentOutput,
    RiskAgentOutput,
)
from backend.services.gemini_moderation import GeminiModerationService


class ModerationGraphState(TypedDict, total=False):
    submission: MemberSubmission
    context: ContextAgentOutput
    policy: PolicyAgentOutput
    risk: RiskAgentOutput
    decision: GeminiModerationOutput
    safety_override: bool
    model_used: str
    trace: list[str]


class ModerationAgentGraph:
    """Compile and run the specialist-agent moderation graph."""

    def __init__(self, service: GeminiModerationService) -> None:
        self.service = service
        self.graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(ModerationGraphState)
        graph.add_node("context_agent", self.context_agent)
        graph.add_node("policy_agent", self.policy_agent)
        graph.add_node("risk_agent", self.risk_agent)
        graph.add_node("safety_gate", self.safety_gate)
        graph.add_node("decision_agent", self.decision_agent)
        graph.add_node("guardrail", self.guardrail)

        graph.set_entry_point("context_agent")
        graph.add_edge("context_agent", "policy_agent")
        graph.add_edge("policy_agent", "risk_agent")
        graph.add_conditional_edges(
            "risk_agent",
            self.route_after_risk,
            {"safety_gate": "safety_gate", "decision_agent": "decision_agent"},
        )
        graph.add_edge("safety_gate", "decision_agent")
        graph.add_edge("decision_agent", "guardrail")
        graph.add_edge("guardrail", END)
        return graph.compile()

    @staticmethod
    def _append_trace(state: ModerationGraphState, label: str) -> list[str]:
        return [*state.get("trace", []), label]

    def context_agent(self, state: ModerationGraphState) -> dict[str, object]:
        submission = state["submission"]
        result = self.service.run_context_agent(submission)
        return {
            "context": cast(ContextAgentOutput, result.output),
            "trace": self._append_trace(state, "Context Agent"),
        }

    def policy_agent(self, state: ModerationGraphState) -> dict[str, object]:
        submission = state["submission"]
        context = state["context"]
        result = self.service.run_policy_agent(submission, context)
        return {
            "policy": cast(PolicyAgentOutput, result.output),
            "trace": self._append_trace(state, "Policy Agent"),
        }

    def risk_agent(self, state: ModerationGraphState) -> dict[str, object]:
        submission = state["submission"]
        result = self.service.run_risk_agent(submission, state["context"], state["policy"])
        return {
            "risk": cast(RiskAgentOutput, result.output),
            "trace": self._append_trace(state, "Risk Agent"),
        }

    @staticmethod
    def route_after_risk(state: ModerationGraphState) -> str:
        risk = state["risk"]
        if risk.risk_level == "critical" or risk.risk_score >= 0.95:
            return "safety_gate"
        return "decision_agent"

    def safety_gate(self, state: ModerationGraphState) -> dict[str, object]:
        return {
            "safety_override": True,
            "trace": self._append_trace(state, "Safety Gate"),
        }

    def decision_agent(self, state: ModerationGraphState) -> dict[str, object]:
        submission = state["submission"]
        result = self.service.run_decision_agent(
            submission,
            state["context"],
            state["policy"],
            state["risk"],
        )
        return {
            "decision": cast(GeminiModerationOutput, result.output),
            "model_used": result.model_used,
            "trace": self._append_trace(state, "Decision Agent"),
        }

    def guardrail(self, state: ModerationGraphState) -> dict[str, object]:
        decision = state["decision"]
        context = state["context"]
        risk = state["risk"]
        force_review = bool(
            state.get("safety_override")
            or risk.escalation_needed
            or context.ambiguity_score >= 0.75
            or decision.action == "review"
            or decision.confidence < 0.90
        )
        if force_review:
            decision = decision.model_copy(update={"action": "review", "needs_admin_review": True})
        return {
            "decision": decision,
            "trace": self._append_trace(state, "Deterministic Guardrail"),
        }

    def invoke(self, submission: MemberSubmission) -> ModerationGraphState:
        return cast(
            ModerationGraphState,
            self.graph.invoke({"submission": submission, "trace": []}),
        )
