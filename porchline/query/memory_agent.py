"""Natural-Language Memory Query Engine, Lingering Package Anomaly Detector, and Evening Digest Generator.

Features:
1. NL Query Engine: Answers questions like:
   - "When did the courier come?"
   - "Did Amazon drop off a package today?"
   - "Did any animals or pets visit?"
   - "Are there any packages still outside?"
2. Lingering Package Anomaly Detection:
   - Flag packages sitting on porch > 4 hours uncollected.
3. Automated Evening Digest Generator:
   - Compiles a daily briefing of front-door life for 6:00 PM / 8:00 PM.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
import re
from porchline.memory.dynamo_store import DynamoDBEpisodicStore

class PorchlineMemoryAgent:
    def __init__(self, store: DynamoDBEpisodicStore):
        self.store = store

    def detect_lingering_packages(self, threshold_hours: float = 4.0) -> List[Dict[str, Any]]:
        """Identify packages delivered that remain on porch past the threshold."""
        events = self.store.get_timeline(limit=100)
        # Sort ascending for timeline walkthrough
        chronological = sorted(events, key=lambda x: x["created_at"])

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

            elapsed_hours = (now - delivery_dt).total_seconds() / 3600.0

            # Check if a subsequent event indicates package pickup
            picked_up = False
            for ev in chronological:
                if ev["created_at"] > d["created_at"] and "pickup" in ev.get("action", "").lower():
                    picked_up = True
                    break

            if not picked_up and elapsed_hours >= threshold_hours:
                anomalies.append({
                    "type": "lingering_package",
                    "severity": "high",
                    "delivery_event_id": d["event_id"],
                    "carrier": d.get("uniform_carrier", "Unknown Carrier"),
                    "delivered_at": d["created_at"],
                    "hours_lingering": round(elapsed_hours, 1),
                    "description": d.get("parcel_description", "Parcel on porch"),
                    "placement": d.get("placement", "Front porch mat"),
                    "recommendation": f"Package has been outside for {round(elapsed_hours, 1)} hrs. Bring inside to avoid weather or porch piracy."
                })
        return anomalies

    def generate_evening_digest(self) -> Dict[str, Any]:
        """Generate automated end-of-day summary digest."""
        events = self.store.get_timeline(limit=50)
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%A, %B %d, %Y")

        if not events:
            return {
                "date": date_str,
                "headline": "Quiet Front Porch Today",
                "summary": "No front door activity recorded today.",
                "total_events": 0,
                "deliveries": [],
                "visitors": [],
                "anomalies": [],
                "active_packages_outside": 0
            }

        courier_events = [e for e in events if e.get("visitor_type") == "courier" or e.get("parcel_detected")]
        visitor_events = [e for e in events if e.get("visitor_type") in ["neighbor", "resident", "unknown"] and e.get("event_type") == "ding"]
        animal_events = [e for e in events if e.get("visitor_type") == "animal"]
        lingering = self.detect_lingering_packages(threshold_hours=4.0)

        headline_parts = []
        if courier_events:
            headline_parts.append(f"{len(courier_events)} Deliveries")
        if visitor_events:
            headline_parts.append(f"{len(visitor_events)} Doorbell Ring{'s' if len(visitor_events) > 1 else ''}")
        if lingering:
            headline_parts.append(f"⚠️ {len(lingering)} Uncollected Parcel Alert")

        headline = " · ".join(headline_parts) if headline_parts else "Routine Front Porch Activity"

        highlights = []
        for e in sorted(events, key=lambda x: x["created_at"]):
            time_part = e["created_at"][11:16] if "T" in e["created_at"] else e["created_at"]
            highlights.append(f"[{time_part}] {e.get('summary')}")

        return {
            "date": date_str,
            "generated_at": now.isoformat(),
            "headline": headline,
            "total_events_today": len(events),
            "deliveries_count": len(courier_events),
            "visitors_count": len(visitor_events),
            "animal_visits_count": len(animal_events),
            "active_anomalies": lingering,
            "highlights": highlights,
            "verdict": "Attention required: Bring in lingering packages." if lingering else "All quiet and secure at the front door."
        }

    def answer_query(self, query: str) -> Dict[str, Any]:
        """Natural-language question answering against episodic front-door memory."""
        q_lower = query.strip().lower()
        events = self.store.get_timeline(limit=50)

        # 1. Courier / Delivery questions
        if any(w in q_lower for w in ["courier", "delivery", "fedex", "amazon", "ups", "package", "parcel", "box", "mail"]):
            # Check for "still outside" or "lingering"
            if any(w in q_lower for w in ["still outside", "left outside", "unattended", "lingering", "pending"]):
                lingering = self.detect_lingering_packages(threshold_hours=1.0)
                if lingering:
                    l = lingering[0]
                    return {
                        "query": query,
                        "found": True,
                        "answer": f"Yes. 1 {l['carrier']} package ({l['description']}) has been outside on the {l['placement']} for {l['hours_lingering']} hours.",
                        "matched_events": [e for e in events if e.get("parcel_detected")],
                        "category": "package_status"
                    }
                else:
                    return {
                        "query": query,
                        "found": True,
                        "answer": "No packages are currently marked as lingering outside.",
                        "matched_events": [],
                        "category": "package_status"
                    }

            # General delivery lookup
            courier_evs = [e for e in events if e.get("visitor_type") == "courier" or e.get("parcel_detected")]
            if courier_evs:
                latest = courier_evs[0]
                ts = latest["created_at"][11:16] if "T" in latest["created_at"] else latest["created_at"]
                carrier = latest.get("uniform_carrier", "courier")
                action = latest.get("action", "delivered a package")
                placement = latest.get("placement", "porch")
                return {
                    "query": query,
                    "found": True,
                    "answer": f"The courier ({carrier}) arrived at {ts} UTC and {action}. Placed at: {placement}.",
                    "matched_events": courier_evs,
                    "category": "delivery_history"
                }
            return {
                "query": query,
                "found": False,
                "answer": "No courier deliveries have been recorded yet in today's episodic memory.",
                "matched_events": [],
                "category": "delivery_history"
            }

        # 2. Neighbor / Chime / Visitor questions
        if any(w in q_lower for w in ["neighbor", "visitor", "someone", "who came", "chime", "doorbell", "rang", "ring"]):
            visitor_evs = [e for e in events if e.get("visitor_type") in ["neighbor", "resident"] or e.get("event_type") == "ding"]
            if visitor_evs:
                latest = visitor_evs[0]
                ts = latest["created_at"][11:16] if "T" in latest["created_at"] else latest["created_at"]
                return {
                    "query": query,
                    "found": True,
                    "answer": f"A visitor was detected at {ts} UTC. Details: {latest.get('summary')}",
                    "matched_events": visitor_evs,
                    "category": "visitor_history"
                }
            return {
                "query": query,
                "found": False,
                "answer": "No visitor doorbell rings recorded in today's episodic timeline.",
                "matched_events": [],
                "category": "visitor_history"
            }

        # 3. Animal / Pet questions
        if any(w in q_lower for w in ["animal", "pet", "dog", "cat", "creature", "raccoon"]):
            animal_evs = [e for e in events if e.get("visitor_type") == "animal" or "animal" in e.get("event_type", "")]
            if animal_evs:
                latest = animal_evs[0]
                ts = latest["created_at"][11:16] if "T" in latest["created_at"] else latest["created_at"]
                return {
                    "query": query,
                    "found": True,
                    "answer": f"Yes! An animal was spotted at {ts} UTC: {latest.get('summary')}",
                    "matched_events": animal_evs,
                    "category": "animal_detection"
                }
            return {
                "query": query,
                "found": False,
                "answer": "No animal or pet visits detected on the front porch.",
                "matched_events": [],
                "category": "animal_detection"
            }

        # 4. Fallback: Search all event summaries
        keyword_matches = [e for e in events if any(word in e.get("summary", "").lower() for word in q_lower.split() if len(word) > 3)]
        if keyword_matches:
            latest = keyword_matches[0]
            ts = latest["created_at"][11:16] if "T" in latest["created_at"] else latest["created_at"]
            return {
                "query": query,
                "found": True,
                "answer": f"At {ts} UTC: {latest.get('summary')}",
                "matched_events": keyword_matches,
                "category": "general_memory"
            }

        return {
            "query": query,
            "found": False,
            "answer": f"I couldn't find any porch events matching '{query}'. Try asking 'When did the courier come?' or 'Are there any packages outside?'.",
            "matched_events": [],
            "category": "not_found"
        }
