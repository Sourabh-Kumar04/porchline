"""Natural-Language Memory Query Engine, Lingering Package Anomaly Detector, and Evening Digest Generator.

Powered by Porchline's 4 Cooperating Agents:
- Perceiver: Multimodal VLM scene analysis
- Memorian: Semantic consolidation & learned household routine baselines
- Sentinel: Anomaly reasoning, causal narratives, and proactive action triggers
- Chronicler: Evening digest synthesis, storytelling, and conversational Q&A
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta

from porchline.memory.dynamo_store import DynamoDBEpisodicStore
from porchline.agents.memorian import MemorianAgent, HouseholdRoutineProfile
from porchline.agents.sentinel import SentinelAgent
from porchline.agents.chronicler import ChroniclerAgent
from porchline.agents.coordinator import PorchlineAgentCoordinator


class PorchlineMemoryAgent:
    """High-level episodic memory facade coordinating Memorian, Sentinel, and Chronicler."""

    def __init__(self, store: DynamoDBEpisodicStore):
        self.store = store
        self.memorian = MemorianAgent(store)
        self.sentinel = SentinelAgent(store, self.memorian)
        self.chronicler = ChroniclerAgent(store, self.memorian, self.sentinel)
        self.coordinator = PorchlineAgentCoordinator(store)

    def detect_lingering_packages(self, threshold_hours: float = 2.0) -> List[Dict[str, Any]]:
        """Identify packages delivered that remain on porch past the threshold."""
        events = self.store.get_timeline(limit=100)
        chronological = sorted(events, key=lambda x: x.get("created_at", ""))

        deliveries = []
        for ev in chronological:
            if ev.get("parcel_detected") and ev.get("visitor_type") == "courier":
                deliveries.append(ev)

        anomalies = []
        now = datetime.now(timezone.utc)
        for d in deliveries:
            try:
                delivery_dt = datetime.fromisoformat(d["created_at"].replace("Z", "+00:00"))
            except Exception:
                delivery_dt = now - timedelta(hours=5)

            elapsed_hours = max(0.0, (now - delivery_dt).total_seconds() / 3600.0)

            # Check if picked up or stolen
            subsequent = [e for e in chronological if e.get("created_at", "") > d.get("created_at", "")]
            picked_up = any("pickup" in e.get("action", "").lower() or "retrieved" in e.get("action", "").lower() for e in subsequent)

            if not picked_up and elapsed_hours >= threshold_hours:
                hours_lingering = round(elapsed_hours, 1)
                carrier = d.get("uniform_carrier", "Unknown Carrier")
                anomalies.append({
                    "type": "lingering_package",
                    "severity": "high" if elapsed_hours >= 4.0 else "moderate",
                    "delivery_event_id": d["event_id"],
                    "carrier": carrier,
                    "delivered_at": d["created_at"],
                    "hours_lingering": hours_lingering,
                    "description": d.get("parcel_description", "Parcel on porch"),
                    "placement": d.get("placement", "Front porch mat"),
                    "recommendation": f"Package has been outside for {hours_lingering} hrs. Bring inside to avoid weather or porch piracy.",
                    "routine_reason": f"Deviates from normal household collection window (2.5h maximum baseline).",
                    "proactive_actions": [
                        {
                            "action_id": "act_alexa_announce",
                            "label": "Announce on Echo / Alexa",
                            "action_type": "chime",
                            "severity": "high",
                            "description": "Broadcast porch reminder on Alexa smart speakers."
                        },
                        {
                            "action_id": "act_push_notify",
                            "label": "Send Urgent Mobile Ping",
                            "action_type": "push",
                            "severity": "high",
                            "description": "Dispatch priority push alert with snapshot to phones."
                        },
                        {
                            "action_id": "act_neighbor_stash",
                            "label": "Ask Neighbor Sarah to Stash",
                            "action_type": "sms",
                            "severity": "moderate",
                            "description": "One-tap text request to trusted neighbor Sarah."
                        }
                    ]
                })
        return anomalies

    def generate_evening_digest(self) -> Dict[str, Any]:
        """Generate automated end-of-day summary digest via Chronicler Agent."""
        return self.chronicler.generate_evening_digest()

    def answer_query(self, query: str) -> Dict[str, Any]:
        """Natural-language question answering against episodic memory via Chronicler Agent."""
        return self.chronicler.answer_query(query)

    def get_routines(self) -> Dict[str, Any]:
        """Retrieve learned household routine profile via Memorian Agent."""
        prof = self.memorian.get_or_build_profile()
        return {
            "device_id": prof.device_id,
            "quiet_hours": prof.quiet_hours,
            "delivery_windows": prof.delivery_windows,
            "recurring_visitors": prof.recurring_visitors,
            "baseline_stats": prof.baseline_stats,
            "last_consolidated": prof.last_consolidated
        }

    def get_causal_narratives(self) -> List[Dict[str, Any]]:
        """Retrieve active causal evidence chains via Sentinel Agent."""
        analysis = self.sentinel.analyze_timeline()
        return analysis.get("narratives", [])
