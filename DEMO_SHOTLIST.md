# Porchline: 3-Minute Demo Video Shotlist & Presentation Beats
**Target Duration:** <= 3 Minutes (180 Seconds)  
**Hackathon:** Amazon "Build, Ship, Shape: Amazon Developer Hackathon 2026"  
**Tracks:** Ring Track + AWS Builder Mini-Challenge  
**Architecture:** 4 Cooperating Agents (Perceiver, Memorian, Sentinel, Chronicler)  

---

## Shotlist Breakdown

### Beat 1: The Problem & Creative Shift (0:00 – 0:25)
- **Visual:** Screen showing barrage of video doorbell notifications ("Motion detected at 2:14 PM", "Motion detected at 2:38 PM", "Motion detected at 3:12 PM").
- **Voiceover / Script:**
  > *"Every day, smart doorbells spam us with nagging motion alerts. But when you ask something useful—'When did the courier come?', 'Did Sarah drop off my keys?', or 'Is that package still sitting in the rain?'—the doorbell has no memory.*
  > *Introducing **Porchline**: an ambient front-door episodic memory agent powered by 4 cooperating agents, Ring webhooks, and Amazon Bedrock."*

---

### Beat 2: 4-Agent Architecture & Learned Routines (0:25 – 0:55)
- **Visual:** Switch to Porchline Web Console. Show the **Cooperating Agent Architecture HUD** (Perceiver, Memorian, Sentinel, Chronicler) and the **Learned Household Routines** card.
- **Voiceover / Script:**
  > *"Porchline replaces linear pipelines with four cooperating agents communicating over Amazon DynamoDB.*
  > ***Perceiver** runs Bedrock multimodal vision.*
  > ***Memorian** consolidates episodic events into semantic household routines: learning typical delivery windows (Amazon 9am to 4pm), recurring visitors (neighbor Sarah, daily dog walks), and nighttime quiet hours (22:00 to 06:00 UTC).*
  > *Every event is evaluated against learned normal—so motion at 2 PM matches routine, while motion at 2 AM with no prior pattern is immediately reasoned as anomalous."*

---

### Beat 3: Adversarial Simulation & Causal Evidence Chains (0:55 – 1:35)
- **Visual:** Show the **Ring Webhook Simulator** with adversarial scenarios (*"Porch Pirate Theft"*, *"Adversarial Package Swap"*, *"Doorway Tailgating"*). Click **"Porch Pirate Theft"**.
- **Voiceover / Script:**
  > *"Our spec-compliant simulator injects HMAC-SHA256 signed JSON:API webhooks with synthetic camera snapshots.*
  > *Watch **Sentinel Agent** synthesize a multi-event **Causal Evidence Chain** across time.*
  > *Instead of 4 disconnected pings, Porchline links the story: [1. Package Delivered at 10:15] ➔ [2. Lingered 5h Uncollected] ➔ [3. Unauthorized Person Approached at 15:30] ➔ [4. Package Missing] = **CONFIRMED THEFT NARRATIVE** (98% confidence)."*
- **Action on Screen:** Point out the visual stepper in the **Causal Evidence Narrative Chains** card showing the 4 linked nodes with red alert verdict.

---

### Beat 4: Proactive Actions & One-Click Mitigation (1:35 – 2:05)
- **Visual:** Focus on the **Proposed Proactive Actions** buttons on the theft chain and lingering package alert.
- **Voiceover / Script:**
  > *"Porchline doesn't just alert—it acts. Sentinel proposes concrete next actions tailored to each threat.*
  > *For lingering packages: 'Announce on Echo / Alexa' or 'Request Neighbor Stash'.*
  > *For confirmed theft: 'Sound 85dB Siren' or 'Auto-File Carrier Claim' with timestamped delivery proof.*
  > *Clicking an action executes it immediately on the camera."*
- **Action on Screen:** Click **"Sound 85dB Siren Warning"** and **"Announce on Echo / Alexa"**—show toast notification confirming action dispatched.

---

### Beat 5: Conversational Memory Q&A & Evening Digest (2:05 – 2:35)
- **Visual:** Move to the **Episodic Memory Query (NL Q&A)** panel and **Evening Digest** card.
- **Voiceover / Script:**
  > *"Residents query front-door history naturally. **Chronicler Agent** answers with routine and causal awareness."*
- **Action on Screen:**
  1. Click chip: `"When did the courier come?"` -> Chronicler answers: *"The courier (Amazon) arrived at 08:30 UTC (matching learned routine delivery window: 09:00 - 16:00 UTC) and placed package on mat."*
  2. Click chip: `"Was there any porch theft or suspicious activity?"` -> Chronicler answers: *"Alert: Confirmed Porch Theft Narrative Chain (HIGH-CONFIDENCE THEFT DETECTED)..."*
  3. Click chip: `"What is our household quiet hours routine?"` -> Explains quiet hours policy and recurring visitors.

---

### Beat 6: Scored Evaluation Benchmark & Mini-Challenge Wrap-up (2:35 – 3:00)
- **Visual:** Zoom into the **Adversarial Evaluation & Scored Metrics** panel. Click **"Run Live Benchmark"**.
- **Voiceover / Script:**
  > *"To prove performance, Porchline includes an automated adversarial evaluation harness.*
  > *Clicking 'Run Live Benchmark' scores our pipeline across real-world adversarial attacks:*
  > ***100% Detection Recall**, **0.0% False-Positive Rate**, and **100% QA Accuracy**.*
  > *Built with Kiro CLI and AWS Bedrock/DynamoDB for the AWS Builder mini-challenge, open-source with 30 green tests and an extensive Friction Log.*
  > *Porchline: intelligent front-door memory for Ring. Thank you!"*
