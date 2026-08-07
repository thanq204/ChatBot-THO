from backend.agents.moderation_graph import ModerationAgentGraph
from backend.models.moderation import (
    ContextAgentOutput,
    GeminiModerationOutput,
    MemberSubmission,
    PolicyAgentOutput,
    RiskAgentOutput,
)
from backend.services.gemini_moderation import GeminiAgentStageResult


class FakeAgentService:
    def run_context_agent(self, submission):
        return GeminiAgentStageResult(
            ContextAgentOutput(
                intent="threat", tone="hostile", context_summary="Direct threat.",
                ambiguity_score=0.1, evidence=[submission.text],
            ),
            "context-model",
            "Context Agent",
        )

    def run_policy_agent(self, submission, context):
        return GeminiAgentStageResult(
            PolicyAgentOutput(
                category="violence", policy_id="violence_policy_001",
                policy_match="Threat policy", violation_signal=True, evidence=[submission.text],
            ),
            "policy-model",
            "Policy Agent",
        )

    def run_risk_agent(self, submission, context, policy):
        return GeminiAgentStageResult(
            RiskAgentOutput(
                risk_level="critical", risk_score=0.98, escalation_needed=True,
                rationale="Critical threat requires human review.", evidence=[submission.text],
            ),
            "risk-model",
            "Risk Agent",
        )

    def run_decision_agent(self, submission, context, policy, risk):
        return GeminiAgentStageResult(
            GeminiModerationOutput(
                action="hide", category="violence", risk_level="critical",
                policy_id="violence_policy_001", reason="Threat detected.", confidence=0.96,
                needs_admin_review=False, evidence=[submission.text],
            ),
            "decision-model",
            "Decision Agent",
        )


def test_critical_risk_uses_safety_gate_and_forces_review():
    graph = ModerationAgentGraph(FakeAgentService())
    state = graph.invoke(MemberSubmission(user_id="U001", text="Đe dọa bạo lực"))

    assert state["decision"].action == "review"
    assert state["decision"].needs_admin_review is True
    assert state["trace"] == [
        "Context Agent",
        "Policy Agent",
        "Risk Agent",
        "Safety Gate",
        "Decision Agent",
        "Deterministic Guardrail",
    ]
