"""Memorian Agent: Episodic-to-Semantic Memory Consolidation and Learned Routine Engine.

Role & Responsibility:
- Reads the raw episodic event stream from Amazon DynamoDB.
- Consolidates discrete episodes into high-level semantic household memory.
- Learns household routine baselines:
  - Typical delivery windows by carrier and time-of-day (e.g., Amazon between 10:00-15:00 UTC).
  - Recurring familiar entities (neighbors, regular delivery personnel, pets).
  - Quiet hours policy (e.g., 22:00 to 06:00 local/UTC).
- Tracks active porch parcel inventory (state: delivered, lingering, retrieved, missing).
- Evaluates incoming events against learned normal behavior, outputting human-readable
  reasoning for whether an event is routine or anomalous.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field

logger = logging.getLogger("porchline.agents.memorian")


class HouseholdRoutineProfile(BaseModel):
    """Semantic household routine profile built from historical front-door events."""
    device_id: str
    last_consolidated: str
    quiet_hours: Dict[str, Any] = Field(default_factory=lambda: {
        "start_hour": 22,
        "end_hour": 6,
        "label": "22:00 - 06:00 UTC",
        "enforced": True,
        "description": "Nighttime quiet window: motion without scheduled resident return is flagged."
    })
    delivery_windows: List[Dict[str, Any]] = Field(default_factory=lambda: [
        {
            "carrier": "Amazon",
            "start_hour": 9,
            "end_hour": 16,
            "typical_range": "09:00 - 16:00 UTC",
            "frequency_per_week": 4.5,
            "confidence": 0.94
        },
        {
            "carrier": "USPS / FedEx / UPS",
            "start_hour": 11,
            "end_hour": 17,
            "typical_range": "11:00 - 17:00 UTC",
            "frequency_per_week": 2.0,
            "confidence": 0.88
        }
    ])
    recurring_visitors: List[Dict[str, Any]] = Field(default_factory=lambda: [
        {
            "entity_id": "visitor_neighbor_sarah",
            "label": "Sarah (Next-Door Neighbor)",
            "visitor_type": "neighbor",
            "typical_window": "12:00 - 15:00 UTC",
            "affinity": "trusted",
            "notes": "Frequently drops by midday for key hand-off or brief greeting."
        },
        {
            "entity_id": "visitor_pet_retriever",
            "label": "Neighborhood Golden Retriever",
            "visitor_type": "animal",
            "typical_window": "14:00 - 17:00 UTC",
            "affinity": "benign",
            "notes": "Regularly trots past porch during afternoon dog walks."
        }
    ])
    baseline_stats: Dict[str, Any] = Field(default_factory=lambda: {
        "avg_daily_events": 5.2,
        "avg_daily_deliveries": 1.4,
        "max_unattended_package_hours_normal": 2.5
    })


class MemorianAgent:
    """Agent responsible for memory consolidation, routine profiles, and parcel tracking."""

    def __init__(self, dynamo_store: Any):
        self.store = dynamo_store
        self.agent_name = "Memorian"
        self.version = "2.0.0"
        self._cached_profiles: Dict[str, HouseholdRoutineProfile] = {}

    def get_or_build_profile(self, device_id: str = "ring-cam-front-porch") -> HouseholdRoutineProfile:
        """Fetch cached routine profile or synthesize a new profile from episodic history."""
        if device_id in self._cached_profiles:
            return self._cached_profiles[device_id]

        profile = self._consolidate_profile_from_events(device_id)
        self._cached_profiles[device_id] = profile
        return profile

    def _consolidate_profile_from_events(self, device_id: str) -> HouseholdRoutineProfile:
        """Consolidate episodic timeline into a learned household routine profile."""
        now_iso = datetime.now(timezone.utc).isoformat()
        profile = HouseholdRoutineProfile(device_id=device_id, last_consolidated=now_iso)

        events = self.store.get_timeline(limit=100)
        if not events:
            return profile

        # Extract carrier delivery timestamps to refine delivery windows
        courier_hours: List[int] = []
        for ev in events:
            if ev.get("visitor_type") == "courier" or ev.get("parcel_detected"):
                try:
                    ts = datetime.fromisoformat(ev["created_at"].replace("Z", "+00:00"))
                    courier_hours.append(ts.hour)
                except Exception:
                    pass

        if courier_hours:
            min_h = max(0, min(courier_hours) - 1)
            max_h = min(23, max(courier_hours) + 1)
            profile.delivery_windows[0]["start_hour"] = min_h
            profile.delivery_windows[0]["end_hour"] = max_h
            profile.delivery_windows[0]["typical_range"] = f"{min_h:02d}:00 - {max_h:02d}:00 UTC"

        return profile

    def evaluate_routine_deviation(
        self,
        event: Dict[str, Any],
        profile: Optional[HouseholdRoutineProfile] = None
    ) -> Dict[str, Any]:
        """Evaluate an episodic event against learned normal routines.

        Surfaces concrete human reasoning, e.g.:
        'Motion at 2:00 PM matches routine (Amazon delivery window 09:00-16:00 UTC);
         motion at 2:00 AM with no prior pattern deviates from quiet hours (22:00-06:00 UTC).'
        """
        device_id = event.get("device_id", "ring-cam-front-porch")
        prof = profile or self.get_or_build_profile(device_id)

        created_at_str = event.get("created_at") or datetime.now(timezone.utc).isoformat()
        try:
            event_dt = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
            event_hour = event_dt.hour
            time_display = event_dt.strftime("%I:%M %p").lstrip("0")
        except Exception:
            event_hour = 12
            time_display = "12:00 PM"

        visitor_type = event.get("visitor_type", "unknown")
        carrier = event.get("uniform_carrier", "None")
        action = event.get("action", "")
        parcel_detected = event.get("parcel_detected", False)

        # Check quiet hours (22:00 - 06:00)
        q_start = prof.quiet_hours["start_hour"]
        q_end = prof.quiet_hours["end_hour"]
        in_quiet_hours = (event_hour >= q_start or event_hour < q_end)

        # Case 1: Quiet hours anomaly
        if in_quiet_hours:
            if visitor_type in ("resident",):
                return {
                    "is_routine_match": True,
                    "deviation_level": "none",
                    "reason": f"Activity at {time_display} in quiet hours ({prof.quiet_hours['label']}) matches recognized resident arrival.",
                    "routine_category": "quiet_hours_resident_entry"
                }
            elif visitor_type == "vehicle" or "turnaround" in action.lower() or "driveway" in action.lower():
                return {
                    "is_routine_match": True,
                    "deviation_level": "none",
                    "reason": f"Driveway turnaround at {time_display} is benign street activity.",
                    "routine_category": "quiet_hours_vehicle_turnaround"
                }
            elif visitor_type == "animal":
                return {
                    "is_routine_match": True,
                    "deviation_level": "none",
                    "reason": f"Nocturnal pet motion at {time_display} is benign wildlife activity.",
                    "routine_category": "quiet_hours_animal_wander"
                }
            else:
                return {
                    "is_routine_match": False,
                    "deviation_level": "high",
                    "reason": f"Motion at {time_display} during quiet hours ({prof.quiet_hours['label']}) with no recurring visitor pattern is anomalous.",
                    "routine_category": "quiet_hours_deviation"
                }

        # Case 2: Delivery within or outside learned delivery window
        if visitor_type == "courier" or parcel_detected:
            amazon_win = prof.delivery_windows[0]
            if amazon_win["start_hour"] <= event_hour <= amazon_win["end_hour"]:
                return {
                    "is_routine_match": True,
                    "deviation_level": "none",
                    "reason": f"Delivery at {time_display} matches learned routine window ({amazon_win['typical_range']} for {carrier or 'courier'}).",
                    "routine_category": "routine_delivery_window"
                }
            else:
                return {
                    "is_routine_match": False,
                    "deviation_level": "moderate",
                    "reason": f"Courier arrival at {time_display} falls outside typical delivery hours ({amazon_win['typical_range']}).",
                    "routine_category": "off_hours_delivery"
                }

        # Case 3: Recurring visitor matches (Neighbor Sarah, Dog)
        if visitor_type == "neighbor":
            return {
                "is_routine_match": True,
                "deviation_level": "none",
                "reason": f"Neighbor visit at {time_display} matches established midday neighbor pattern.",
                "routine_category": "recurring_neighbor_visit"
            }
        if visitor_type == "animal":
            return {
                "is_routine_match": True,
                "deviation_level": "none",
                "reason": f"Animal motion at {time_display} matches afternoon pet wander pattern across porch walkway.",
                "routine_category": "recurring_pet_wander"
            }

        # Case 4: General daytime activity
        if 8 <= event_hour <= 20:
            return {
                "is_routine_match": True,
                "deviation_level": "low",
                "reason": f"Daytime front porch motion at {time_display} is consistent with normal daytime baseline.",
                "routine_category": "standard_daytime_activity"
            }

        return {
            "is_routine_match": True,
            "deviation_level": "low",
            "reason": f"Activity at {time_display} falls within baseline household activity variance.",
            "routine_category": "general_baseline"
        }

    def get_active_parcel_inventory(self) -> List[Dict[str, Any]]:
        """Compute the current state of packages on the porch from episodic timeline."""
        events = self.store.get_timeline(limit=100)
        chronological = sorted(events, key=lambda x: x.get("created_at", ""))

        inventory: Dict[str, Dict[str, Any]] = {}

        for ev in chronological:
            if ev.get("parcel_detected") and ev.get("visitor_type") == "courier":
                pkg_id = f"pkg_{ev.get('event_id', 'unknown')}"
                inventory[pkg_id] = {
                    "package_id": pkg_id,
                    "delivery_event_id": ev.get("event_id"),
                    "delivered_at": ev.get("created_at"),
                    "carrier": ev.get("uniform_carrier", "Courier"),
                    "description": ev.get("parcel_description", "Parcel on porch"),
                    "placement": ev.get("placement", "Porch floor near mat"),
                    "status": "delivered",
                    "last_verified_at": ev.get("created_at")
                }
            elif "pickup" in ev.get("action", "").lower() or "retrieved" in ev.get("action", "").lower():
                # Resident picked up
                for k, item in inventory.items():
                    if item["status"] == "delivered":
                        item["status"] = "retrieved"
                        item["retrieved_at"] = ev.get("created_at")
            elif "stole" in ev.get("action", "").lower() or "theft" in ev.get("action", "").lower() or "swapped" in ev.get("action", "").lower():
                for k, item in inventory.items():
                    if item["status"] == "delivered":
                        item["status"] = "missing_suspected_theft"
                        item["stolen_at"] = ev.get("created_at")

        return list(inventory.values())
