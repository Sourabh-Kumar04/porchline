"""Comprehensive unit and integration test suite for Porchline."""

import json
import pytest
from fastapi.testclient import TestClient
from porchline.main import app, RING_SECRET, dynamo_store, deduplicator
from porchline.simulator.simulator_engine import (
    compute_ring_signature,
    create_ring_event_payload,
    ScenarioCatalog,
    WebhookSimulatorClient
)
from porchline.ingestion.verifier import WebhookVerifier, EventDeduplicator
from porchline.query.memory_agent import PorchlineMemoryAgent

client = TestClient(app)

def test_ring_signature_verification():
    secret = "test_secret_123"
    payload = b'{"hello":"world"}'
    sig = compute_ring_signature(payload, secret)

    verifier = WebhookVerifier(secret)
    valid, _ = verifier.verify(payload, sig)
    assert valid is True

    # Bad signature
    invalid, reason = verifier.verify(payload, "bad_signature_hex")
    assert invalid is False
    assert "mismatch" in reason

def test_event_deduplication():
    dedup = EventDeduplicator(ttl_seconds=10)
    req_id = "req_unique_abc_123"

    assert dedup.is_duplicate(req_id) is False
    # Second check should return True (it's a duplicate)
    assert dedup.is_duplicate(req_id) is True

def test_event_deduplication_dynamo_conditional_put():
    from botocore.exceptions import ClientError
    class MockDynamoTable:
        def __init__(self):
            self.items = set()
        def put_item(self, Item, ConditionExpression):
            if Item["PK"] in self.items:
                raise ClientError({"Error": {"Code": "ConditionalCheckFailedException"}}, "PutItem")
            self.items.add(Item["PK"])

    class MockStore:
        is_live = True
        table = MockDynamoTable()

    dedup = EventDeduplicator(ttl_seconds=3600, dynamo_store=MockStore())
    assert dedup.is_duplicate("req_atomic_1") is False
    assert dedup.is_duplicate("req_atomic_1") is True

def test_webhook_ingest_valid_and_fast_ack():
    # Reset store
    dynamo_store.clear()

    payload_data = create_ring_event_payload(
        event_type="package_delivery",
        request_id="req_test_pack_001",
        attributes_override={
            "scenario_title": "Test Delivery Drop",
            "simulated_visual_truth": {
                "visitor_type": "courier",
                "uniform_carrier": "Amazon",
                "action": "placed box on porch",
                "parcel_detected": True,
                "parcel_count": 1,
                "parcel_description": "Small cardboard box",
                "placement": "porch floor"
            }
        }
    )
    payload_bytes = json.dumps(payload_data, separators=(',', ':')).encode("utf-8")
    sig = compute_ring_signature(payload_bytes, RING_SECRET)

    headers = {
        "Content-Type": "application/vnd.api+json",
        "X-Signature": sig,
        "X-Ring-Event-Type": "package_delivery",
        "X-Ring-Device-Id": "ring-cam-front-porch"
    }

    res = client.post("/webhook/ring", content=payload_bytes, headers=headers)
    assert res.status_code == 200
    res_json = res.json()
    assert res_json["status"] == "acknowledged"
    assert res_json["deduplicated"] is False
    assert res_json["request_id"] == "req_test_pack_001"

    # Second submission with same request_id must be acknowledged but deduplicated
    res_dup = client.post("/webhook/ring", content=payload_bytes, headers=headers)
    assert res_dup.status_code == 200
    res_dup_json = res_dup.json()
    assert res_dup_json["deduplicated"] is True

def test_webhook_unauthorized_rejection():
    payload_bytes = b'{"data":{"attributes":{"request_id":"req_unauthorized"}}}'
    headers = {
        "Content-Type": "application/vnd.api+json",
        "X-Signature": "invalid_hmac_hash"
    }
    res = client.post("/webhook/ring", content=payload_bytes, headers=headers)
    assert res.status_code == 401

def test_simulator_scenarios_and_emit():
    # 1. Fetch scenarios
    res = client.get("/api/simulator/scenarios")
    assert res.status_code == 200
    scenarios = res.json()["scenarios"]
    assert len(scenarios) >= 5

    # 2. Emit first scenario
    first_id = scenarios[0]["id"]
    res_emit = client.post("/api/simulator/emit", json={"scenario_id": first_id})
    assert res_emit.status_code == 200
    assert "result" in res_emit.json()

def test_nl_query_engine_and_lingering_packages():
    # Seed timeline
    client.post("/api/simulator/reset")

    # Ask about courier
    res_q1 = client.post("/api/query", json={"query": "When did the courier come?"})
    assert res_q1.status_code == 200
    ans1 = res_q1.json()
    assert ans1["found"] is True
    assert "courier" in ans1["answer"].lower() or "amazon" in ans1["answer"].lower()

    # Ask about packages outside
    res_q2 = client.post("/api/query", json={"query": "Are there any packages still outside?"})
    assert res_q2.status_code == 200
    ans2 = res_q2.json()
    assert ans2["found"] is True
    assert "package" in ans2["answer"].lower()

    # Ask about animals
    res_q3 = client.post("/api/query", json={"query": "Did any animal or pet visit?"})
    assert res_q3.status_code == 200
    ans3 = res_q3.json()
    assert ans3["found"] is True
    assert "animal" in ans3["answer"].lower() or "pet" in ans3["answer"].lower()

def test_evening_digest_endpoint():
    res = client.get("/api/digest")
    assert res.status_code == 200
    data = res.json()
    assert "headline" in data
    assert "highlights" in data
    assert data["total_events_today"] > 0

def test_web_console_html_endpoint():
    res = client.get("/")
    assert res.status_code == 200
    assert "Porchline" in res.text
    assert "Ring Webhook Simulator" in res.text
    # Must have a visible MOCK/LIVE badge in the web console UI
    assert "MOCK MODE" in res.text or "LIVE BEDROCK" in res.text

def test_system_status_endpoint():
    res = client.get("/api/status")
    assert res.status_code == 200
    data = res.json()
    assert "bedrock_mode" in data
    assert data["bedrock_mode"] in ("MOCK", "LIVE")
    assert "dynamodb_mode" in data
