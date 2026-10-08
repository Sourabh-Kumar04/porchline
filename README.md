# 🚪 Porchline — Front-Door Episodic Memory Agent

[![Amazon Build, Ship, Shape Hackathon 2026](https://img.shields.io/badge/Amazon%20Hackathon-Ring%20Track-blue.svg)](https://devpost.com)
[![AWS Builder Mini](https://img.shields.io/badge/AWS%20Builder%20Mini-Bedrock%20%7C%20DynamoDB-orange.svg)](https://aws.amazon.com/bedrock/)
[![Kiro CLI Qualified](https://img.shields.io/badge/Built%20With-Kiro%20CLI-purple.svg)](https://kiro.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Tests: 20/20 Green](https://img.shields.io/badge/Tests-20%2F20%20Passing-brightgreen.svg)](tests/)

> **Porchline** transforms Ring doorbells from nagging motion alarms into an ambient episodic memory agent. Powered by **Ring Partner API webhooks**, **Amazon Bedrock Multimodal VLM**, and **Amazon DynamoDB**, Porchline understands daily home life, answers natural-language questions (*"When did the courier come?"*), alerts you to lingering packages (>4h), and automatically compiles an end-of-day digest.

---

## 🌟 Why Porchline? (The Creative Non-Security Mandate)
Most smart camera apps are basic security alarms that spam residents with noisy alerts ("Motion detected at 2:14 PM").

The Amazon Hackathon explicitly penalizes obvious security camera viewers and rewards **creative, non-security applications** (such as package/delivery management and accessibility).

**Porchline redefines the front door:**
- **Episodic Front-Door Timeline:** Knows *who* came (courier, neighbor, pet, resident), *what* they did, and *where* items were placed.
- **Natural Language Memory Q&A:** Residents ask plain-English questions instead of scrubbing through hours of video clips.
- **Lingering Package Anomaly Alerts:** Flags deliveries sitting outdoors > 4 hours uncollected.
- **Automated Evening Digest:** Summarizes daily arrivals and doorbells at 6:00 PM.
- **Spec-Compliant Ring Simulator:** Implements authentic `HMAC-SHA256` signed JSON:API payloads and synthetic snapshot frames—overcoming the lack of an official Ring GUI hardware emulator.

---

## 🏗️ Architecture

```
                       +------------------------------------+
                       |     RING LOCAL WEBHOOK SIMULATOR   |
                       | - Emulates api.amazonvision.com    |
                       | - Generates synthetic snapshot     |
                       | - Computes HMAC-SHA256 X-Signature |
                       +-----------------+------------------+
                                         | HTTPS POST (JSON:API)
                                         v
+---------------------------------------------------------------------------------+
|                                PORCHLINE SERVER                                 |
|                                                                                 |
|   1. Fast-ACK Ingestion Layer                                                   |
|      - Verifies HMAC-SHA256 signature                                           |
|      - Idempotent deduplication by request_id (<5s Ring SLA)                   |
|                                                                                 |
|   2. Multimodal Perception (Amazon Bedrock Claude 3.5 Sonnet / Nova)            |
|      - Parses snapshot image frame + Ring metadata                              |
|      - Extracts visitor type, courier uniform, parcel presence, action          |
|                                                                                 |
|   3. Episodic Memory Store (Amazon DynamoDB)                                    |
|      - Single-table schema (PK: DEVICE#<id>, SK: EVENT#<ts>#<id>)               |
|      - Seamless local in-memory fallback when credentials absent                |
|                                                                                 |
|   4. Agentic Intelligence & Web Console                                         |
|      - Natural language memory Q&A engine                                       |
|      - Lingering package anomaly detector (>4 hrs)                              |
|      - Automated 6:00 PM Evening Digest                                         |
|      - Modern Tailwind / HTML5 real-time console                                |
+---------------------------------------------------------------------------------+
```

---

## 🏆 Hackathon Stack & Mini-Challenge Alignments

1. **Ring Track (Primary):**
   - Implements full Ring Partner API webhook schema (`ding`, `motion.human`, `motion.animal`, `motion.vehicle`, `package_delivery`).
   - Validates official `X-Signature` HMAC-SHA256 headers.
   - Solves the documented "data thinness" problem using vision intelligence.

2. **AWS Builder Mini-Challenge:**
   - **Amazon Bedrock:** Multimodal VLM analysis of snapshot frames.
   - **Amazon DynamoDB:** Single-table episodic event log design.
   - **AWS SAM Template:** Ready-to-deploy serverless infrastructure (`template.yaml`).
   - **Kiro CLI:** Built and architected using Kiro CLI agents (`.kiro/agents/porchline-aws.toml`).

3. **Friction Log Bonus (+10% Judging Bonus):**
   - Full evaluation report in [`FRICTION_LOG.md`](FRICTION_LOG.md) detailing discrepancies between marketing claims and technical reality (lack of official hardware emulator, subscription gating, and global dev access).

4. **Open Source Mini-Challenge:**
   - Released under the open-source MIT License with full test suite.

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

*(Or install core dependencies directly: `pip install fastapi uvicorn pydantic boto3 pytest httpx pillow`)*

### 3. Run the Web Demo Console
```bash
python3 -m uvicorn porchline.main:app --host 0.0.0.0 --port 8000
```
Open **`http://localhost:8000`** in your browser.

- **Test Ingestion:** Click any scenario button (*"Amazon Prime Courier Drop-off"*, *"Neighbor Visit"*, *"Golden Retriever Visit"*) to inject HMAC-signed payloads into the live pipeline.
- **Ask the Agent:** Try queries like:
  - *"When did the courier come?"*
  - *"Are there any packages still outside?"*
  - *"Did an animal visit the porch?"*
- **View Digest:** See the automatically generated daily digest with active lingering package alerts.

### 4. Run the Test Suite
```bash
pytest -v
```
All **20/20 tests** pass (including all unit, integration, and hostile break-it QA suites).

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
- **Web Console Indicator Badge:** The live web console at `/` features a visible, prominent indicator badge in the top navigation header (`MOCK MODE` or `LIVE BEDROCK`) as well as in the AWS Builder Mini Stack card, ensuring judges and reviewers always know exactly which mode is active.

---

## ⚡ Concurrency & Event Deduplication Architecture

Ring webhooks must satisfy a strict **<5s SLA** and can be delivered multiple times under network retries.

- **Distributed Deduplication (Production):** When running against live DynamoDB (e.g. across concurrent AWS Lambda instances), deduplication is enforced via atomic conditional writes (`ConditionExpression="attribute_not_exists(PK)"`) on `DEDUP#<request_id>` items with TTL. If concurrent Lambda invocations receive identical request IDs, DynamoDB atomicity guarantees exactly one execution while subsequent invocations fast-ACK with `deduplicated: true`.
- **Known Limitation in Local Mode:** When running in local single-process development mode without live DynamoDB, deduplication is managed via an in-process TTL cache (`EventDeduplicator`). In this mode, deduplication state is process-local and does not persist across application restarts or container recreation.

---

## 📁 Repository Layout
```
├── .kiro/
│   └── agents/
│       └── porchline-aws.toml        # Kiro CLI agent specification
├── porchline/
│   ├── ingestion/
│   │   └── verifier.py               # HMAC-SHA256 signature verifier & deduplicator
│   ├── memory/
│   │   ├── bedrock_processor.py      # Bedrock Claude/Nova multimodal vision parser
│   │   └── dynamo_store.py           # DynamoDB single-table episodic store
│   ├── query/
│   │   └── memory_agent.py           # NL Q&A, anomaly detector & evening digest
│   ├── simulator/
│   │   ├── frame_generator.py        # Doorbell camera snapshot frame generator
│   │   └── simulator_engine.py       # Ring Partner API JSON:API webhook simulator
│   ├── lambda_handler.py             # AWS Lambda ASGI adapter
│   └── main.py                       # FastAPI router & interactive web console
├── tests/
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
