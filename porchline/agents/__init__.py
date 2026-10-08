"""Porchline Cooperating Agent Architecture.

Four specialized agents communicating through the DynamoDB event timeline:
1. Perceiver: Multimodal VLM scene analysis (Bedrock Claude 3.5 Sonnet / Nova).
2. Memorian: Episodic-to-semantic memory consolidation & learned routine profiles.
3. Sentinel: Anomaly reasoning, routine deviation detection, and causal evidence chains.
4. Chronicler: Evening digest synthesis, natural-language Q&A, and causal narratives.
"""

from porchline.agents.perceiver import PerceiverAgent
from porchline.agents.memorian import MemorianAgent, HouseholdRoutineProfile
from porchline.agents.sentinel import SentinelAgent, CausalNarrative, AnomalyAlert, ProactiveAction
from porchline.agents.chronicler import ChroniclerAgent
from porchline.agents.coordinator import PorchlineAgentCoordinator

__all__ = [
    "PerceiverAgent",
    "MemorianAgent",
    "HouseholdRoutineProfile",
    "SentinelAgent",
    "CausalNarrative",
    "AnomalyAlert",
    "ProactiveAction",
    "ChroniclerAgent",
    "PorchlineAgentCoordinator",
]
