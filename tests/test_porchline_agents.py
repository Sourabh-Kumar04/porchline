"""Unit and integration tests for Porchline's 4 Cooperating Agent Architecture:
- PerceiverAgent (multimodal VLM perception)
- MemorianAgent (episodic-to-semantic consolidation & learned routines)
- SentinelAgent (anomaly reasoning & causal narratives)
- ChroniclerAgent (daily digest & routine-aware NL Q&A)
- PorchlineAgentCoordinator (orchestration over DynamoDB timeline)
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from porchline.main import app, dynamo_store, coordinator, memory_agent
from porchline.agents.perceiver import PerceiverAgent
from porchline.agents.memorian import MemorianAgent, HouseholdRoutineProfile
from porchline.agents.sentinel import SentinelAgent
from porchline.agents.chronicler import ChroniclerAgent
from porchline.agents.coordinator import PorchlineAgentCoordinator
from porchline.memory.dynamo_store import DynamoDBEpisodicStore

client = TestClient(app)


def test_perceiver_agent_frame_analysis():
    """Verify Perceiver produces structured scene perception envelope."""
    perceiver = PerceiverAgent()
    meta = {
        "event_type": "package_delivery",
        "device_id": "ring-cam-test",
        "simulated_visual_truth": {
            "visitor_type": "courier",
            "uniform_carrier": "Amazon",
            "action": "placed box on mat",
            "parcel_detected": True,
            "parcel_count": 1,
            "parcel_description": "Small brown box",
            "placement": "front mat"
        }
    }
    result = perceiver.perceive(b"", meta)
    assert result["agent"] == "Perceiver"
    assert result["visitor_type"] == "courier"
    assert result["uniform_carrier"] == "Amazon"
    assert result["parcel_detected"] is True
    assert result["confidence"] > 0.9


def test_memorian_learned_routines_and_deviation():
    """Verify Memorian constructs routine profiles and detects learned deviations."""
    store = DynamoDBEpisodicStore()
    memorian = MemorianAgent(store)

    profile = memorian.get_or_build_profile("ring-cam-test")
    assert profile.quiet_hours["start_hour"] == 22
    assert profile.quiet_hours["end_hour"] == 6
    assert len(profile.delivery_windows) > 0
    assert len(profile.recurring_visitors) > 0

    # 1. Routine delivery at 2:00 PM (14:00 UTC) matches routine
    event_2pm = {
        "created_at": "2026-10-08T14:00:00+00:00",
        "visitor_type": "courier",
        "uniform_carrier": "Amazon",
        "action": "delivered parcel",
        "parcel_detected": True
    }
    eval_2pm = memorian.evaluate_routine_deviation(event_2pm, profile)
    assert eval_2pm["is_routine_match"] is True
    assert "matches" in eval_2pm["reason"].lower()

    # 2. Motion at 2:00 AM (quiet hours) deviates from routine
    event_2am = {
        "created_at": "2026-10-08T02:00:00+00:00",
        "visitor_type": "unknown",
        "action": "motion near doorway",
        "parcel_detected": False
    }
    eval_2am = memorian.evaluate_routine_deviation(event_2am, profile)
    assert eval_2am["is_routine_match"] is False
    assert eval_2am["deviation_level"] == "high"
    assert "quiet hours" in eval_2am["reason"].lower()


def test_sentinel_causal_narrative_theft_chain():
    """Verify Sentinel connects separate events into a causal theft narrative."""
    store = DynamoDBEpisodicStore()
    memorian = MemorianAgent(store)
    sentinel = SentinelAgent(store, memorian)

    t0 = (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat()
    t1 = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()

    # Event 1: Courier delivers
    store.save_event({
        "device_id": "ring-cam-front-porch",
        "event_id": "evt_del_1",
        "created_at": t0,
        "event_type": "package_delivery",
        "visitor_type": "courier",
        "uniform_carrier": "Amazon",
        "action": "deposited package on porch",
        "parcel_detected": True,
        "summary": "Amazon courier dropped off box."
    })

    # Event 2: Unknown person steals package
    store.save_event({
        "device_id": "ring-cam-front-porch",
        "event_id": "evt_theft_1",
        "created_at": t1,
        "event_type": "motion.human",
        "visitor_type": "unknown",
        "action": "stole package from porch mat and fled rapidly (theft event)",
        "parcel_detected": False,
        "summary": "Stranger stole parcel from mat."
    })

    analysis = sentinel.analyze_timeline()
    narratives = analysis["narratives"]
    assert len(narratives) > 0
    theft_narrative = next((n for n in narratives if n["narrative_type"] == "package_theft"), None)
    assert theft_narrative is not None
    assert theft_narrative["severity"] == "critical"
    assert len(theft_narrative["nodes"]) >= 2
    assert len(theft_narrative["proactive_actions"]) > 0


def test_chronicler_routine_aware_nl_qa_and_digest():
    """Verify Chronicler answers queries with learned routine and causal context."""
    store = DynamoDBEpisodicStore()
    memorian = MemorianAgent(store)
    sentinel = SentinelAgent(store, memorian)
    chronicler = ChroniclerAgent(store, memorian, sentinel)

    # Ask about routine schedule
    res_routine = chronicler.answer_query("What is our quiet hours schedule?")
    assert res_routine["found"] is True
    assert "quiet hours" in res_routine["answer"].lower()

    # Digest generation
    digest = chronicler.generate_evening_digest()
    assert "headline" in digest
    assert "date" in digest


def test_coordinator_and_proactive_action_execution():
    """Verify Coordinator coordinates all agents and executes proactive mitigations."""
    store = DynamoDBEpisodicStore()
    coord = PorchlineAgentCoordinator(store)

    payload = {
        "data": {
            "id": "evt_coord_01",
            "attributes": {
                "device_id": "ring-cam-front-porch",
                "event_type": "package_delivery",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "simulated_visual_truth": {
                    "visitor_type": "courier",
                    "uniform_carrier": "Amazon",
                    "action": "delivered parcel",
                    "parcel_detected": True
                }
            }
        }
    }
    result = coord.process_incoming_event(payload)
    assert result["perception"]["visitor_type"] == "courier"
    assert "routine_eval" in result

    # Execute proactive action
    action_res = coord.execute_proactive_action("act_alexa_announce", {"volume": 8})
    assert action_res["status"] == "success"
    assert action_res["action_id"] == "act_alexa_announce"


def test_api_endpoints_routines_and_narratives():
    """Test /api/routines, /api/narratives, and /api/actions/execute endpoints."""
    # Reset store with default seeds
    client.post("/api/simulator/reset")

    # 1. Routines
    res_r = client.get("/api/routines")
    assert res_r.status_code == 200
    r_data = res_r.json()
    assert "quiet_hours" in r_data
    assert "delivery_windows" in r_data
    assert "recurring_visitors" in r_data

    # 2. Narratives
    res_n = client.get("/api/narratives")
    assert res_n.status_code == 200
    n_data = res_n.json()
    assert "narratives" in n_data

    # 3. Action execution
    res_act = client.post("/api/actions/execute", json={
        "action_id": "act_push_notify",
        "target_device": "ring-cam-front-porch"
    })
    assert res_act.status_code == 200
    assert res_act.json()["status"] == "success"


def test_sentinel_package_swap_and_tailgating_chains():
    """Verify Sentinel correctly builds causal chains for package swaps and tailgating."""
    store = DynamoDBEpisodicStore()
    memorian = MemorianAgent(store)
    sentinel = SentinelAgent(store, memorian)

    t0 = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    t1 = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()

    # Delivery + Swap events
    store.save_event({
        "device_id": "ring-cam-front-porch",
        "event_id": "evt_swap_del",
        "created_at": t0,
        "event_type": "package_delivery",
        "visitor_type": "courier",
        "uniform_carrier": "Amazon",
        "action": "dropped package on porch",
        "parcel_detected": True,
        "summary": "Amazon courier delivered package."
    })
    store.save_event({
        "device_id": "ring-cam-front-porch",
        "event_id": "evt_swap_act",
        "created_at": t1,
        "event_type": "motion.human",
        "visitor_type": "unknown",
        "action": "swapped parcel on mat with empty flyer envelope",
        "parcel_detected": True,
        "summary": "Unknown actor substituted parcel with flyer."
    })

    analysis = sentinel.analyze_timeline()
    narratives = analysis["narratives"]
    swap_narrative = next((n for n in narratives if n["narrative_type"] == "package_swap"), None)
    assert swap_narrative is not None
    assert swap_narrative["severity"] == "critical"
    assert "SWAP" in swap_narrative["verdict"]

    # Tailgating event
    store.clear()
    store.save_event({
        "device_id": "ring-cam-front-porch",
        "event_id": "evt_tg_act",
        "created_at": t1,
        "event_type": "motion.human",
        "visitor_type": "unknown",
        "action": "tailgating detected: stranger followed resident into open door without ringing",
        "parcel_detected": False,
        "summary": "Stranger slipped through doorway behind resident."
    })
    analysis_tg = sentinel.analyze_timeline()
    tg_narrative = next((n for n in analysis_tg["narratives"] if n["narrative_type"] == "tailgating"), None)
    assert tg_narrative is not None
    assert tg_narrative["severity"] == "critical"
