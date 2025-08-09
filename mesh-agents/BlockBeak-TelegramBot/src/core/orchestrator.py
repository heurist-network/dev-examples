#!/usr/bin/env python3

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from pydantic import BaseModel
from agents import Agent as OpenAIAgent, Runner, handoff, gen_trace_id, trace, ModelSettings
from agents.mcp import MCPServerSse

from src.config.settings import Settings

logger = logging.getLogger(__name__)


# -------- Structured handoff payloads ---------

class ResearchAdvice(BaseModel):
    summary: str
    recommendation: str  # buy | sell | hold | transfer | tip | none
    asset: Optional[str] = None
    chain: Optional[str] = None
    amount: Optional[str] = None
    recipient: Optional[str] = None
    confidence: Optional[str] = None
    rationale: Optional[str] = None


class DelegationRequest(BaseModel):
    action: str  # buy | sell | transfer | tip
    asset: str
    amount: str
    chain: str
    sender_inbox_id: Optional[str] = None
    recipient: Optional[str] = None
    note: Optional[str] = None
    ref: Optional[str] = None  # conversation/message reference


class TriageOrchestrator:
    """Multi-agent orchestrator implementing Triage → BlockBeak → BankrDelegator."""

    def __init__(self, config_override: Optional[Dict[str, Any]] = None):
        settings = Settings()
        cfg = settings.get_openai_config()
        if config_override:
            cfg.update(config_override)

        self.model = cfg["model"]
        self.temperature = cfg.get("temperature", 0.1)
        self.max_tokens = cfg.get("max_tokens", 10000)
        self.mcp_sse_url = cfg["mcp_sse_url"]

        # Context that will be visible to all agents
        self.context: Dict[str, Any] = {
            "bankr_handle": settings.bankr_handle,
            "default_chain": settings.default_chain,
        }

        # Shared MCP server
        self.mcp_server = MCPServerSse(
            name="MCP SSE Server",
            params={"url": self.mcp_sse_url},
            client_session_timeout_seconds=60,
        )

        # Model settings kept conservative; triage will be concise
        # Increase caps if using GPT-5 family
        is_gpt5 = str(self.model).split("/")[-1].startswith("gpt-5")
        self.model_settings = ModelSettings(
            temperature=self.temperature,
            max_tokens=min(self.max_tokens, 64000 if is_gpt5 else 8000),
        )

        # Build agents and wire handoffs
        self._build_agents(settings)
        self.trace_id: Optional[str] = None

    def _build_agents(self, settings: Settings) -> None:
        # BankrDelegator: emits text-only, machine-parseable command line
        bankr_instructions = settings.get_agent_instructions_by_name("bankr_delegator")
        self.bankr = OpenAIAgent(
            name="BankrDelegator",
            instructions=bankr_instructions,
            mcp_servers=[self.mcp_server],
            model=self.model,
            model_settings=self.model_settings,
        )

        # Triage placeholder so BlockBeak can reference it in its handoff
        triage_instructions = settings.get_agent_instructions_by_name("triage")
        self.triage = OpenAIAgent(
            name="Triage",
            instructions=triage_instructions,
            mcp_servers=[self.mcp_server],
            model=self.model,
            model_settings=self.model_settings,
        )

        # BlockBeak research agent that MUST handoff back with ResearchAdvice
        blockbeak_instructions = settings.get_agent_instructions_by_name("blockbeak")
        self.blockbeak = OpenAIAgent(
            name="BlockBeak",
            instructions=blockbeak_instructions,
            mcp_servers=[self.mcp_server],
            model=self.model,
            model_settings=self.model_settings,
            handoffs=[self.triage],
        )

        # Add outgoing handoffs from triage to children agents
        # Note: triage.handoffs expects Agent objects (not handoff() tools)
        self.triage.handoffs = [self.blockbeak, self.bankr]

    async def process_message(
        self,
        message: str,
        context_update: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        """Run the triage flow and return final text and trace URL."""

        if context_update:
            self.context.update(context_update)

        self.trace_id = gen_trace_id()

        async with self.mcp_server:
            with trace(workflow_name="BlockBeak Multi-Agent Orchestration", trace_id=self.trace_id):
                result = await Runner.run(
                    starting_agent=self.triage,
                    input=message,
                    context=self.context,
                )

        return {"output": result.final_output, "trace_url": self.get_trace_url()}

    def get_trace_url(self) -> str:
        return f"https://platform.openai.com/traces/trace?trace_id={self.trace_id}"


def create_triage_orchestrator(config_override: Optional[Dict[str, Any]] = None) -> TriageOrchestrator:
    return TriageOrchestrator(config_override)


