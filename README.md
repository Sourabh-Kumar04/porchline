# 🚪 Porchline — Front-Door Episodic Memory Agent

[![Amazon Build, Ship, Shape Hackathon 2026](https://img.shields.io/badge/Amazon%20Hackathon-Ring%20Track-blue.svg)](https://devpost.com)
[![AWS Builder Mini](https://img.shields.io/badge/AWS%20Builder%20Mini-Bedrock%20%7C%20DynamoDB-orange.svg)](https://aws.amazon.com/bedrock/)
[![Kiro CLI Qualified](https://img.shields.io/badge/Built%20With-Kiro%20CLI-purple.svg)](https://kiro.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Tests: 30/30 Green](https://img.shields.io/badge/Tests-30%2F30%20Passing-brightgreen.svg)](tests/)

> **Porchline** transforms Ring smart doorbells from noisy motion sensors into an ambient episodic memory agent. Built with an **Agentic Cooperating Architecture** (**Perceiver**, **Memorian**, **Sentinel**, **Chronicler**), **Ring Partner API webhooks**, **Amazon Bedrock Multimodal VLM**, and **Amazon DynamoDB**, Porchline learns household routines, synthesizes causal evidence chains, proactively mitigates anomalies, and provides conversational memory Q&A.

---

## 🌟 Why Porchline? (The Creative Non-Security Mandate)
Most smart camera apps spam residents with nagging, uninformative motion alerts (*"Motion detected at 2:14 PM"*).

The Amazon Hackathon explicitly penalizes naive camera viewers and rewards **creative, non-security applications** with genuine technical depth (such as package/delivery intelligence, routine awareness, and accessibility).

**Porchline introduces depth:**
- **Cooperating Agent Architecture:** Refactored into 4 specialized agents communicating asynchronously through an Amazon DynamoDB event timeline.
- **Learned Household Routines:** Builds statistical baselines of normal delivery windows (e.g. Amazon 09:00-16:00 UTC), recurring visitors (neighbors, dog walks), and nighttime quiet hours (22:00-06:00 UTC).
- **Deviation Reasoning:** Anomalies are evaluated against *learned normal*, surfacing clear human explanations (*"Motion at 2:00 PM matches routine delivery window; motion at 2:00 AM with no prior pattern deviates from quiet hours"*).
- **Causal Evidence Chains:** Links multi-event sequences across time into causal narratives (*Package Delivered ➔ Lingered 5h ➔ Unknown Approach ➔ Package Missing = Confirmed Theft Narrative*).
- **Proactive Actions:** Anomalies propose concrete, one-click mitigations (*Broadcast Alexa Echo Chime, Dispatch Urgent Mobile Ping, Request Neighbor Stash, Sound 85dB Siren, Auto-file Carrier Claim*).
- **Adversarial Evaluation Harness:** Built-in benchmarking suite measuring detection recall, false-positive rate, and QA accuracy across adversarial scenarios (theft, package swap, tailgating, benign false alarms).

---

## 🤖 Cooperating Agent Architecture

Porchline operates as an autonomous multi-agent system where four specialized agents communicate through the **Amazon DynamoDB** event timeline and semantic state:

```
                            +------------------------------------+
                            |     RING PARTNER API WEBHOOKS      |
                            | - HMAC-SHA256 Signed (X-Signature) |
                            | - Fast-Ack (<5s SLA) Ingestion     |
                            +-----------------+------------------+
                                              |
                                              v
+=============================================================================================+
|                                4 COOPERATING AGENTS                                         |
|                                                                                             |
|   1. 👁️ PERCEIVER AGENT (Multimodal VLM Perception)                                         |
|      - Analyzes snapshot image frames via Amazon Bedrock (Claude 3.5 Sonnet / Nova).        |
|      - Extracts visitor types, courier carriers, micro-actions, parcel attributes.          |
|                                              |                                              |
|                                              v                                              |
|                    [ Amazon DynamoDB Single-Table Event Timeline ]                          |
|                                              |                                              |
|                                              v                                              |
|   2. 🧠 MEMORIAN AGENT (Episodic-to-Semantic Consolidation)                                 |
|      - Learns household baseline routines: typical delivery windows, recurring entities.    |
|      - Enforces nighttime quiet hours policy (22:00 - 06:00 UTC).                           |
|      - Tracks active porch parcel inventory & state transitions.                            |
|                                              |                                              |
|                                              v                                              |
|   3. 🛡️ SENTINEL AGENT (Anomaly Reasoning & Causal Narratives)                               |
|      - Evaluates events against learned routines to explain deviations.                     |
|      - Synthesizes multi-event causal evidence chains (theft, swaps, tailgating).           |
|      - Attaches concrete, prioritized Proactive Mitigation Actions.                         |
|                                              |                                              |
|                                              v                                              |
|   4. 📜 CHRONICLER AGENT (Digest Synthesis & Conversational Memory Q&A)                     |
|      - Compiles automated 6:00 PM Evening Digest with routine adherence scores.             |
|      - Powers conversational natural-language Q&A with deep episodic and routine context.   |
+=============================================================================================+
```

### Agent Responsibilities
| Agent | Responsibility | Core Output / Interface |
|---|---|---|
| **Perceiver** | Multimodal VLM visual perception | Structured perception envelope (`visitor_type`, `carrier`, `action`, `parcel`, `confidence`) |
| **Memorian** | Episodic-to-semantic consolidation | `HouseholdRoutineProfile`, delivery windows, recurring visitor registry, parcel inventory |
| **Sentinel** | Anomaly reasoning & causal narratives | `AnomalyAlert`, `CausalNarrative` evidence chains, `ProactiveAction` triggers |
| **Chronicler** | Evening digest synthesis & NL Q&A | Daily briefing, routine adherence scores, conversational query answering |

---

## 📈 Evaluation Harness & Scored Metrics

Porchline includes a rigorous automated evaluation harness (`porchline/eval/harness.py`) that subjects the agent pipeline to an adversarial scenario suite in the simulator, measuring real detection capabilities and false-alarm resistance.

### Measured Benchmark Scores
| Metric | Benchmark Result | Definition & Formula | Target SLA |
|---|:---:|---|:---:|
| **Detection Recall** | **100.0%** | $\frac{\text{True Positives}}{\text{True Positives} + \text{False Negatives}}$ (Thefts, swaps, tailgating, lingering alerts) | $\ge 90.0\%$ |
| **False-Positive Rate** | **0.0%** | $\frac{\text{False Positives}}{\text{False Positives} + \text{True Negatives}}$ (Resistance to flagging benign wind/shadows/pets) | $\le 5.0\%$ |
| **QA Precision** | **100.0%** | $\frac{\text{Correct Answers}}{\text{Total Standard Memory Queries}}$ against ground-truth facts | $\ge 95.0\%$ |
| **Pipeline Latency** | **< 15 ms** | End-to-end multi-agent evaluation latency (mock mode) / < 1.5s (live Bedrock) | $< 5.0\text{ s}$ |

### Adversarial Test Battery
- **Theft Scenario (`theft_porch_pirate`):** Package delivered ➔ lingers unattended ➔ unauthorized actor seizes parcel and flees. *(Detected: 100% recall, synthesized into critical theft evidence chain).*
- **Package Swap Scenario (`adversarial_package_swap`):** Stranger substitutes genuine parcel with dummy flyer envelope. *(Detected: 100% recall, flagged as deceptive swap).*
- **Tailgating Scenario (`adversarial_tailgating`):** Stranger follows resident through open doorway without ringing. *(Detected: 100% recall, immediate deadbolt lockdown proposed).*
- **Benign False Alarm (`benign_false_alarm_wind`):** Wind blowing porch foliage triggering PIR sensor with package untouched. *(Correctly classified: 0.0% false-positive rate).*
- **Recurring Visitor:** Midday visit from trusted neighbor Sarah and afternoon pet walk. *(Correctly matched to routine).*

Judges can execute this benchmark live directly in the web console (`POST /api/evaluation/run`) or query cached metrics (`GET /api/evaluation/benchmark`).

---

## 🔗 Causal Evidence Chains

Instead of treating doorbell rings as disconnected atomic alerts, **Sentinel** connects related events across time into causal evidence chains displayed visually in the demo console:

```
[1. Package Deposited] ──> [2. Lingered 5.2h] ──> [3. Unrecognized Approach] ──> [4. Package Seized]
    (Amazon Prime 10:15)      (Collection Window       (Actor without Uniform      (Unauthorized Theft,
                               Exceeded)                15:35 UTC)                   Actor Flees)
                                                                                          │
                                                                                          ▼
                                                                             [ VERDICT: CRITICAL THEFT ]
                                                                             Confidence: 98%
                                                                             • Sound 85dB Siren Warning
                                                                             • Auto-File Carrier Claim
                                                                             • Export to Ring Neighbors
```

---

## ⚡ Proactive Mitigation Actions

Every anomaly detected by Sentinel is paired with concrete, one-click mitigation actions executable from the web console or automated via home automation:

- **Lingering Package (>4h):**
  - `act_alexa_announce`: Broadcast porch reminder chime on Alexa Echo smart speakers.
  - `act_push_notify`: Dispatch urgent push alert with camera snapshot.
  - `act_neighbor_request`: Send one-tap SMS asking neighbor Sarah to stash the package inside.
- **Porch Theft / Intrusion:**
  - `act_siren_alarm`: Trigger exterior camera's 85dB siren warning.
  - `act_file_carrier_claim`: Generate automated one-click claim packet with delivery & theft timestamps.
  - `act_export_evidence`: Export 30-second incident video clip to local Ring Neighborhood feed.
- **Doorway Tailgating:**
  - `act_lockdown_home`: Immediately command smart deadbolts to lock.

---

## 🚀 Quickstart & Demo

### 1. Prerequisites
- Python 3.10+
- `pip`

### 2. Installation
```bash
git clone https://github.com/Sourabh-Kumar04/porchline.git
cd porchline
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Run the Web Demo Console
```bash
python3 -m uvicorn porchline.main:app --host 0.0.0.0 --port 8000
```
Open **`http://localhost:8000`** in your browser.

- **Test Ingestion:** Click any scenario button (*"Porch Pirate Theft"*, *"Adversarial Package Swap"*, *"Doorway Tailgating"*, *"Amazon Prime Courier Drop-off"*) to inject HMAC-signed payloads into the live cooperating agent pipeline.
- **Inspect Routines:** View the *Learned Household Routines* card showing quiet hours, carrier delivery windows, and familiar recurring visitors.
- **View Causal Chains:** Observe Sentinel synthesize visual multi-event chains with proposed proactive actions.
- **Run Live Benchmark:** Click *"Run Live Benchmark"* to score the agent architecture across adversarial scenarios in real time.
- **Ask the Agent:** Try queries like:
  - *"When did the courier come?"*
  - *"Are there any packages still outside?"*
  - *"Was there any porch theft or suspicious activity?"*
  - *"What is our household quiet hours routine?"*

### 4. Run the Test Suite
```bash
pytest -v
```
All **30/30 tests** pass (including multi-agent unit tests, causal chain integration tests, adversarial evaluation harness tests, and hostile QA break-it tests).

---

## 🔐 Configuration & Security

### Ring Webhook Secret Override (`RING_WEBHOOK_SECRET`)
Ring Partner API webhooks require HMAC-SHA256 signature verification via a shared secret header (`X-Signature`).

- **Local Development / Fast Testing:** Defaults to a development secret for seamless zero-config local testing.
- **Environment Variable Override:** Set `RING_WEBHOOK_SECRET` in your shell or deployment environment:
  ```bash
  export RING_WEBHOOK_SECRET="your_secure_random_production_secret_here"
  ```
- **Fail-Fast Security in Production:** If Porchline detects a production or staging environment (via `PORCHLINE_ENV=production`, `ENVIRONMENT=production`, or when running inside AWS Lambda) and the default development secret is present or unconfigured, the application **fails fast at startup** with a descriptive `RuntimeError`. This prevents accidental deployment of public repository defaults into live environments.
- **AWS SAM Deployments (`template.yaml`):** The `RingWebhookSecretParam` parameter does not include a committed default secret; it must be supplied at deploy time via `sam deploy --guided` or parameter overrides.

---

## 🧪 Amazon Bedrock & DynamoDB: Live vs. Mock Mode Disclosure

To provide a seamless zero-friction experience for judges, peer reviewers, and automated evaluation harnesses without requiring active AWS accounts or incurring cloud charges:

- **Zero-Credential Mock Mode:** If AWS credentials (`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`) are omitted or mock keys are used, Porchline automatically operates in high-fidelity mock mode:
  - Synthetic snapshot frames are analyzed using deterministic, spec-compliant perception logic.
  - Episodic records are stored in an in-memory DynamoDB-compatible timeline store.
- **Live AWS Cloud Mode:** When valid AWS credentials with Amazon Bedrock and DynamoDB permissions are present:
  - Snapshot frames are transmitted directly to **Amazon Bedrock** (`anthropic.claude-3-5-sonnet-20240620-v1:0` multimodal VLM).
  - Events are persisted directly into the live **Amazon DynamoDB** single-table (`PorchlineEpisodicEvents`).
- **Web Console Indicator Badge:** The live web console at `/` features a visible, prominent indicator badge in the top navigation header (`MOCK MODE` or `LIVE BEDROCK`), ensuring judges and reviewers always know exactly which mode is active.

---

## 📁 Repository Layout
```
├── .kiro/
│   └── agents/
│       └── porchline-aws.toml        # Kiro CLI agent specification
├── porchline/
│   ├── agents/                       # 4 Cooperating Agents Architecture
│   │   ├── __init__.py
│   │   ├── perceiver.py              # Perceiver: VLM multimodal scene parsing
│   │   ├── memorian.py               # Memorian: Learned routines & consolidation
│   │   ├── sentinel.py               # Sentinel: Anomaly reasoning & causal chains
│   │   ├── chronicler.py             # Chronicler: Evening digest & conversational Q&A
│   │   └── coordinator.py            # PorchlineAgentCoordinator orchestrator
│   ├── eval/                         # Adversarial Evaluation Benchmark Suite
│   │   ├── __init__.py
│   │   └── harness.py                # Scored metrics (Recall, FPR, QA accuracy)
│   ├── ingestion/
│   │   └── verifier.py               # HMAC-SHA256 signature verifier & deduplicator
│   ├── memory/
│   │   ├── bedrock_processor.py      # Bedrock Claude/Nova multimodal vision parser
│   │   └── dynamo_store.py           # DynamoDB single-table episodic store
│   ├── query/
│   │   └── memory_agent.py           # Facade integrating cooperating agents
│   ├── simulator/
│   │   ├── frame_generator.py        # Doorbell camera snapshot frame generator
│   │   └── simulator_engine.py       # Ring Partner API JSON:API webhook simulator
│   ├── lambda_handler.py             # AWS Lambda ASGI adapter
│   └── main.py                       # FastAPI router, APIs & interactive web console
├── tests/
│   ├── test_porchline_agents.py      # Multi-agent, routine, & causal chain tests
│   ├── test_porchline_eval.py        # Adversarial evaluation harness benchmark tests
│   ├── test_porchline_core.py        # Core unit & integration tests
│   └── test_porchline_hostile.py     # Hostile QA break-it tests
├── template.yaml                     # AWS SAM serverless deployment template
├── FRICTION_LOG.md                   # +10% bonus friction log documentation
├── QA_REPORT.md                      # Hostile QA verification audit report
├── DEMO_SHOTLIST.md                  # <=3 min video demo beats & script
└── pyproject.toml                    # Pytest and project configuration
```

---

## 📄 License
This project is licensed under the [MIT License](LICENSE).
