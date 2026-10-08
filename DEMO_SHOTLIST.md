# Porchline: 3-Minute Demo Video Shotlist & Presentation Beats
**Target Duration:** <= 3 Minutes (180 Seconds)  
**Hackathon:** Amazon "Build, Ship, Shape: Amazon Developer Hackathon 2026"  
**Tracks:** Ring Track + AWS Builder Mini-Challenge  

---

## Shotlist Breakdown

### Beat 1: The Problem & Creative Shift (0:00 – 0:30)
- **Visual:** Screen showing typical barrage of video doorbell notifications ("Motion detected at 2:14 PM", "Motion detected at 2:38 PM", "Motion detected at 3:12 PM").
- **Voiceover / Script:**
  > *"Every day, smart video doorbells send us hundreds of nagging pings: 'Motion detected.' But when you actually want to know something useful—like 'Did the Amazon courier drop off my medication?', 'When did the neighbor return my tools?', or 'Is that package still sitting in the rain?'—the camera has no memory.*
  > *Introducing **Porchline**: an ambient front-door episodic memory agent built for Ring and Amazon Bedrock."*

---

### Beat 2: Architecture & The Ring Webhook Simulator (0:30 – 1:05)
- **Visual:** Switch to Porchline Web Console. Show the **Ring Webhook Simulator Harness** on the left.
- **Voiceover / Script:**
  > *"Because no official GUI device simulator exists in the Ring developer ecosystem, Porchline includes a fully spec-compliant Local Webhook Simulator. It emits HMAC-SHA256 signed JSON:API payloads matching the Ring Partner API standards, complete with synthetic camera snapshots.*
  > *Our FastAPI ingestion layer immediately verifies the signature, enforces fast-ack within Ring’s 5-second SLA, and deduplicates events via `request_id`."*
- **Action on Screen:** Click **"Amazon Prime Courier Drop-off"** scenario button. Show the instantaneous Fast ACK in the network tab and the timeline updating.

---

### Beat 3: AWS Bedrock Multimodal VLM & DynamoDB Memory (1:05 – 1:45)
- **Visual:** Zoom into the timeline card that just appeared. Show the generated camera frame, visitor classification, and structured metadata.
- **Voiceover / Script:**
  > *"Ring webhooks only say 'package_delivery'—they're too thin for deep queries. Porchline takes the snapshot frame and routes it through **Amazon Bedrock Multimodal VLM**.*
  > *Bedrock extracts the rich scene: courier uniform (Amazon Prime), action (deposited parcel on mat), parcel count, and placement. This is stored directly in **Amazon DynamoDB** using a single-table episodic schema."*
- **Action on Screen:** Click the **"Golden Retriever Porch Visit"** and **"Neighbor Sarah Visit"** scenarios to demonstrate non-security, everyday neighborhood life tracking.

---

### Beat 4: Natural Language Memory Q&A (1:45 – 2:20)
- **Visual:** Move to the right-hand **Episodic Memory Query (NL Q&A)** panel.
- **Voiceover / Script:**
  > *"Now, front-door memory becomes conversational. Residents can simply ask in plain English."*
- **Action on Screen:**
  1. Type or click: `"When did the courier come?"` -> Show agent answer: *"The courier (Amazon) arrived at 08:30 UTC and delivered a package on the left side of the welcome mat."*
  2. Type or click: `"Did an animal visit the porch?"` -> Show agent answer: *"Yes! A domestic pet was detected sniffing near the walkway at 10:15 UTC."*
  3. Type or click: `"Are there any packages still outside?"` -> Show agent answer: *"Yes, 1 Amazon parcel has been outside on the porch floor for 5.2 hours."*

---

### Beat 5: Lingering Package Anomaly & Automated Evening Digest (2:20 – 2:45)
- **Visual:** Highlight the **Evening Digest & Anomalies** card.
- **Voiceover / Script:**
  > *"Porchline actively watches for anomalies. If a parcel sits uncollected for over 4 hours, it flags a lingering package alert to prevent weather damage or porch piracy.*
  > *And every evening at 6:00 PM, Porchline automatically compiles an Evening Digest summarizing the day's visits, rings, and parcel statuses."*

---

### Beat 6: The Mini-Challenges & Wrap-up (2:45 – 3:00)
- **Visual:** Show the GitHub repository (`README.md`, `FRICTION_LOG.md`, `.kiro/agents/porchline-aws.toml`, `template.yaml`).
- **Voiceover / Script:**
  > *"Porchline stacks both mini-challenges: built using the **Kiro CLI** and **Amazon Bedrock/DynamoDB** for AWS Builder, published fully open-source on GitHub, and accompanied by a detailed Friction Log documenting Ring developer realities.*
  > *Porchline: turning smart doorbells into intelligent front-door memory. Thank you!"*
