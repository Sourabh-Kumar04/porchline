"""Episodic Memory Store backed by AWS DynamoDB (Single-Table Design).

Features:
- Partition Key: PK = DEVICE#<device_id>
- Sort Key: SK = EVENT#<timestamp>#<event_id>
- Global Secondary Index 1 (GSI1): GSI1PK = TYPE#<visitor_type>, GSI1SK = <timestamp>
- In-memory SQLite / dict fallback when AWS credentials are not configured or for local fast testing.
- Tracks lingering package anomalies (package delivered but no subsequent pickup recorded).
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("porchline.store")

TABLE_NAME = os.environ.get("PORCHLINE_TABLE_NAME", "PorchlineEpisodicEvents")

class DynamoDBEpisodicStore:
    def __init__(self, region: str = "us-east-1"):
        self.region = region
        self.is_live = False
        self.table = None
        self._local_records: List[Dict[str, Any]] = []

        aws_key = os.environ.get("AWS_ACCESS_KEY_ID")
        aws_secret = os.environ.get("AWS_SECRET_ACCESS_KEY")
        if aws_key and aws_secret and not aws_key.startswith("mock"):
            try:
                import boto3
                dynamodb = boto3.resource("dynamodb", region_name=self.region)
                self.table = dynamodb.Table(TABLE_NAME)
                # Test connectivity
                self.table.load()
                self.is_live = True
                logger.info(f"Connected to live AWS DynamoDB table: {TABLE_NAME}")
            except Exception as e:
                logger.warning(f"Could not connect to live DynamoDB ({e}), using in-memory mock store.")
                self.is_live = False
        else:
            logger.info("Using local in-memory DynamoDB-compatible episodic store.")

    def save_event(self, event_record: Dict[str, Any]) -> Dict[str, Any]:
        """Save structured episodic event."""
        device_id = event_record.get("device_id", "ring-cam-front-porch")
        ts = event_record.get("created_at") or datetime.now(timezone.utc).isoformat()
        event_id = event_record.get("event_id") or f"evt_{datetime.now(timezone.utc).timestamp()}"
        visitor_type = event_record.get("visitor_type", "unknown")

        item = {
            "PK": f"DEVICE#{device_id}",
            "SK": f"EVENT#{ts}#{event_id}",
            "GSI1PK": f"TYPE#{visitor_type}",
            "GSI1SK": ts,
            "device_id": device_id,
            "event_id": event_id,
            "created_at": ts,
            "event_type": event_record.get("event_type", "motion"),
            "visitor_type": visitor_type,
            "uniform_carrier": event_record.get("uniform_carrier", "None"),
            "action": event_record.get("action", ""),
            "parcel_detected": bool(event_record.get("parcel_detected", False)),
            "parcel_count": int(event_record.get("parcel_count", 0)),
            "parcel_description": event_record.get("parcel_description", ""),
            "placement": event_record.get("placement", ""),
            "summary": event_record.get("summary", ""),
            "confidence": float(event_record.get("confidence", 0.95)),
            "snapshot_data_url": event_record.get("snapshot_data_url", ""),
            "scenario_title": event_record.get("scenario_title", ""),
            "provider": event_record.get("provider", "local")
        }

        if self.is_live and self.table:
            try:
                self.table.put_item(Item=item)
            except Exception as e:
                logger.error(f"Failed to put item in DynamoDB: {e}")

        # Always save in local list for fast memory retrieval and fallback
        self._local_records.append(item)
        # Sort descending by timestamp
        self._local_records.sort(key=lambda x: x["created_at"], reverse=True)
        return item

    def get_timeline(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return events chronologically descending."""
        return self._local_records[:limit]

    def clear(self):
        """Clear local test records."""
        self._local_records = []
