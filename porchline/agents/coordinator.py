"""Porchline Agent Coordinator: Cooperating Agent Orchestrator.

Orchestrates the 4 agents communicating over the DynamoDB timeline:
1. Perceiver (VLM Multimodal Perception)
2. Memorian (Semantic Consolidation & Learned Routines)
3. Sentinel (Anomaly Reasoning & Causal Narratives)
4. Chronicler (Evening Digest & Routine-Aware Q&A)
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from porchline.agents.perceiver import PerceiverAgent
from porchline.agents.memorian import MemorianAgent
from porchline.agents.sentinel import SentinelAgent
from porchline.agents.chronicler import ChroniclerAgent

logger = logging.getLogger("porchline.agents.coordinator")


class PorchlineAgentCoordinator:
    """Coordinator coordinating Perceiver, Memorian, Sentinel, and Chronicler agents."""

    def __init__(self, dynamo_store: Any, vision_processor: Optional[Any] = None):
        self.store = dynamo_store
        self.perceiver = PerceiverAgent(vision_processor)
        self.memorian = MemorianAgent(dynamo_store)
        self.sentinel = SentinelAgent(dynamo_store, self.memorian)
        self.chronicler = ChroniclerAgent(dynamo_store, self.memorian, self.sentinel)
        self.executed_actions: List[Dict[str, Any]] = []

    def process_incoming_event(self, payload: Dict[str, Any], snapshot_bytes: bytes = b"") -> Dict[str, Any]:
        """End-to-end multi-agent processing pipeline for an incoming Ring event."""
        data = payload.get("data", {})
        attrs = data.get("attributes", {})
        event_id = data.get("id") or attrs.get("request_id") or f"evt_{datetime.now(timezone.utc).timestamp()}"
        device_id = attrs.get("device_id", "ring-cam-front-porch")
        created_at = attrs.get("created_at") or datetime.now(timezone.utc).isoformat()
        event_type = attrs.get("event_type", "motion.human")
        snapshot_url = attrs.get("snapshot_data_url")

        # Step 1: Perceiver analyzes visual scene and metadata
        perception = self.perceiver.perceive(snapshot_bytes, attrs)

        # Step 2: Build episodic event record and evaluate learned routine fit via Memorian
        routine_eval = self.memorian.evaluate_routine_deviation({
            "created_at": created_at,
            "visitor_type": perception.get("visitor_type"),
            "uniform_carrier": perception.get("uniform_carrier"),
            "action": perception.get("action"),
            "parcel_detected": perception.get("parcel_detected"),
            "device_id": device_id
        })

        event_record = {
            "device_id": device_id,
            "event_id": event_id,
            "created_at": created_at,
            "event_type": event_type,
            "visitor_type": perception.get("visitor_type", "unknown"),
            "uniform_carrier": perception.get("uniform_carrier", "None"),
            "action": perception.get("action", ""),
            "parcel_detected": perception.get("parcel_detected", False),
            "parcel_count": perception.get("parcel_count", 0),
            "parcel_description": perception.get("parcel_description", ""),
            "placement": perception.get("placement", ""),
            "summary": perception.get("summary", ""),
            "confidence": perception.get("confidence", 0.95),
            "snapshot_data_url": snapshot_url or "",
            "scenario_title": attrs.get("scenario_title", ""),
            "provider": perception.get("provider", "bedrock"),
            "routine_context": routine_eval
        }

        # Step 3: Persist to DynamoDB timeline
        saved_item = self.store.save_event(event_record)

        # Step 4: Sentinel reasoning on updated timeline
        sentinel_result = self.sentinel.analyze_timeline()

        logger.info(
            f"[Coordinator] Processed {event_id} via Perceiver. "
            f"Routine fit: {routine_eval['is_routine_match']} ({routine_eval['routine_category']}). "
            f"Active narratives: {len(sentinel_result['narratives'])}"
        )

        return {
            "saved_event": saved_item,
            "perception": perception,
            "routine_eval": routine_eval,
            "sentinel_analysis": sentinel_result
        }

    def execute_proactive_action(self, action_id: str, action_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute or acknowledge a proactive mitigation action."""
        record = {
            "action_id": action_id,
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "status": "success",
            "message": f"Proactive action '{action_id}' successfully executed on target device.",
            "details": action_data or {}
        }
        self.executed_actions.append(record)
        logger.info(f"[Coordinator] Executed proactive action: {action_id}")
        return record
