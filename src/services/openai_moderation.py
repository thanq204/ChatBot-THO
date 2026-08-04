"""OpenAI structured-output provider for the multi-agent moderation graph."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from src.config import Settings
from src.models.moderation import (
    ContextAgentOutput,
    GeminiModerationOutput,
    MemberSubmission,
    PolicyAgentOutput,
    RiskAgentOutput,
)
from src.services.gemini_moderation import GeminiAgentStageResult, GeminiStageResult, GeminiModerationService


class OpenAIModerationError(RuntimeError):
    def __init__(self, code: str, user_message: str) -> None:
        super().__init__(code)
        self.code = code
        self.user_message = user_message


@dataclass(frozen=True)
class OpenAIUsage:
    model_used: str


class OpenAIModerationService:
    """Provider-compatible service used by the existing LangGraph specialist flow."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def moderate_with_triage(self, submission: MemberSubmission) -> GeminiStageResult:
        return self._generate(self._prompt(submission, "triage"))

    def review_ambiguous_content(self, submission: MemberSubmission, triage: GeminiStageResult) -> GeminiStageResult:
        return self._generate(self._prompt(submission, "review", triage.output))

    def run_context_agent(self, submission: MemberSubmission) -> GeminiAgentStageResult:
        return self.generate_structured(
            self._agent_prompt(submission, "context", "Interpret intent, tone and ambiguity."),
            ContextAgentOutput,
            "Context Agent",
        )

    def run_policy_agent(self, submission: MemberSubmission, context: ContextAgentOutput) -> GeminiAgentStageResult:
        return self.generate_structured(
            self._agent_prompt(
                submission,
                "policy",
                "Map the message to exactly one moderation policy.\ncontext_agent_output:\n" + context.model_dump_json(),
            ),
            PolicyAgentOutput,
            "Policy Agent",
        )

    def run_risk_agent(self, submission: MemberSubmission, context: ContextAgentOutput, policy: PolicyAgentOutput) -> GeminiAgentStageResult:
        return self.generate_structured(
            self._agent_prompt(
                submission,
                "risk",
                "Score safety risk and decide whether escalation is needed.\n"
                f"context_agent_output:\n{context.model_dump_json()}\n"
                f"policy_agent_output:\n{policy.model_dump_json()}",
            ),
            RiskAgentOutput,
            "Risk Agent",
        )

    def run_decision_agent(self, submission: MemberSubmission, context: ContextAgentOutput, policy: PolicyAgentOutput, risk: RiskAgentOutput) -> GeminiAgentStageResult:
        return self.generate_structured(
            self._agent_prompt(
                submission,
                "decision",
                "Produce the final moderation decision using all specialist outputs.\n"
                f"context_agent_output:\n{context.model_dump_json()}\n"
                f"policy_agent_output:\n{policy.model_dump_json()}\n"
                f"risk_agent_output:\n{risk.model_dump_json()}",
            ),
            GeminiModerationOutput,
            "Decision Agent",
        )

    def generate_structured(self, prompt: str, schema: type[BaseModel], agent_name: str) -> GeminiAgentStageResult:
        try:
            from langchain_openai import ChatOpenAI

            llm = ChatOpenAI(
                model=self.settings.openai_moderation_model,
                api_key=self.settings.openai_api_key,
                temperature=self.settings.llm_temperature,
            )
            try:
                structured = llm.with_structured_output(schema, method="json_schema")
            except TypeError:
                structured = llm.with_structured_output(schema)
            output: Any = structured.invoke(prompt)
            if isinstance(output, dict):
                output = schema.model_validate(output)
            if not isinstance(output, BaseModel):
                raise ValueError("OpenAI returned an unexpected structured-output type.")
            return GeminiAgentStageResult(
                output=output,
                model_used=self.settings.openai_moderation_model,
                agent_name=agent_name,
            )
        except Exception as exc:
            raise OpenAIModerationError(
                "invalid_structured_output" if "schema" in str(exc).lower() or "validation" in str(exc).lower() else "network_or_api",
                "OpenAI không trả về structured output hợp lệ. Hãy kiểm tra model, key và quota.",
            ) from exc

    def _generate(self, prompt: str) -> GeminiStageResult:
        result = self.generate_structured(prompt, GeminiModerationOutput, "Moderation Agent")
        return GeminiStageResult(output=result.output, model_used=result.model_used)

    @staticmethod
    def _prompt(submission: MemberSubmission, stage: str, triage: GeminiModerationOutput | None = None) -> str:
        return GeminiModerationService._prompt(submission, stage, triage)

    @staticmethod
    def _agent_prompt(submission: MemberSubmission, agent: str, task: str) -> str:
        return GeminiModerationService._agent_prompt(submission, agent, task)
