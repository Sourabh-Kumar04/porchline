"""Ring Partner API Webhook Simulator and Scenario Generator.

Implements JSON:API specification payloads with HMAC-SHA256 signature verification headers.
Supported Event Types:
- ding (Doorbell press)
- motion.human (Person detected)
- motion.vehicle (Vehicle detected)
- motion.animal (Pet / Animal detected)
- package_delivery (Package alert on porch)
"""

import hmac
import hashlib
import json
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import requests
from porchline.simulator.frame_generator import generate_scene_image, get_base64_scene_image

DEFAULT_RING_SECRET = "porchline_ring_webhook_secret_2026_hackathon"

def get_default_secret() -> str:
    """Return configured secret from RING_WEBHOOK_SECRET env var, falling back to local dev secret."""
    import os
    return os.environ.get("RING_WEBHOOK_SECRET", DEFAULT_RING_SECRET)

def compute_ring_signature(payload_bytes: bytes, secret: Optional[str] = None) -> str:
    """Compute Ring Partner API HMAC-SHA256 signature (hex format)."""
    resolved_secret = secret if secret is not None else get_default_secret()
    return hmac.new(resolved_secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()

def create_ring_event_payload(
    event_type: str,
    device_id: str = "ring-cam-front-porch",
    request_id: Optional[str] = None,
    created_at: Optional[str] = None,
    attributes_override: Optional[Dict[str, Any]] = None,
    snapshot_data_url: Optional[str] = None
) -> Dict[str, Any]:
    """Build a spec-compliant JSON:API payload matching Ring Partner API specifications."""
    req_id = request_id or f"req_{uuid.uuid4().hex[:16]}"
    ts = created_at or datetime.now(timezone.utc).isoformat()
    event_id = f"evt_{uuid.uuid4().hex[:12]}"

    attributes = {
        "event_type": event_type,
        "created_at": ts,
        "device_id": device_id,
        "request_id": req_id,
        "state": "active",
        "battery_level": 88,
        "firmware_version": "v2026.4.1",
        "snapshot_url": f"https://api.amazonvision.com/v1/devices/{device_id}/snapshot?token={req_id}",
    }
    if snapshot_data_url:
        attributes["snapshot_data_url"] = snapshot_data_url

    if attributes_override:
        attributes.update(attributes_override)

    payload = {
        "data": {
            "type": "ring_event",
            "id": event_id,
            "attributes": attributes,
            "relationships": {
                "device": {
                    "data": {"type": "device", "id": device_id}
                }
            }
        },
        "meta": {
            "api_version": "1.0",
            "spec": "json:api",
            "schema": "https://api.amazonvision.com/schemas/v1/events.json"
        }
    }
    return payload

class ScenarioCatalog:
    """Catalog of realistic front-door scenarios for testing and demonstration."""

    @staticmethod
    def get_preset_scenarios() -> List[Dict[str, Any]]:
        base_time = datetime.now(timezone.utc) - timedelta(hours=6)

        scenarios = [
            {
                "id": "morning_courier_amazon",
                "title": "Amazon Prime Courier Package Drop-off",
                "subtitle": "Courier in Amazon vest places parcel on mat",
                "event_type": "package_delivery",
                "device_id": "ring-cam-front-porch",
                "time_offset_hours": -5.5,
                "badge_color": "#2563eb",
                "package_present": True,
                "scenario_type": "package_delivery",
                "simulated_visual_truth": {
                    "visitor_type": "courier",
                    "uniform_carrier": "Amazon",
                    "action": "delivered package",
                    "parcel_detected": True,
                    "parcel_count": 1,
                    "parcel_description": "Medium Amazon cardboard box with Prime tape",
                    "placement": "Left side of welcome mat",
                    "urgency": "normal"
                }
            },
            {
                "id": "midday_neighbor_visit",
                "title": "Neighbor Quick Visit / Hand-off",
                "subtitle": "Neighbor Sarah drops off spare garden keys",
                "event_type": "ding",
                "device_id": "ring-cam-front-porch",
                "time_offset_hours": -3.0,
                "badge_color": "#10b981",
                "package_present": True,  # Amazon box still lingering!
                "scenario_type": "neighbor_visit",
                "simulated_visual_truth": {
                    "visitor_type": "neighbor",
                    "uniform_carrier": "None",
                    "action": "rang doorbell and left keys on ledge",
                    "parcel_detected": True,
                    "parcel_count": 1,
                    "parcel_description": "Amazon box still resting on porch floor",
                    "placement": "Porch floor near mat",
                    "urgency": "low"
                }
            },
            {
                "id": "afternoon_pet_wander",
                "title": "Golden Retriever Porch Visit",
                "subtitle": "Neighbor's dog trots across front porch",
                "event_type": "motion.animal",
                "device_id": "ring-cam-front-porch",
                "time_offset_hours": -1.5,
                "badge_color": "#f59e0b",
                "package_present": True,  # Box still lingering!
                "scenario_type": "pet_detected",
                "simulated_visual_truth": {
                    "visitor_type": "animal",
                    "uniform_carrier": "None",
                    "action": "wandered onto porch and sniffed package",
                    "parcel_detected": True,
                    "parcel_count": 1,
                    "parcel_description": "Amazon box remains undisturbed on mat",
                    "placement": "Porch floor near mat",
                    "urgency": "low"
                }
            },
            {
                "id": "evening_lingering_alert",
                "title": "Lingering Package Anomaly (>4 hours)",
                "subtitle": "Porchline alerts package left unattended 5+ hours",
                "event_type": "motion.human",
                "device_id": "ring-cam-front-porch",
                "time_offset_hours": -0.2,
                "badge_color": "#dc2626",
                "package_present": True,
                "scenario_type": "lingering_package",
                "simulated_visual_truth": {
                    "visitor_type": "resident",
                    "uniform_carrier": "None",
                    "action": "approached door",
                    "parcel_detected": True,
                    "parcel_count": 1,
                    "parcel_description": "Uncollected Amazon parcel still outdoors after dark",
                    "placement": "Porch floor near mat",
                    "urgency": "high"
                }
            },
            {
                "id": "night_vehicle_turnaround",
                "title": "Late Night Delivery Van Turnaround",
                "subtitle": "Headlights illuminate driveway, no drop-off",
                "event_type": "motion.vehicle",
                "device_id": "ring-cam-front-porch",
                "time_offset_hours": -0.05,
                "badge_color": "#64748b",
                "package_present": True,
                "scenario_type": "vehicle_motion",
                "simulated_visual_truth": {
                    "visitor_type": "vehicle",
                    "uniform_carrier": "Unmarked Delivery Van",
                    "action": "turned around in driveway",
                    "parcel_detected": True,
                    "parcel_count": 1,
                    "parcel_description": "Amazon box visible on porch under vehicle headlights",
                    "placement": "Porch floor near mat",
                    "urgency": "low"
                }
            },
            {
                "id": "theft_porch_pirate",
                "title": "Porch Pirate Theft Incident",
                "subtitle": "Unauthorized actor seizes lingering parcel and flees",
                "event_type": "motion.human",
                "device_id": "ring-cam-front-porch",
                "time_offset_hours": -0.02,
                "badge_color": "#dc2626",
                "package_present": False,
                "scenario_type": "theft_porch_pirate",
                "simulated_visual_truth": {
                    "visitor_type": "unknown",
                    "uniform_carrier": "None",
                    "action": "seized parcel from porch mat and fled rapidly (theft event)",
                    "parcel_detected": False,
                    "parcel_count": 0,
                    "parcel_description": "None remaining on porch",
                    "placement": "none",
                    "urgency": "critical"
                }
            },
            {
                "id": "adversarial_package_swap",
                "title": "Adversarial Package Swap",
                "subtitle": "Stranger substitutes delivery with empty envelope",
                "event_type": "motion.human",
                "device_id": "ring-cam-front-porch",
                "time_offset_hours": -0.01,
                "badge_color": "#b91c1c",
                "package_present": True,
                "scenario_type": "package_swap",
                "simulated_visual_truth": {
                    "visitor_type": "unknown",
                    "uniform_carrier": "None",
                    "action": "swapped delivered parcel on mat with empty flyer envelope",
                    "parcel_detected": True,
                    "parcel_count": 1,
                    "parcel_description": "Empty flyer envelope substituted in place of original parcel",
                    "placement": "Porch floor near mat",
                    "urgency": "critical"
                }
            },
            {
                "id": "adversarial_tailgating",
                "title": "Doorway Tailgating Approach",
                "subtitle": "Stranger follows directly behind resident into doorway",
                "event_type": "motion.human",
                "device_id": "ring-cam-front-porch",
                "time_offset_hours": -0.03,
                "badge_color": "#ef4444",
                "package_present": False,
                "scenario_type": "tailgating_entry",
                "simulated_visual_truth": {
                    "visitor_type": "unknown",
                    "uniform_carrier": "None",
                    "action": "tailgating detected: stranger followed resident into open door without ringing",
                    "parcel_detected": False,
                    "parcel_count": 0,
                    "parcel_description": "",
                    "placement": "none",
                    "urgency": "critical"
                }
            },
            {
                "id": "benign_false_alarm_wind",
                "title": "Benign False Alarm (Wind & Tree Shadow)",
                "subtitle": "Foliage swaying in wind triggers motion; package intact",
                "event_type": "motion.human",
                "device_id": "ring-cam-front-porch",
                "time_offset_hours": -0.04,
                "badge_color": "#10b981",
                "package_present": True,
                "scenario_type": "benign_false_alarm",
                "simulated_visual_truth": {
                    "visitor_type": "resident",
                    "uniform_carrier": "None",
                    "action": "wind motion swaying porch foliage; package undisturbed on welcome mat",
                    "parcel_detected": True,
                    "parcel_count": 1,
                    "parcel_description": "Amazon box remains untouched in original position",
                    "placement": "Left side of welcome mat",
                    "urgency": "none"
                }
            }
        ]
        return scenarios

class WebhookSimulatorClient:
    """Simulator client to fire Ring webhook events to an ingestion target."""

    def __init__(self, target_url: str, secret: Optional[str] = None):
        self.target_url = target_url
        self.secret = secret if secret is not None else get_default_secret()

    def emit_scenario(self, scenario: Dict[str, Any]) -> Dict[str, Any]:
        """Emit a scenario event to the ingestion webhook URL."""
        # Calculate simulated timestamp
        offset = scenario.get("time_offset_hours", 0)
        scenario_time = (datetime.now(timezone.utc) + timedelta(hours=offset)).isoformat()

        # Generate snapshot frame
        frame_bytes = generate_scene_image(
            title=scenario["title"],
            subtitle=scenario["subtitle"],
            timestamp_str=scenario_time[:19].replace("T", " "),
            visitor_type=scenario.get("simulated_visual_truth", {}).get("visitor_type", "visitor"),
            badge_color=scenario.get("badge_color", "#2563eb"),
            package_present=scenario.get("package_present", False),
            scenario_type=scenario.get("scenario_type", "package_delivery")
        )
        b64_frame = get_base64_scene_image(
            title=scenario["title"],
            subtitle=scenario["subtitle"],
            timestamp_str=scenario_time[:19].replace("T", " "),
            visitor_type=scenario.get("simulated_visual_truth", {}).get("visitor_type", "visitor"),
            badge_color=scenario.get("badge_color", "#2563eb"),
            package_present=scenario.get("package_present", False),
            scenario_type=scenario.get("scenario_type", "package_delivery")
        )

        # Build payload with simulated snapshot frame and ground truth metadata
        payload = create_ring_event_payload(
            event_type=scenario["event_type"],
            device_id=scenario.get("device_id", "ring-cam-front-porch"),
            created_at=scenario_time,
            attributes_override={
                "scenario_id": scenario["id"],
                "scenario_title": scenario["title"],
                "simulated_visual_truth": scenario.get("simulated_visual_truth", {})
            },
            snapshot_data_url=f"data:image/jpeg;base64,{b64_frame}"
        )

        payload_bytes = json.dumps(payload, separators=(',', ':')).encode("utf-8")
        signature = compute_ring_signature(payload_bytes, self.secret)

        headers = {
            "Content-Type": "application/vnd.api+json",
            "User-Agent": "Ring-Partner-Webhook-Dispatcher/2026.1",
            "X-Signature": signature,
            "X-Ring-Event-Type": scenario["event_type"],
            "X-Ring-Device-Id": scenario.get("device_id", "ring-cam-front-porch"),
        }

        try:
            resp = requests.post(self.target_url, data=payload_bytes, headers=headers, timeout=5.0)
            return {
                "status_code": resp.status_code,
                "response": resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text,
                "payload": payload,
                "signature": signature
            }
        except Exception as e:
            return {
                "status_code": 0,
                "error": str(e),
                "payload": payload,
                "signature": signature
            }
