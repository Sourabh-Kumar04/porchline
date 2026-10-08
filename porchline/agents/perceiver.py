"""Perceiver Agent: Front-Door Multimodal VLM Perception Engine.

Role & Responsibility:
- Analyzes incoming Ring doorbell snapshot frames and webhook event metadata.
- Leverages Amazon Bedrock (Claude 3.5 Sonnet / Amazon Nova) or simulated VLM fallback.
- Extracts structured visual perception:
  - Visitor classification (courier, neighbor, resident, animal, unknown, vehicle)
  - Carrier uniform & logistics branding (Amazon, FedEx, UPS, USPS, None)
  - Object & parcel status (count, description, spatial placement, dimensions)
  - Micro-action classification (deposit parcel, grab parcel, ring chime, loiter, pass-by)
  - Confidence scoring and perceptual scene summary.
- Communicates perceptual events downstream into the DynamoDB event timeline.
"""

import logging
from typing import Dict, Any, Optional
from porchline.memory.bedrock_processor import BedrockVisionProcessor

logger = logging.getLogger("porchline.agents.perceiver")


class PerceiverAgent:
    """Agent responsible for raw multimodal perception and scene understanding."""

    def __init__(self, vision_processor: Optional[BedrockVisionProcessor] = None):
        self.processor = vision_processor or BedrockVisionProcessor()
        self.agent_name = "Perceiver"
        self.version = "2.0.0"

    @property
    def is_live(self) -> bool:
        """Indicate whether Amazon Bedrock live API is connected."""
        return getattr(self.processor, "is_live", False)

    def perceive(self, image_bytes: bytes, event_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Execute multimodal scene understanding and return standardized perception record."""
        logger.info(f"[{self.agent_name}] Parsing frame for event: {event_metadata.get('event_type')}")
        raw_analysis = self.processor.analyze_frame(image_bytes, event_metadata)

        # Standardize perception envelope
        perception = {
            "agent": self.agent_name,
            "agent_version": self.version,
            "provider": raw_analysis.get("provider", "aws_bedrock_simulated"),
            "model": raw_analysis.get("model", getattr(self.processor, "model_id", "claude-3-5-sonnet")),
            "visitor_type": raw_analysis.get("visitor_type", "unknown"),
            "uniform_carrier": raw_analysis.get("uniform_carrier", "None"),
            "action": raw_analysis.get("action", "activity detected at porch"),
            "parcel_detected": bool(raw_analysis.get("parcel_detected", False)),
            "parcel_count": int(raw_analysis.get("parcel_count", 0)),
            "parcel_description": raw_analysis.get("parcel_description", ""),
            "placement": raw_analysis.get("placement", "porch floor"),
            "summary": raw_analysis.get("summary", ""),
            "confidence": float(raw_analysis.get("confidence", 0.95)),
            "visual_cues": {
                "clothing": raw_analysis.get("clothing", ""),
                "motion_direction": raw_analysis.get("motion_direction", "approaching_door"),
                "handling_parcel": bool(raw_analysis.get("parcel_detected", False)),
            }
        }
        return perception
