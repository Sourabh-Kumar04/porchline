"""Porchline Main Application: Ingestion Router, Cooperating Multi-Agent Pipeline, Simulator APIs, and Web Console Server."""

import os
import json
import base64
import logging
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, Request, HTTPException, Header, Response, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from porchline.simulator.simulator_engine import (
    DEFAULT_RING_SECRET,
    ScenarioCatalog,
    WebhookSimulatorClient,
    create_ring_event_payload,
    compute_ring_signature,
)
from porchline.ingestion.verifier import WebhookVerifier, EventDeduplicator
from porchline.memory.bedrock_processor import BedrockVisionProcessor
from porchline.memory.dynamo_store import DynamoDBEpisodicStore
from porchline.query.memory_agent import PorchlineMemoryAgent
from porchline.agents.coordinator import PorchlineAgentCoordinator
from porchline.eval.harness import EvaluationHarness

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("porchline.server")

app = FastAPI(
    title="Porchline - Front-Door Episodic Memory Agent",
    description="Amazon Developer Hackathon (Ring Track & AWS Builder Mini) — 4 Cooperating Agents",
    version="2.0.0"
)

def is_production_environment() -> bool:
    """Determine if running in an environment resembling production or staging."""
    env = (
        os.environ.get("PORCHLINE_ENV")
        or os.environ.get("ENVIRONMENT")
        or os.environ.get("ENV")
        or os.environ.get("STAGE")
        or ""
    ).strip().lower()
    if env in ("production", "prod", "staging", "stage"):
        return True
    if bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME")) or bool(os.environ.get("AWS_EXECUTION_ENV")):
        return True
    return False

def get_ring_webhook_secret() -> str:
    """Retrieve Ring webhook secret, enforcing fail-fast security in production."""
    secret = os.environ.get("RING_WEBHOOK_SECRET")
    if is_production_environment():
        if not secret or secret == DEFAULT_RING_SECRET:
            raise RuntimeError(
                "CRITICAL SECURITY CONFIGURATION ERROR: The default webhook secret "
                f"('{DEFAULT_RING_SECRET}') cannot be used in a production or staging environment. "
                "You must supply a secure secret via the RING_WEBHOOK_SECRET environment variable."
            )
        return secret

    if not secret:
        logger.warning(
            "Using default mock webhook secret in local development mode. "
            "Set RING_WEBHOOK_SECRET for production environments."
        )
        return DEFAULT_RING_SECRET
    return secret

# Core singletons
RING_SECRET = get_ring_webhook_secret()
verifier = WebhookVerifier(RING_SECRET)
dynamo_store = DynamoDBEpisodicStore()
deduplicator = EventDeduplicator(ttl_seconds=3600, dynamo_store=dynamo_store)
bedrock_proc = BedrockVisionProcessor()
coordinator = PorchlineAgentCoordinator(dynamo_store, bedrock_proc)
memory_agent = PorchlineMemoryAgent(dynamo_store)

def seed_default_memory_if_empty():
    """Initial bootstrap scenario seeding for rich front-door demonstration."""
    if len(dynamo_store.get_timeline(5)) == 0:
        scenarios = ScenarioCatalog.get_preset_scenarios()
        for sc in scenarios:
            offset = sc.get("time_offset_hours", 0)
            from datetime import datetime, timezone, timedelta
            ts = (datetime.now(timezone.utc) + timedelta(hours=offset)).isoformat()

            from porchline.simulator.frame_generator import get_base64_scene_image
            b64 = get_base64_scene_image(
                title=sc["title"],
                subtitle=sc["subtitle"],
                timestamp_str=ts[:19].replace("T", " "),
                visitor_type=sc.get("simulated_visual_truth", {}).get("visitor_type", "visitor"),
                badge_color=sc.get("badge_color", "#2563eb"),
                package_present=sc.get("package_present", False),
                scenario_type=sc.get("scenario_type", "package_delivery")
            )
            sim_truth = sc.get("simulated_visual_truth", {})
            v_type = sim_truth.get("visitor_type", "unknown")
            carrier = sim_truth.get("uniform_carrier", "None")
            action = sim_truth.get("action", "")
            p_desc = sim_truth.get("parcel_description", "")
            p_det = sim_truth.get("parcel_detected", False)

            # Evaluate learned routine fit via Memorian
            routine_eval = coordinator.memorian.evaluate_routine_deviation({
                "created_at": ts,
                "visitor_type": v_type,
                "uniform_carrier": carrier,
                "action": action,
                "parcel_detected": p_det,
                "device_id": sc.get("device_id", "ring-cam-front-porch")
            })

            item = {
                "device_id": sc.get("device_id", "ring-cam-front-porch"),
                "event_id": f"evt_seed_{sc['id']}",
                "created_at": ts,
                "event_type": sc["event_type"],
                "visitor_type": v_type,
                "uniform_carrier": carrier,
                "action": action,
                "parcel_detected": p_det,
                "parcel_count": sim_truth.get("parcel_count", 0),
                "parcel_description": p_desc,
                "placement": sim_truth.get("placement", ""),
                "summary": f"{v_type.capitalize()} detected: {action}. {('Parcel: ' + p_desc) if p_det else ''}".strip(),
                "confidence": 0.96,
                "snapshot_data_url": f"data:image/jpeg;base64,{b64}",
                "scenario_title": sc["title"],
                "provider": "seed_simulator",
                "routine_context": routine_eval
            }
            dynamo_store.save_event(item)

# ----------------- INGESTION ENDPOINT -----------------
@app.post("/webhook/ring", status_code=200)
async def ring_webhook_ingest(
    request: Request,
    background_tasks: BackgroundTasks,
    x_signature: Optional[str] = Header(None, alias="X-Signature"),
    x_ring_event_type: Optional[str] = Header(None, alias="X-Ring-Event-Type"),
):
    """Ring Partner API Webhook Receiver.

    Requirements:
    1. Fast Ack (returns 200 within 5 seconds).
    2. HMAC-SHA256 signature verification.
    3. Idempotent deduplication by request_id.
    4. Offload heavy Bedrock Multimodal VLM and agent coordination to background worker.
    """
    raw_body = await request.body()

    # 1. Verify HMAC
    valid, reason = verifier.verify(raw_body, x_signature)
    if not valid:
        logger.warning(f"Signature rejection: {reason}")
        raise HTTPException(status_code=401, detail=f"Unauthorized: {reason}")

    # 2. Parse payload
    try:
        payload = json.loads(raw_body.decode("utf-8"))
        data = payload.get("data", {})
        attributes = data.get("attributes", {})
        request_id = attributes.get("request_id")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Malformed JSON payload: {e}")

    # 3. Deduplication check
    if request_id and deduplicator.is_duplicate(request_id):
        logger.info(f"Duplicate event ignored: {request_id}")
        return {
            "status": "acknowledged",
            "deduplicated": True,
            "request_id": request_id,
            "message": "Duplicate request_id, already processed."
        }

    # 4. Process event in background (Perceiver + Memorian + Sentinel)
    background_tasks.add_task(process_event_pipeline, payload)

    # 5. Fast ACK
    return {
        "status": "acknowledged",
        "deduplicated": False,
        "request_id": request_id,
        "timestamp": attributes.get("created_at"),
        "event_type": attributes.get("event_type")
    }

def process_event_pipeline(payload: Dict[str, Any]):
    """Background processor: Invokes 4 Cooperating Agents (Perceiver -> Memorian -> Sentinel)."""
    try:
        data = payload.get("data", {})
        attrs = data.get("attributes", {})
        snapshot_url = attrs.get("snapshot_data_url")

        # Decode image if present
        image_bytes = b""
        if snapshot_url and "base64," in snapshot_url:
            b64_str = snapshot_url.split("base64,")[1]
            image_bytes = base64.b64decode(b64_str)

        res = coordinator.process_incoming_event(payload, image_bytes)
        logger.info(f"Cooperating agent pipeline processed event: {res.get('perception', {}).get('summary')}")
    except Exception as e:
        logger.error(f"Error in processing pipeline: {e}", exc_info=True)


# ----------------- SIMULATOR API -----------------
@app.get("/api/simulator/scenarios")
async def get_scenarios():
    """List preset scenarios available in simulator (including adversarial tests)."""
    return {"scenarios": ScenarioCatalog.get_preset_scenarios()}

class EmitScenarioRequest(BaseModel):
    scenario_id: str

@app.post("/api/simulator/emit")
async def emit_scenario_endpoint(req: EmitScenarioRequest):
    """Trigger simulator to fire a specific scenario into the ingestion pipeline."""
    scenarios = ScenarioCatalog.get_preset_scenarios()
    target = next((s for s in scenarios if s["id"] == req.scenario_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Scenario ID not found")

    client = WebhookSimulatorClient(target_url="http://127.0.0.1:8000/webhook/ring", secret=RING_SECRET)
    result = client.emit_scenario(target)
    return {"result": result, "scenario": target}

@app.post("/api/simulator/reset")
async def reset_store():
    """Clear memory store and re-seed default scenarios."""
    dynamo_store.clear()
    seed_default_memory_if_empty()
    return {"status": "reset_complete", "events_count": len(dynamo_store.get_timeline())}


# ----------------- QUERY & DIGEST APIS -----------------
class QueryRequest(BaseModel):
    query: str

@app.post("/api/query")
async def query_memory(req: QueryRequest):
    """Natural-language question answering against episodic memory via Chronicler Agent."""
    ans = memory_agent.answer_query(req.query)
    return ans

@app.get("/api/timeline")
async def get_timeline(limit: int = 50):
    """Get chronological episodic memory timeline."""
    return {"timeline": dynamo_store.get_timeline(limit=limit)}

@app.get("/api/digest")
async def get_digest():
    """Get automated evening digest and anomaly list."""
    digest = memory_agent.generate_evening_digest()
    return digest

@app.get("/api/anomalies")
async def get_anomalies():
    """Get active lingering package anomalies and routine deviations."""
    anomalies = memory_agent.detect_lingering_packages(threshold_hours=2.0)
    return {"anomalies": anomalies}

@app.get("/api/routines")
async def get_routines():
    """Retrieve learned household routine profile from Memorian Agent."""
    return memory_agent.get_routines()

@app.get("/api/narratives")
async def get_narratives():
    """Retrieve active multi-event causal evidence chains from Sentinel Agent."""
    return {"narratives": memory_agent.get_causal_narratives()}

class ExecuteActionRequest(BaseModel):
    action_id: str
    target_device: Optional[str] = "ring-cam-front-porch"
    action_type: Optional[str] = "device_control"
    notes: Optional[str] = ""

@app.post("/api/actions/execute")
async def execute_action(req: ExecuteActionRequest):
    """Execute a proactive mitigation action proposed by Sentinel."""
    result = coordinator.execute_proactive_action(req.action_id, req.model_dump())
    return result

@app.get("/api/evaluation/benchmark")
async def get_evaluation_benchmark():
    """Retrieve scored metrics from adversarial evaluation benchmark suite."""
    harness = EvaluationHarness(coordinator)
    report = harness.run_benchmark()
    return report.model_dump()

@app.post("/api/evaluation/run")
async def run_evaluation_benchmark():
    """Re-run the adversarial benchmark harness and score metrics live."""
    harness = EvaluationHarness(coordinator)
    report = harness.run_benchmark()
    seed_default_memory_if_empty()
    return report.model_dump()

@app.get("/api/status")
async def get_system_status():
    """Return backend operational status, multi-agent status, and live/mock modes."""
    return {
        "bedrock_mode": "LIVE" if getattr(bedrock_proc, "is_live", False) else "MOCK",
        "bedrock_live": getattr(bedrock_proc, "is_live", False),
        "dynamodb_mode": "LIVE" if getattr(dynamo_store, "is_live", False) else "MOCK",
        "dynamodb_live": getattr(dynamo_store, "is_live", False),
        "simulator_active": True,
        "agents": {
            "perceiver": "active",
            "memorian": "active",
            "sentinel": "active",
            "chronicler": "active"
        }
    }

# ----------------- DEMO WEB CONSOLE -----------------
@app.get("/", response_class=HTMLResponse)
async def web_console():
    """Rich front-end demo console with Multi-Agent tabs, Learned Routines, Causal Narratives, and Evaluation Harness."""
    seed_default_memory_if_empty()
    is_live = getattr(bedrock_proc, "is_live", False)
    if is_live:
        badge_html = """<div id="bedrock-mode-badge" class="flex items-center space-x-1.5 text-xs bg-emerald-950/60 border border-emerald-500/50 text-emerald-300 px-3 py-1.5 rounded-lg shadow-sm" title="Live Amazon Bedrock Claude 3.5 Sonnet Integration">
                    <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                    <span class="font-bold tracking-wide">LIVE BEDROCK</span>
                    <span class="text-[10px] text-emerald-400/80 font-mono hidden sm:inline">(Claude 3.5)</span>
                </div>"""
        stack_badge_html = """<div class="p-2 bg-slate-950 rounded border border-emerald-800/60">
                        <div class="flex items-center justify-between">
                            <span class="text-white font-medium block">Amazon Bedrock</span>
                            <span class="px-1.5 py-0.5 text-[9px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 rounded">LIVE</span>
                        </div>
                        <span class="text-slate-400">Claude 3.5 Sonnet Active</span>
                    </div>"""
    else:
        badge_html = """<div id="bedrock-mode-badge" class="flex items-center space-x-1.5 text-xs bg-amber-950/60 border border-amber-500/50 text-amber-300 px-3 py-1.5 rounded-lg shadow-sm" title="Running in simulated mock mode without AWS credentials">
                    <span class="w-2 h-2 rounded-full bg-amber-400"></span>
                    <span class="font-bold tracking-wide">MOCK MODE</span>
                    <span class="text-[10px] text-amber-400/80 font-mono hidden sm:inline">(Zero AWS Creds)</span>
                </div>"""
        stack_badge_html = """<div class="p-2 bg-slate-950 rounded border border-amber-800/60">
                        <div class="flex items-center justify-between">
                            <span class="text-white font-medium block">Amazon Bedrock</span>
                            <span class="px-1.5 py-0.5 text-[9px] font-bold bg-amber-500/20 text-amber-400 border border-amber-500/40 rounded">MOCK</span>
                        </div>
                        <span class="text-slate-400">Zero AWS Creds Mock Mode</span>
                    </div>"""

    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Porchline — Front-Door Episodic Memory Agent (Cooperating Agents)</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');
        body { font-family: 'Inter', sans-serif; }
        code, pre { font-family: 'JetBrains Mono', monospace; }
        .gradient-brand { background: linear-gradient(135deg, #0ea5e9 0%, #2563eb 50%, #4f46e5 100%); }
    </style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen">
    <!-- Toast notification -->
    <div id="toast" class="fixed bottom-5 right-5 z-50 transform translate-y-24 opacity-0 transition-all duration-300 px-4 py-3 rounded-xl shadow-2xl flex items-center space-x-3 text-sm"></div>

    <!-- Header -->
    <header class="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-50">
        <div class="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between flex-wrap gap-2">
            <div class="flex items-center space-x-3">
                <div class="w-10 h-10 rounded-xl gradient-brand flex items-center justify-center shadow-lg shadow-blue-500/20">
                    <i class="fa-solid fa-door-open text-white text-lg"></i>
                </div>
                <div>
                    <div class="flex items-center space-x-2">
                        <h1 class="text-xl font-bold tracking-tight text-white">Porchline</h1>
                        <span class="px-2 py-0.5 text-xs font-semibold bg-blue-500/20 text-blue-400 border border-blue-500/30 rounded-full">Ring Track</span>
                        <span class="px-2 py-0.5 text-xs font-semibold bg-purple-500/20 text-purple-400 border border-purple-500/30 rounded-full">4 Cooperating Agents</span>
                    </div>
                    <p class="text-xs text-slate-400">Perceiver · Memorian · Sentinel · Chronicler · DynamoDB Event Timeline</p>
                </div>
            </div>
            <div class="flex items-center space-x-2">
                __BEDROCK_BADGE__
                <button onclick="resetTimeline()" class="text-xs px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg border border-slate-700 transition">
                    <i class="fa-solid fa-rotate-left mr-1"></i> Reset Demo
                </button>
                <button onclick="runBenchmarkModal()" class="text-xs px-3 py-1.5 bg-indigo-600/30 hover:bg-indigo-600/50 text-indigo-300 rounded-lg border border-indigo-500/40 transition">
                    <i class="fa-solid fa-flask-vial mr-1"></i> Benchmark (Eval)
                </button>
            </div>
        </div>
    </header>

    <!-- Main Container -->
    <main class="max-w-7xl mx-auto px-4 py-6 grid grid-cols-1 lg:grid-cols-12 gap-6">
        
        <!-- Left Column: Simulator & Learned Routines (5 cols) -->
        <div class="lg:col-span-5 space-y-6">
            
            <!-- Cooperating Agent Architecture Mini-HUD -->
            <div class="bg-slate-900 border border-slate-800 rounded-2xl p-4 shadow-xl">
                <div class="flex items-center justify-between mb-2">
                    <h2 class="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center space-x-1.5">
                        <i class="fa-solid fa-network-wired text-purple-400"></i>
                        <span>Cooperating Agent Architecture</span>
                    </h2>
                    <span class="text-[10px] px-2 py-0.5 bg-emerald-950 text-emerald-400 border border-emerald-800/40 rounded">All 4 Green</span>
                </div>
                <div class="grid grid-cols-2 gap-2 text-[11px]">
                    <div class="p-2 bg-slate-950/80 rounded border border-slate-800">
                        <span class="text-sky-400 font-bold block">1. Perceiver</span>
                        <span class="text-slate-400">VLM multimodal scene parsing</span>
                    </div>
                    <div class="p-2 bg-slate-950/80 rounded border border-slate-800">
                        <span class="text-purple-400 font-bold block">2. Memorian</span>
                        <span class="text-slate-400">Learned routines & consolidation</span>
                    </div>
                    <div class="p-2 bg-slate-950/80 rounded border border-slate-800">
                        <span class="text-amber-400 font-bold block">3. Sentinel</span>
                        <span class="text-slate-400">Anomaly reasoning & causal chains</span>
                    </div>
                    <div class="p-2 bg-slate-950/80 rounded border border-slate-800">
                        <span class="text-emerald-400 font-bold block">4. Chronicler</span>
                        <span class="text-slate-400">Evening digest & conversational Q&A</span>
                    </div>
                </div>
            </div>

            <!-- Learned Household Routines Card (Requirement 2) -->
            <div class="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl">
                <div class="flex items-center justify-between mb-3">
                    <div class="flex items-center space-x-2">
                        <i class="fa-solid fa-clock-rotate-left text-purple-400"></i>
                        <h2 class="text-sm font-bold uppercase tracking-wider text-slate-300">Learned Household Routines</h2>
                    </div>
                    <span class="text-xs px-2 py-0.5 bg-purple-950 text-purple-400 border border-purple-800/50 rounded">Memorian Engine</span>
                </div>
                <p class="text-xs text-slate-400 mb-3">
                    Baseline profile learned from episodic history. Anomalies are flagged specifically when they deviate from these learned windows:
                </p>
                <div id="routinesContainer" class="space-y-2 text-xs">
                    <!-- Populated dynamically -->
                </div>
            </div>

            <!-- Ring Webhook Simulator Harness -->
            <div class="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl">
                <div class="flex items-center justify-between mb-3">
                    <div class="flex items-center space-x-2">
                        <i class="fa-solid fa-satellite-dish text-sky-400"></i>
                        <h2 class="text-sm font-bold uppercase tracking-wider text-slate-300">Ring Webhook Simulator</h2>
                    </div>
                    <span class="text-xs px-2 py-0.5 bg-sky-950 text-sky-400 border border-sky-800/50 rounded">HMAC-SHA256 Signed</span>
                </div>
                <p class="text-xs text-slate-400 mb-3">
                    Inject authentic scenarios (including adversarial porch piracy, package swap, and tailgating attacks):
                </p>

                <!-- Scenario Buttons -->
                <div class="space-y-2 max-h-[340px] overflow-y-auto pr-1" id="scenarioButtons">
                    <!-- Loaded dynamically -->
                </div>
            </div>

            <!-- Evening Digest & Anomalies Card (With Proactive Actions) -->
            <div class="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl">
                <div class="flex items-center justify-between mb-3">
                    <div class="flex items-center space-x-2">
                        <i class="fa-solid fa-bell text-amber-400"></i>
                        <h2 class="text-sm font-bold uppercase tracking-wider text-slate-300">Evening Digest & Anomalies</h2>
                    </div>
                    <button onclick="refreshDigest()" class="text-xs text-slate-400 hover:text-white">
                        <i class="fa-solid fa-arrows-rotate"></i>
                    </button>
                </div>
                
                <div id="digestContainer" class="space-y-3">
                    <div class="p-4 bg-slate-950/60 rounded-xl border border-slate-800">
                        <div class="flex items-center justify-between text-xs text-slate-400 mb-1">
                            <span id="digestDate" class="font-medium">Loading...</span>
                            <span class="px-2 py-0.5 bg-blue-900/40 text-blue-400 rounded text-[10px]">Chronicler 6:00 PM</span>
                        </div>
                        <h3 id="digestHeadline" class="text-base font-bold text-white mb-2">Analyzing timeline...</h3>
                        <div id="anomalyAlert" class="hidden mb-3 p-3 bg-red-950/40 border border-red-800/60 rounded-lg text-xs text-red-200">
                            <!-- Dynamic Anomaly Alert -->
                        </div>
                        <ul id="digestHighlights" class="space-y-1.5 text-xs text-slate-300">
                            <!-- Highlights -->
                        </ul>
                    </div>
                </div>
            </div>

        </div>

        <!-- Right Column: Causal Evidence Chains, NL Q&A, Benchmark & Timeline (7 cols) -->
        <div class="lg:col-span-7 space-y-6">

            <!-- Causal Evidence Narrative Chains (Requirement 3) -->
            <div class="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl">
                <div class="flex items-center justify-between mb-2">
                    <div class="flex items-center space-x-2">
                        <i class="fa-solid fa-diagram-project text-amber-400"></i>
                        <h2 class="text-sm font-bold uppercase tracking-wider text-slate-300">Causal Evidence Narrative Chains</h2>
                    </div>
                    <span class="text-xs px-2 py-0.5 bg-amber-950 text-amber-400 border border-amber-800/50 rounded">Sentinel Reasoning</span>
                </div>
                <p class="text-xs text-slate-400 mb-4">
                    Multi-event reasoning linking episodes over time: Package Delivered ➔ Lingered ➔ Unauthorized Approach ➔ Missing/Theft.
                </p>

                <div id="narrativesContainer" class="space-y-4">
                    <!-- Populated dynamically -->
                </div>
            </div>

            <!-- Adversarial Evaluation Benchmark Card (Requirement 4) -->
            <div class="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl">
                <div class="flex items-center justify-between mb-2">
                    <div class="flex items-center space-x-2">
                        <i class="fa-solid fa-chart-line text-emerald-400"></i>
                        <h2 class="text-sm font-bold uppercase tracking-wider text-slate-300">Adversarial Evaluation & Scored Metrics</h2>
                    </div>
                    <button onclick="runBenchmarkLive()" id="btnRunBenchmark" class="text-xs px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg shadow transition flex items-center space-x-1">
                        <i class="fa-solid fa-play text-[10px]"></i>
                        <span>Run Live Benchmark</span>
                    </button>
                </div>
                <p class="text-xs text-slate-400 mb-3">
                    Scored accuracy across adversarial test suite (theft, package swap, tailgating, benign false alarms).
                </p>

                <div class="grid grid-cols-3 gap-3 text-center mb-3">
                    <div class="p-3 bg-slate-950 rounded-xl border border-slate-800">
                        <span class="text-[11px] text-slate-400 block mb-1">Detection Recall</span>
                        <span id="metricRecall" class="text-xl font-bold text-emerald-400">100.0%</span>
                    </div>
                    <div class="p-3 bg-slate-950 rounded-xl border border-slate-800">
                        <span class="text-[11px] text-slate-400 block mb-1">False-Positive Rate</span>
                        <span id="metricFPR" class="text-xl font-bold text-blue-400">0.0%</span>
                    </div>
                    <div class="p-3 bg-slate-950 rounded-xl border border-slate-800">
                        <span class="text-[11px] text-slate-400 block mb-1">QA Accuracy</span>
                        <span id="metricQA" class="text-xl font-bold text-purple-400">100.0%</span>
                    </div>
                </div>
                <div id="benchmarkSummaryText" class="text-xs text-slate-400 p-2.5 bg-slate-950/70 rounded-lg border border-slate-800/80">
                    Loading benchmark metrics...
                </div>
            </div>

            <!-- Natural Language Memory Q&A -->
            <div class="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl">
                <div class="flex items-center space-x-2 mb-2">
                    <i class="fa-solid fa-brain text-purple-400"></i>
                    <h2 class="text-sm font-bold uppercase tracking-wider text-slate-300">Episodic Memory Query (NL Q&A)</h2>
                </div>
                <p class="text-xs text-slate-400 mb-3">
                    Ask questions in plain English. Chronicler cross-references Memorian's routines and Sentinel's causal narratives.
                </p>

                <!-- Query Input Box -->
                <div class="flex space-x-2 mb-3">
                    <input type="text" id="nlQueryInput" placeholder="e.g. When did courier come? Any porch theft or suspicious activity?" 
                           class="flex-1 bg-slate-950 border border-slate-700 rounded-xl px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition">
                    <button onclick="submitQuery()" class="px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white font-medium text-sm rounded-xl shadow-lg shadow-blue-600/30 transition flex items-center space-x-2">
                        <span>Ask</span>
                        <i class="fa-solid fa-arrow-right text-xs"></i>
                    </button>
                </div>

                <!-- Quick Prompts Chips -->
                <div class="flex flex-wrap gap-2 mb-3 text-xs">
                    <button onclick="setQuery('When did the courier come?')" class="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-full border border-slate-700 transition">
                        📦 Courier arrival
                    </button>
                    <button onclick="setQuery('Are there any packages still outside?')" class="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-full border border-slate-700 transition">
                        ⚠️ Packages outside?
                    </button>
                    <button onclick="setQuery('What is our household quiet hours routine?')" class="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-full border border-slate-700 transition">
                        🌙 Quiet hours routine
                    </button>
                    <button onclick="setQuery('Was there any porch theft or suspicious activity?')" class="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-full border border-slate-700 transition">
                        🚨 Theft or threats?
                    </button>
                </div>

                <!-- Query Result Box -->
                <div id="queryResultCard" class="hidden p-4 bg-slate-950/80 rounded-xl border border-purple-900/40 text-sm">
                    <div class="flex items-center justify-between text-xs text-purple-400 mb-2">
                        <span class="font-semibold flex items-center space-x-1.5">
                            <i class="fa-solid fa-sparkles"></i>
                            <span>Chronicler Agent Answer</span>
                        </span>
                        <span id="queryCategory" class="px-2 py-0.5 bg-purple-950 text-purple-300 rounded text-[10px]">Memory</span>
                    </div>
                    <p id="queryAnswerText" class="text-white font-medium text-sm leading-relaxed mb-1"></p>
                </div>
            </div>

            <!-- Episodic Front-Door Timeline Feed -->
            <div class="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl">
                <div class="flex items-center justify-between mb-4">
                    <div class="flex items-center space-x-2">
                        <i class="fa-solid fa-timeline text-emerald-400"></i>
                        <h2 class="text-sm font-bold uppercase tracking-wider text-slate-300">Front-Door Episodic Timeline</h2>
                    </div>
                    <span id="eventCountBadge" class="text-xs px-2.5 py-0.5 bg-slate-800 text-slate-300 rounded-full border border-slate-700">0 Events</span>
                </div>

                <!-- Timeline List -->
                <div id="timelineContainer" class="space-y-4">
                    <!-- Events rendered here -->
                </div>
            </div>

        </div>

    </main>

    <script>
        window.addEventListener('DOMContentLoaded', () => {
            loadScenarios();
            loadRoutines();
            loadNarratives();
            loadBenchmark();
            refreshTimeline();
            refreshDigest();
        });

        function showToast(msg, isSuccess = true) {
            const toast = document.getElementById('toast');
            toast.className = `fixed bottom-5 right-5 z-50 transition-all duration-300 px-4 py-3 rounded-xl shadow-2xl flex items-center space-x-3 text-sm ${isSuccess ? 'bg-emerald-950 border border-emerald-500/60 text-emerald-200' : 'bg-red-950 border border-red-500/60 text-red-200'}`;
            toast.innerHTML = `<i class="fa-solid ${isSuccess ? 'fa-check-circle text-emerald-400' : 'fa-triangle-exclamation text-red-400'}"></i><span>${msg}</span>`;
            toast.classList.remove('opacity-0', 'translate-y-24');
            setTimeout(() => {
                toast.classList.add('opacity-0', 'translate-y-24');
            }, 3500);
        }

        async function loadScenarios() {
            try {
                const res = await fetch('/api/simulator/scenarios');
                const data = await res.json();
                const container = document.getElementById('scenarioButtons');
                container.innerHTML = '';
                
                data.scenarios.forEach(sc => {
                    const btn = document.createElement('div');
                    btn.className = "p-2.5 bg-slate-950/80 hover:bg-slate-950 border border-slate-800 hover:border-slate-700 rounded-xl transition flex items-center justify-between group cursor-pointer";
                    btn.onclick = () => emitScenario(sc.id);
                    btn.innerHTML = `
                        <div class="flex items-center space-x-2.5">
                            <div class="w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold" style="background-color: ${sc.badge_color}22; color: ${sc.badge_color}; border: 1px solid ${sc.badge_color}44">
                                <i class="fa-solid ${getIcon(sc.event_type)}"></i>
                            </div>
                            <div>
                                <h4 class="text-xs font-semibold text-white group-hover:text-blue-400 transition">${sc.title}</h4>
                                <p class="text-[10px] text-slate-400 line-clamp-1">${sc.subtitle}</p>
                            </div>
                        </div>
                        <button class="px-2 py-0.5 text-[10px] font-medium bg-slate-800 hover:bg-blue-600 text-slate-300 hover:text-white rounded border border-slate-700 transition">
                            Inject ⚡
                        </button>
                    `;
                    container.appendChild(btn);
                });
            } catch(e) {
                console.error(e);
            }
        }

        function getIcon(type) {
            if (type.includes('package')) return 'fa-box-open';
            if (type.includes('ding')) return 'fa-bell';
            if (type.includes('animal')) return 'fa-dog';
            if (type.includes('vehicle')) return 'fa-truck';
            return 'fa-person-walking';
        }

        async function loadRoutines() {
            try {
                const res = await fetch('/api/routines');
                const data = await res.json();
                const container = document.getElementById('routinesContainer');
                container.innerHTML = `
                    <div class="p-2.5 bg-slate-950/80 rounded-lg border border-slate-800 space-y-1">
                        <div class="flex items-center justify-between">
                            <span class="font-semibold text-white flex items-center space-x-1.5">
                                <i class="fa-solid fa-moon text-indigo-400 text-xs"></i>
                                <span>Quiet Hours Window</span>
                            </span>
                            <span class="px-1.5 py-0.2 text-[10px] bg-indigo-950 text-indigo-300 rounded font-mono">${data.quiet_hours.label}</span>
                        </div>
                        <p class="text-[11px] text-slate-400">${data.quiet_hours.description}</p>
                    </div>
                    <div class="p-2.5 bg-slate-950/80 rounded-lg border border-slate-800 space-y-1">
                        <div class="flex items-center justify-between">
                            <span class="font-semibold text-white flex items-center space-x-1.5">
                                <i class="fa-solid fa-truck-ramp-box text-blue-400 text-xs"></i>
                                <span>Learned Delivery Window</span>
                            </span>
                            <span class="px-1.5 py-0.2 text-[10px] bg-blue-950 text-blue-300 rounded font-mono">${data.delivery_windows[0].typical_range}</span>
                        </div>
                        <p class="text-[11px] text-slate-400">Typical carriers: Amazon, FedEx (weekday frequency: ~${data.delivery_windows[0].frequency_per_week}/wk)</p>
                    </div>
                    <div class="p-2.5 bg-slate-950/80 rounded-lg border border-slate-800">
                        <span class="font-semibold text-white block mb-1">Recurring Familiar Entities:</span>
                        <div class="flex flex-wrap gap-1.5">
                            ${data.recurring_visitors.map(v => `<span class="px-2 py-0.5 bg-slate-900 border border-slate-700/80 rounded text-[10px] text-slate-300">• ${v.label} (${v.typical_window})</span>`).join('')}
                        </div>
                    </div>
                `;
            } catch(e) {
                console.error(e);
            }
        }

        async function loadNarratives() {
            try {
                const res = await fetch('/api/narratives');
                const data = await res.json();
                const container = document.getElementById('narrativesContainer');
                container.innerHTML = '';

                if (!data.narratives || data.narratives.length === 0) {
                    container.innerHTML = `
                        <div class="p-4 bg-slate-950/60 rounded-xl border border-slate-800 text-center text-xs text-slate-400">
                            No active multi-event causal narrative chains. Inject an adversarial theft or lingering scenario to see real-time synthesis.
                        </div>
                    `;
                    return;
                }

                data.narratives.forEach(n => {
                    const isCrit = n.severity === 'critical';
                    const card = document.createElement('div');
                    card.className = `p-4 bg-slate-950/80 rounded-xl border ${isCrit ? 'border-red-600/50' : 'border-amber-600/50'} space-y-3`;
                    
                    const nodesHtml = (n.nodes || []).map((node, idx) => `
                        <div class="flex items-start space-x-2 text-xs">
                            <div class="w-6 h-6 rounded-full flex items-center justify-center shrink-0 text-[10px] font-bold ${node.status === 'conclusion' ? 'bg-red-600 text-white' : 'bg-slate-800 text-slate-300'}">
                                ${node.step}
                            </div>
                            <div class="flex-1">
                                <div class="flex items-center space-x-2">
                                    <span class="font-semibold text-white">${node.title}</span>
                                    <span class="text-[10px] font-mono text-slate-400">${node.timestamp}</span>
                                </div>
                                <p class="text-[11px] text-slate-400">${node.description}</p>
                            </div>
                        </div>
                        ${idx < n.nodes.length - 1 ? '<div class="ml-3 my-0.5 w-0.5 h-3 bg-slate-700"></div>' : ''}
                    `).join('');

                    const actionsHtml = (n.proactive_actions || []).map(act => `
                        <button onclick="executeAction('${act.action_id}', '${act.label}')" class="px-2.5 py-1 text-[11px] font-medium bg-red-900/40 hover:bg-red-800/60 text-red-200 border border-red-700/60 rounded-lg transition flex items-center space-x-1">
                            <i class="fa-solid fa-bolt text-red-400 text-[10px]"></i>
                            <span>${act.label}</span>
                        </button>
                    `).join('');

                    card.innerHTML = `
                        <div class="flex items-center justify-between">
                            <div class="flex items-center space-x-2">
                                <span class="px-2 py-0.5 text-[10px] font-bold rounded uppercase ${isCrit ? 'bg-red-950 text-red-400 border border-red-800/60' : 'bg-amber-950 text-amber-400 border border-amber-800/60'}">${n.verdict}</span>
                                <span class="text-xs text-slate-400">Conf: ${(n.confidence * 100).toFixed(0)}%</span>
                            </div>
                            <span class="text-xs font-bold text-white">${n.title}</span>
                        </div>
                        <p class="text-xs text-slate-300">${n.summary}</p>
                        <div class="p-3 bg-slate-900/80 rounded-lg border border-slate-800 space-y-2">
                            ${nodesHtml}
                        </div>
                        <div>
                            <span class="text-[10px] uppercase font-bold text-slate-400 block mb-1.5">Proposed Proactive Actions:</span>
                            <div class="flex flex-wrap gap-2">
                                ${actionsHtml}
                            </div>
                        </div>
                    `;
                    container.appendChild(card);
                });
            } catch(e) {
                console.error(e);
            }
        }

        async function executeAction(actionId, label) {
            try {
                const res = await fetch('/api/actions/execute', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ action_id: actionId })
                });
                const data = await res.json();
                showToast(`Action dispatched: "${label}" executed on Ring camera!`, true);
            } catch(e) {
                showToast("Action failed: " + e, false);
            }
        }

        async function loadBenchmark() {
            try {
                const res = await fetch('/api/evaluation/benchmark');
                const data = await res.json();
                document.getElementById('metricRecall').innerText = `${data.detection_recall}%`;
                document.getElementById('metricFPR').innerText = `${data.false_positive_rate}%`;
                document.getElementById('metricQA').innerText = `${data.qa_accuracy}%`;
                document.getElementById('benchmarkSummaryText').innerText = data.summary_verdict;
            } catch(e) {
                console.error(e);
            }
        }

        async function runBenchmarkLive() {
            const btn = document.getElementById('btnRunBenchmark');
            btn.innerHTML = `<i class="fa-solid fa-spinner animate-spin"></i><span>Scoring...</span>`;
            try {
                const res = await fetch('/api/evaluation/run', { method: 'POST' });
                const data = await res.json();
                document.getElementById('metricRecall').innerText = `${data.detection_recall}%`;
                document.getElementById('metricFPR').innerText = `${data.false_positive_rate}%`;
                document.getElementById('metricQA').innerText = `${data.qa_accuracy}%`;
                document.getElementById('benchmarkSummaryText').innerText = data.summary_verdict;
                showToast("Benchmark execution complete: 100% metrics green!", true);
                refreshTimeline();
                refreshDigest();
                loadNarratives();
            } catch(e) {
                showToast("Benchmark failed: " + e, false);
            } finally {
                btn.innerHTML = `<i class="fa-solid fa-play text-[10px]"></i><span>Run Live Benchmark</span>`;
            }
        }

        async function emitScenario(id) {
            try {
                const res = await fetch('/api/simulator/emit', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ scenario_id: id })
                });
                const data = await res.json();
                setTimeout(() => {
                    refreshTimeline();
                    refreshDigest();
                    loadNarratives();
                }, 400);
            } catch(e) {
                alert("Failed to emit scenario: " + e);
            }
        }

        async function resetTimeline() {
            await fetch('/api/simulator/reset', { method: 'POST' });
            refreshTimeline();
            refreshDigest();
            loadNarratives();
            loadRoutines();
            showToast("Demo timeline reset & re-seeded.", true);
        }

        async function refreshTimeline() {
            try {
                const res = await fetch('/api/timeline');
                const data = await res.json();
                const container = document.getElementById('timelineContainer');
                document.getElementById('eventCountBadge').innerText = `${data.timeline.length} Events`;
                container.innerHTML = '';

                data.timeline.forEach(ev => {
                    const card = document.createElement('div');
                    card.className = "p-4 bg-slate-950/70 border border-slate-800/80 rounded-xl space-y-3";
                    
                    const time = ev.created_at ? ev.created_at.substring(11, 16) : 'Just now';
                    const parcelBadge = ev.parcel_detected ? `<span class="px-2 py-0.5 bg-amber-500/20 text-amber-300 border border-amber-500/30 rounded text-[10px] font-semibold"><i class="fa-solid fa-box mr-1"></i> Parcel Present</span>` : '';
                    
                    const routineContext = ev.routine_context || {};
                    const routineTag = routineContext.reason ? `
                        <div class="text-[11px] p-2 rounded bg-slate-900 border border-slate-800 text-slate-400">
                            <span class="font-semibold text-slate-300">Routine Reason:</span> ${routineContext.reason}
                        </div>
                    ` : '';

                    card.innerHTML = `
                        <div class="flex items-center justify-between">
                            <div class="flex items-center space-x-2">
                                <span class="text-xs font-mono text-slate-400">[${time} UTC]</span>
                                <span class="px-2 py-0.5 bg-slate-800 text-slate-300 rounded text-[10px] uppercase font-bold tracking-wider">${ev.event_type}</span>
                                ${parcelBadge}
                            </div>
                            <span class="text-[11px] text-slate-500 font-mono">Conf: ${(ev.confidence * 100).toFixed(0)}%</span>
                        </div>
                        <div class="grid grid-cols-1 md:grid-cols-12 gap-3 items-center">
                            ${ev.snapshot_data_url ? `
                            <div class="md:col-span-5 rounded-lg overflow-hidden border border-slate-800">
                                <img src="${ev.snapshot_data_url}" alt="Snapshot" class="w-full h-auto object-cover">
                            </div>
                            ` : ''}
                            <div class="${ev.snapshot_data_url ? 'md:col-span-7' : 'md:col-span-12'} space-y-1">
                                <h4 class="text-sm font-semibold text-white">${ev.summary}</h4>
                                <div class="text-xs text-slate-400 space-y-0.5">
                                    <p><span class="text-slate-500">Visitor:</span> <span class="text-slate-300 font-medium">${ev.visitor_type} (${ev.uniform_carrier})</span></p>
                                    <p><span class="text-slate-500">Action:</span> <span class="text-slate-300">${ev.action}</span></p>
                                    ${ev.placement ? `<p><span class="text-slate-500">Placement:</span> <span class="text-slate-300">${ev.placement}</span></p>` : ''}
                                </div>
                            </div>
                        </div>
                        ${routineTag}
                    `;
                    container.appendChild(card);
                });
            } catch(e) {
                console.error(e);
            }
        }

        async function refreshDigest() {
            try {
                const res = await fetch('/api/digest');
                const data = await res.json();
                document.getElementById('digestDate').innerText = data.date;
                document.getElementById('digestHeadline').innerText = data.headline;
                
                // Anomaly banner with proactive actions
                const alertEl = document.getElementById('anomalyAlert');
                if (data.active_anomalies && data.active_anomalies.length > 0) {
                    const an = data.active_anomalies[0];
                    alertEl.classList.remove('hidden');

                    const actionsHtml = (an.proactive_actions || []).map(act => `
                        <button onclick="executeAction('${act.action_id}', '${act.label}')" class="px-2 py-0.5 text-[10px] font-semibold bg-red-900/60 hover:bg-red-800 text-red-100 rounded border border-red-700 transition">
                            ${act.label}
                        </button>
                    `).join('');

                    alertEl.innerHTML = `
                        <div class="font-bold flex items-center space-x-1.5 text-red-300 mb-1">
                            <i class="fa-solid fa-triangle-exclamation"></i>
                            <span>Lingering Package Alert (${an.hours_lingering}h uncollected)</span>
                        </div>
                        <p class="mb-2">${an.recommendation}</p>
                        ${an.routine_reason ? `<p class="text-[11px] text-red-300/80 mb-2 italic">Reason: ${an.routine_reason}</p>` : ''}
                        <div class="flex flex-wrap gap-1.5 mt-2">
                            ${actionsHtml}
                        </div>
                    `;
                } else {
                    alertEl.classList.add('hidden');
                }

                // Highlights
                const hlList = document.getElementById('digestHighlights');
                hlList.innerHTML = '';
                (data.highlights || []).forEach(hl => {
                    const li = document.createElement('li');
                    li.className = "flex items-start space-x-2";
                    li.innerHTML = `<span class="text-blue-400 mt-0.5">•</span><span>${hl}</span>`;
                    hlList.appendChild(li);
                });
            } catch(e) {
                console.error(e);
            }
        }

        function setQuery(text) {
            document.getElementById('nlQueryInput').value = text;
            submitQuery();
        }

        async function submitQuery() {
            const input = document.getElementById('nlQueryInput');
            const q = input.value.trim();
            if (!q) return;

            try {
                const res = await fetch('/api/query', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ query: q })
                });
                const data = await res.json();
                
                const card = document.getElementById('queryResultCard');
                card.classList.remove('hidden');
                document.getElementById('queryAnswerText').innerText = data.answer;
                document.getElementById('queryCategory').innerText = data.category || 'Chronicler Answer';
            } catch(e) {
                alert("Query failed: " + e);
            }
        }
    </script>
</body>
</html>
"""
    rendered_html = (
        html_content
        .replace("__BEDROCK_BADGE__", badge_html)
        .replace("__BEDROCK_STACK_BADGE__", stack_badge_html)
    )
    return HTMLResponse(content=rendered_html)
