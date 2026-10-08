"""Sentinel Agent: Anomaly Reasoning, Causal Narratives, and Proactive Actions.

Role & Responsibility:
- Continuously inspects episodic events in context with Memorian's learned routine profiles.
- Reasoning capabilities:
  1. Routine Deviations: flags events breaching learned normal thresholds (quiet hours, unusual carriers).
  2. Lingering Package Anomalies: detects deliveries sitting outside > threshold hours uncollected.
  3. Causal Narrative Synthesis (Evidence Chains):
     - Links related events across time into causal evidence chains:
       * Theft Narrative: [Package Delivered] -> [Lingered 6h] -> [Unknown Approached] -> [Package Missing]
       * Package Swap Narrative: [Delivered] -> [Stranger Replaces with Dummy] -> [Original Taken]
       * Tailgating Narrative: [Resident Unlocks Door] -> [Stranger Follows Directly Inside]
       * Benign False Alarm: [Wind / Animal Motion] -> [Package Confirmed Intact, No Disturbance]
  4. Proactive Next Actions:
     - Equips each anomaly and causal narrative with concrete, one-click mitigations:
       * Trigger Alexa Chime / Echo Announcement
       * Arm Ring 85dB Siren Warning
       * Auto-file Carrier Claim with Snapshot Proof
       * Floodlight Activation & Two-Way Intercom
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field

logger = logging.getLogger("porchline.agents.sentinel")


class ProactiveAction(BaseModel):
    """Concrete actionable mitigation suggested for an anomaly or causal event."""
    action_id: str
    label: str
    action_type: str  # chime, siren, push, claim, device_control, export
    severity: str  # critical, high, moderate, info
    description: str
    target_device: str = "ring-cam-front-porch"
    executed: bool = False


class AnomalyAlert(BaseModel):
    """Structured anomaly alert with routine context and proactive actions."""
    anomaly_id: str
    type: str  # lingering_package, quiet_hours_intrusion, suspicious_loiter, routine_deviation
    severity: str  # critical, high, moderate, low
    title: str
    description: str
    routine_reason: str
    event_id: Optional[str] = None
    detected_at: str
    proactive_actions: List[ProactiveAction] = Field(default_factory=list)
    confidence: float = 0.95


class CausalNode(BaseModel):
    """Step/Node in a multi-event causal narrative chain."""
    step: int
    event_id: str
    timestamp: str
    title: str
    description: str
    visitor_type: str
    carrier: str
    icon: str
    status: str  # normal, lingering, trigger, conclusion


class CausalNarrative(BaseModel):
    """Multi-event causal evidence chain linking related episodes."""
    narrative_id: str
    narrative_type: str  # package_theft, package_swap, tailgating, lingering_delivery, benign_cleared
    title: str
    verdict: str
    severity: str  # critical, high, moderate, benign
    confidence: float
    summary: str
    nodes: List[CausalNode] = Field(default_factory=list)
    proactive_actions: List[ProactiveAction] = Field(default_factory=list)
    resolved: bool = False


class SentinelAgent:
    """Agent responsible for anomaly reasoning, causal narrative construction, and proactive action generation."""

    def __init__(self, dynamo_store: Any, memorian_agent: Any):
        self.store = dynamo_store
        self.memorian = memorian_agent
        self.agent_name = "Sentinel"
        self.version = "2.0.0"

    def analyze_timeline(self, lingering_threshold_hours: float = 4.0) -> Dict[str, Any]:
        """Run complete anomaly reasoning over the timeline."""
        events = self.store.get_timeline(limit=100)
        profile = self.memorian.get_or_build_profile()

        anomalies = self._detect_anomalies(events, profile, lingering_threshold_hours)
        narratives = self._synthesize_causal_narratives(events, profile)

        return {
            "agent": self.agent_name,
            "anomalies": [a.model_dump() for a in anomalies],
            "narratives": [n.model_dump() for n in narratives],
            "active_threat_level": "critical" if any(n.severity == "critical" for n in narratives) else ("high" if anomalies else "normal")
        }

    def _detect_anomalies(
        self,
        events: List[Dict[str, Any]],
        profile: Any,
        threshold_hours: float = 4.0
    ) -> List[AnomalyAlert]:
        """Detect deviations from learned routine baselines and lingering packages."""
        anomalies: List[AnomalyAlert] = []
        now = datetime.now(timezone.utc)
        chronological = sorted(events, key=lambda x: x.get("created_at", ""))

        # 1. Lingering package detection with proactive actions
        deliveries = [e for e in chronological if e.get("parcel_detected") and e.get("visitor_type") == "courier"]
        for d in deliveries:
            try:
                delivery_dt = datetime.fromisoformat(d["created_at"].replace("Z", "+00:00"))
            except Exception:
                delivery_dt = now - timedelta(hours=5)

            elapsed_hours = max(0.0, (now - delivery_dt).total_seconds() / 3600.0)

            # Check if picked up or removed
            subsequent = [e for e in chronological if e.get("created_at", "") > d.get("created_at", "")]
            picked_up = any("pickup" in e.get("action", "").lower() or "retrieved" in e.get("action", "").lower() for e in subsequent)
            stolen = any("stole" in e.get("action", "").lower() or "theft" in e.get("action", "").lower() for e in subsequent)

            if not picked_up and not stolen and elapsed_hours >= threshold_hours:
                hours_str = f"{elapsed_hours:.1f}"
                carrier = d.get("uniform_carrier", "Courier")
                anomalies.append(AnomalyAlert(
                    anomaly_id=f"anom_linger_{d.get('event_id', 'unknown')}",
                    type="lingering_package",
                    severity="high" if elapsed_hours >= 4.0 else "moderate",
                    title=f"Lingering {carrier} Parcel ({hours_str}h uncollected)",
                    description=f"Package delivered at {d.get('created_at', '')[:16]} UTC remains outside on {d.get('placement', 'the porch')}.",
                    routine_reason=f"Exceeds normal household collection window ({profile.baseline_stats.get('max_unattended_package_hours_normal', 2.5)}h limit).",
                    event_id=d.get("event_id"),
                    detected_at=now.isoformat(),
                    confidence=0.96,
                    proactive_actions=[
                        ProactiveAction(
                            action_id="act_alexa_announce",
                            label="Announce on Echo / Alexa",
                            action_type="chime",
                            severity="high",
                            description="Broadcast porch chime reminder: 'A package has been outside for 5 hours'."
                        ),
                        ProactiveAction(
                            action_id="act_push_notify",
                            label="Send Urgent Mobile Ping",
                            action_type="push",
                            severity="high",
                            description="Send priority notification with snapshot to household phones."
                        ),
                        ProactiveAction(
                            action_id="act_neighbor_request",
                            label="Request Neighbor Stash",
                            action_type="sms",
                            severity="moderate",
                            description="Send one-tap text to Sarah to bring package inside until you return."
                        )
                    ]
                ))

        # 2. Quiet hours routine deviations
        for ev in events:
            dev_check = self.memorian.evaluate_routine_deviation(ev, profile)
            if not dev_check["is_routine_match"] and dev_check["deviation_level"] == "high":
                anom_id = f"anom_quiet_{ev.get('event_id', 'unknown')}"
                if not any(a.anomaly_id == anom_id for a in anomalies):
                    anomalies.append(AnomalyAlert(
                        anomaly_id=anom_id,
                        type="quiet_hours_intrusion",
                        severity="high",
                        title="Off-Hours Porch Activity During Quiet Hours",
                        description=ev.get("summary", "Unrecognized activity detected during nighttime hours."),
                        routine_reason=dev_check["reason"],
                        event_id=ev.get("event_id"),
                        detected_at=ev.get("created_at", now.isoformat()),
                        confidence=0.92,
                        proactive_actions=[
                            ProactiveAction(
                                action_id="act_floodlight_on",
                                label="Activate Porch Floodlight",
                                action_type="device_control",
                                severity="high",
                                description="Turn on 2000-lumen Ring floodlight to illuminate the porch walkway."
                            ),
                            ProactiveAction(
                                action_id="act_two_way_talk",
                                label="Open Two-Way Intercom",
                                action_type="intercom",
                                severity="moderate",
                                description="Open live two-way audio stream through the Ring mobile app."
                            )
                        ]
                    ))

        # 3. Explicit Lingering Alert Detection
        for ev in events:
            action_l = ev.get("action", "").lower()
            summary_l = ev.get("summary", "").lower()
            desc_l = ev.get("parcel_description", "").lower()
            sc_title = ev.get("scenario_title", "").lower()
            if ev.get("parcel_detected") and any(k in action_l or k in summary_l or k in desc_l or k in sc_title for k in ["lingering", "uncollected", "unattended", "after dark"]):
                anom_id = f"anom_linger_{ev.get('event_id', 'unknown')}"
                if not any(a.anomaly_id == anom_id for a in anomalies):
                    anomalies.append(AnomalyAlert(
                        anomaly_id=anom_id,
                        type="lingering_package",
                        severity="high",
                        title="Lingering Uncollected Package Anomaly",
                        description=ev.get("summary", "Package left unattended past normal collection threshold."),
                        routine_reason=f"Exceeds normal household collection window ({profile.baseline_stats.get('max_unattended_package_hours_normal', 2.5)}h limit).",
                        event_id=ev.get("event_id"),
                        detected_at=ev.get("created_at", now.isoformat()),
                        confidence=0.96,
                        proactive_actions=[
                            ProactiveAction(
                                action_id="act_alexa_announce",
                                label="Announce on Echo / Alexa",
                                action_type="chime",
                                severity="high",
                                description="Broadcast porch chime reminder on Alexa smart speakers."
                            ),
                            ProactiveAction(
                                action_id="act_push_notify",
                                label="Send Urgent Mobile Ping",
                                action_type="push",
                                severity="high",
                                description="Send priority notification with snapshot to household phones."
                            )
                        ]
                    ))

        # 4. Direct Threat & Intrusion Actions (Theft, Swap, Tailgating)
        for ev in events:
            action_l = ev.get("action", "").lower()
            summary_l = ev.get("summary", "").lower()
            if any(k in action_l or k in summary_l for k in ["stole", "theft", "pirate", "seized parcel"]):
                anom_id = f"anom_theft_{ev.get('event_id', 'unknown')}"
                if not any(a.anomaly_id == anom_id for a in anomalies):
                    anomalies.append(AnomalyAlert(
                        anomaly_id=anom_id,
                        type="porch_theft",
                        severity="critical",
                        title="Porch Theft / Unauthorized Package Removal",
                        description=ev.get("summary", "Unauthorized actor seized parcel from porch."),
                        routine_reason="Critical security breach: package removed without resident pickup.",
                        event_id=ev.get("event_id"),
                        detected_at=ev.get("created_at", now.isoformat()),
                        confidence=0.98,
                        proactive_actions=[
                            ProactiveAction(
                                action_id="act_siren_alarm",
                                label="Sound 85dB Siren Warning",
                                action_type="siren",
                                severity="critical",
                                description="Trigger siren chime on exterior Ring camera."
                            ),
                            ProactiveAction(
                                action_id="act_file_carrier_claim",
                                label="Auto-File Carrier Stolen Claim",
                                action_type="claim",
                                severity="critical",
                                description="Generate carrier claim with proof of theft."
                            )
                        ]
                    ))
            elif any(k in action_l or k in summary_l for k in ["swap", "substituted"]):
                anom_id = f"anom_swap_{ev.get('event_id', 'unknown')}"
                if not any(a.anomaly_id == anom_id for a in anomalies):
                    anomalies.append(AnomalyAlert(
                        anomaly_id=anom_id,
                        type="package_swap",
                        severity="critical",
                        title="Adversarial Package Swap Detected",
                        description=ev.get("summary", "Package replaced with substitute dummy envelope."),
                        routine_reason="Deceptive parcel tampering detected at entryway.",
                        event_id=ev.get("event_id"),
                        detected_at=ev.get("created_at", now.isoformat()),
                        confidence=0.95,
                        proactive_actions=[
                            ProactiveAction(
                                action_id="act_flag_swap",
                                label="Flag Tampered Delivery",
                                action_type="claim",
                                severity="critical",
                                description="Report package swap to carrier."
                            )
                        ]
                    ))
            elif any(k in action_l or k in summary_l for k in ["tailgat"]):
                anom_id = f"anom_tailgate_{ev.get('event_id', 'unknown')}"
                if not any(a.anomaly_id == anom_id for a in anomalies):
                    anomalies.append(AnomalyAlert(
                        anomaly_id=anom_id,
                        type="tailgating_entry",
                        severity="critical",
                        title="Doorway Tailgating Approach Detected",
                        description=ev.get("summary", "Stranger followed resident into open entryway."),
                        routine_reason="Unauthorized entryway entry without chime or credential.",
                        event_id=ev.get("event_id"),
                        detected_at=ev.get("created_at", now.isoformat()),
                        confidence=0.94,
                        proactive_actions=[
                            ProactiveAction(
                                action_id="act_lockdown_home",
                                label="Lock Smart Door Deadbolts",
                                action_type="device_control",
                                severity="critical",
                                description="Command smart locks to immediately engage deadbolts."
                            )
                        ]
                    ))

        return anomalies

    def _synthesize_causal_narratives(
        self,
        events: List[Dict[str, Any]],
        profile: Any
    ) -> List[CausalNarrative]:
        """Link related events into chronological evidence chains (theft, tailgating, swaps, benign)."""
        narratives: List[CausalNarrative] = []
        chronological = sorted(events, key=lambda x: x.get("created_at", ""))

        # Scan for theft chain: Delivery -> Lingering -> Unknown approaching -> Parcel removed/stolen
        delivery_event = None
        for ev in chronological:
            if ev.get("parcel_detected") and ev.get("visitor_type") == "courier":
                delivery_event = ev
                break

        theft_event = None
        unknown_approach = None
        for ev in chronological:
            action_l = ev.get("action", "").lower()
            summary_l = ev.get("summary", "").lower()
            v_type = ev.get("visitor_type", "")
            if "stole" in action_l or "theft" in action_l or "pirate" in summary_l or "unauthorized removal" in summary_l:
                theft_event = ev
            elif (v_type in ("unknown", "loiterer") or "approached door" in action_l) and ev != delivery_event:
                unknown_approach = ev

        # 1. Porch Piracy / Theft Causal Chain
        if delivery_event and theft_event:
            del_ts = delivery_event.get("created_at", "")[:16].replace("T", " ")
            theft_ts = theft_event.get("created_at", "")[:16].replace("T", " ")
            nodes = [
                CausalNode(
                    step=1,
                    event_id=delivery_event.get("event_id", "del_1"),
                    timestamp=del_ts,
                    title="Package Deposited by Courier",
                    description=f"{delivery_event.get('uniform_carrier', 'Courier')} dropped parcel ({delivery_event.get('parcel_description', 'box')}) on {delivery_event.get('placement', 'mat')}.",
                    visitor_type="courier",
                    carrier=delivery_event.get("uniform_carrier", "Amazon"),
                    icon="fa-box",
                    status="normal"
                ),
                CausalNode(
                    step=2,
                    event_id=f"linger_node_{delivery_event.get('event_id')}",
                    timestamp="During Afternoon",
                    title="Parcel Lingered Unattended >5 Hours",
                    description=f"Package remained in place outside beyond normal {profile.baseline_stats.get('max_unattended_package_hours_normal', 2.5)}h collection window.",
                    visitor_type="system",
                    carrier="None",
                    icon="fa-clock",
                    status="lingering"
                ),
            ]
            if unknown_approach:
                app_ts = unknown_approach.get("created_at", "")[:16].replace("T", " ")
                nodes.append(CausalNode(
                    step=3,
                    event_id=unknown_approach.get("event_id", "app_1"),
                    timestamp=app_ts,
                    title="Unrecognized Person Approached Porch",
                    description=f"Non-courier individual approached welcome mat without ringing doorbell: {unknown_approach.get('summary')}",
                    visitor_type=unknown_approach.get("visitor_type", "unknown"),
                    carrier="None",
                    icon="fa-person-walking",
                    status="trigger"
                ))

            nodes.append(CausalNode(
                step=len(nodes) + 1,
                event_id=theft_event.get("event_id", "theft_1"),
                timestamp=theft_ts,
                title="Parcel Removed Without Authorization (Theft Event)",
                description=f"Individual seized parcel and retreated rapidly from doorway: {theft_event.get('summary')}",
                visitor_type=theft_event.get("visitor_type", "unknown"),
                carrier="None",
                icon="fa-triangle-exclamation",
                status="conclusion"
            ))

            narratives.append(CausalNarrative(
                narrative_id="narrative_theft_001",
                narrative_type="package_theft",
                title="Confirmed Porch Theft Narrative Chain",
                verdict="HIGH-CONFIDENCE THEFT DETECTED",
                severity="critical",
                confidence=0.98,
                summary="Package was safely delivered, lingered uncollected past routine baseline, and was subsequently seized by an unauthorized person who fled without ringing.",
                nodes=nodes,
                proactive_actions=[
                    ProactiveAction(
                        action_id="act_siren_alarm",
                        label="Sound 85dB Siren Warning",
                        action_type="siren",
                        severity="critical",
                        description="Trigger siren chime on exterior Ring camera to deter actor."
                    ),
                    ProactiveAction(
                        action_id="act_file_carrier_claim",
                        label="Auto-File Carrier Stolen Claim",
                        action_type="claim",
                        severity="critical",
                        description=f"Generate one-click proof packet for {delivery_event.get('uniform_carrier', 'Amazon')} claim with delivery and theft timestamps."
                    ),
                    ProactiveAction(
                        action_id="act_export_evidence",
                        label="Export Video to Ring Neighbors",
                        action_type="export",
                        severity="high",
                        description="Export 30-second evidence clip with incident metadata to local Ring Neighborhood feed."
                    )
                ]
            ))

        # 2. Package Swap Chain (Adversarial)
        swap_event = next((e for e in chronological if "swapped" in e.get("action", "").lower() or "swap" in e.get("summary", "").lower()), None)
        if delivery_event and swap_event:
            narratives.append(CausalNarrative(
                narrative_id="narrative_swap_001",
                narrative_type="package_swap",
                title="Package Substitution / Tamper Chain",
                verdict="SUSPICIOUS PACKAGE SWAP DETECTED",
                severity="critical",
                confidence=0.94,
                summary="Legitimate package was replaced with dummy envelope/junk parcel by an unknown individual.",
                nodes=[
                    CausalNode(
                        step=1,
                        event_id=delivery_event.get("event_id", "del_1"),
                        timestamp=delivery_event.get("created_at", "")[:16],
                        title="Original High-Value Delivery",
                        description=delivery_event.get("summary", "Delivered"),
                        visitor_type="courier",
                        carrier=delivery_event.get("uniform_carrier", "Amazon"),
                        icon="fa-box",
                        status="normal"
                    ),
                    CausalNode(
                        step=2,
                        event_id=swap_event.get("event_id", "swp_1"),
                        timestamp=swap_event.get("created_at", "")[:16],
                        title="Substitution Action Observed",
                        description=swap_event.get("summary", "Unknown actor substituted parcel"),
                        visitor_type="unknown",
                        carrier="None",
                        icon="fa-arrows-rotate",
                        status="conclusion"
                    )
                ],
                proactive_actions=[
                    ProactiveAction(
                        action_id="act_flag_swap",
                        label="Flag Fraudulent Delivery",
                        action_type="claim",
                        severity="critical",
                        description="Report package swap to carrier and retain video logs."
                    )
                ]
            ))

        # 3. Tailgating Chain (Adversarial)
        tailgate_event = next((e for e in chronological if "tailgat" in e.get("action", "").lower() or "tailgat" in e.get("summary", "").lower()), None)
        if tailgate_event:
            narratives.append(CausalNarrative(
                narrative_id="narrative_tailgate_001",
                narrative_type="tailgating",
                title="Doorway Tailgating Incident Chain",
                verdict="UNINVITED DOORWAY ENTRY DETECTED",
                severity="critical",
                confidence=0.93,
                summary="An unknown individual entered through the front entryway directly behind a resident without ringing.",
                nodes=[
                    CausalNode(
                        step=1,
                        event_id="node_res_entry",
                        timestamp="Moments prior",
                        title="Resident Front Door Access",
                        description="Resident unlocked door and entered doorway.",
                        visitor_type="resident",
                        carrier="None",
                        icon="fa-key",
                        status="normal"
                    ),
                    CausalNode(
                        step=2,
                        event_id=tailgate_event.get("event_id", "tg_1"),
                        timestamp=tailgate_event.get("created_at", "")[:16],
                        title="Close Follow-In Detected",
                        description=tailgate_event.get("summary", "Stranger slipped through open door"),
                        visitor_type="unknown",
                        carrier="None",
                        icon="fa-user-secret",
                        status="conclusion"
                    )
                ],
                proactive_actions=[
                    ProactiveAction(
                        action_id="act_lockdown_home",
                        label="Lock Smart Door Deadbolts",
                        action_type="device_control",
                        severity="critical",
                        description="Command smart locks to immediately engage deadbolts."
                    )
                ]
            ))

        # 4. Standard Lingering Chain (if no theft, but lingering)
        if delivery_event and not theft_event and not swap_event:
            try:
                del_dt = datetime.fromisoformat(delivery_event["created_at"].replace("Z", "+00:00"))
                el_h = (datetime.now(timezone.utc) - del_dt).total_seconds() / 3600.0
            except Exception:
                el_h = 5.0

            if el_h >= 2.0:
                narratives.append(CausalNarrative(
                    narrative_id="narrative_linger_001",
                    narrative_type="lingering_delivery",
                    title="Delivery Lifecycle & Lingering Evidence Chain",
                    verdict="PACKAGE SAFE BUT VULNERABLE",
                    severity="moderate",
                    confidence=0.96,
                    summary=f"Package was delivered at {delivery_event.get('created_at', '')[:16]} UTC and has remained undisturbed on porch for {el_h:.1f} hours.",
                    nodes=[
                        CausalNode(
                            step=1,
                            event_id=delivery_event.get("event_id", "del_1"),
                            timestamp=delivery_event.get("created_at", "")[:16],
                            title="Package Deposited by Courier",
                            description=f"{delivery_event.get('uniform_carrier', 'Amazon')} placed box on mat.",
                            visitor_type="courier",
                            carrier=delivery_event.get("uniform_carrier", "Amazon"),
                            icon="fa-box",
                            status="normal"
                        ),
                        CausalNode(
                            step=2,
                            event_id="linger_step_2",
                            timestamp="Currently Outside",
                            title=f"Uncollected for {el_h:.1f} Hours",
                            description="No pickup or door retrieval event recorded in episodic memory.",
                            visitor_type="system",
                            carrier="None",
                            icon="fa-triangle-exclamation",
                            status="trigger"
                        )
                    ],
                    proactive_actions=[
                        ProactiveAction(
                            action_id="act_alexa_announce",
                            label="Broadcast Chime on Alexa",
                            action_type="chime",
                            severity="moderate",
                            description="Broadcast reminder to smart speakers throughout the house."
                        ),
                        ProactiveAction(
                            action_id="act_push_notify",
                            label="Send Push Notification",
                            action_type="push",
                            severity="moderate",
                            description="Deliver push notification to resident phone."
                        )
                    ]
                ))

        return narratives
