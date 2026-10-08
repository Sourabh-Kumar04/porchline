"""Ingestion Service for Ring Partner API Webhooks.

Responsibilities:
1. Fast-Ack within Ring's 5s SLA.
2. Validate HMAC-SHA256 signature against shared secret.
3. Idempotent Deduplication by request_id.
4. Pass valid event downstream to Bedrock Vision Processor and DynamoDB Timeline.
"""

import hmac
import hashlib
import json
import logging
from typing import Dict, Any, Tuple, Optional
from datetime import datetime, timezone

logger = logging.getLogger("porchline.ingestion")

class WebhookVerifier:
    def __init__(self, secret: str):
        self.secret = secret

    def verify(self, payload_bytes: bytes, signature_header: Optional[str]) -> Tuple[bool, str]:
        if not signature_header:
            return False, "Missing X-Signature header"

        computed = hmac.new(self.secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
        # Clean hex comparison
        clean_sig = signature_header.strip()
        if clean_sig.startswith("sha256="):
            clean_sig = clean_sig[7:]

        if hmac.compare_digest(computed.lower(), clean_sig.lower()):
            return True, "Valid signature"
        return False, "Signature mismatch"

class EventDeduplicator:
    """Deduplication handler supporting DynamoDB conditional writes for multi-instance Lambdas
    with in-memory fallback for local development and fast testing."""
    def __init__(self, ttl_seconds: int = 3600, dynamo_store: Optional[Any] = None):
        self.ttl_seconds = ttl_seconds
        self.dynamo_store = dynamo_store
        self.seen: Dict[str, float] = {}

    def is_duplicate(self, request_id: str) -> bool:
        if not request_id:
            return False

        if self.dynamo_store and getattr(self.dynamo_store, "is_live", False) and getattr(self.dynamo_store, "table", None):
            return self._is_duplicate_dynamodb(request_id)

        return self._is_duplicate_local(request_id)

    def _is_duplicate_local(self, request_id: str) -> bool:
        now = datetime.now(timezone.utc).timestamp()
        # Clean expired
        expired = [k for k, v in self.seen.items() if now - v > self.ttl_seconds]
        for k in expired:
            del self.seen[k]

        if request_id in self.seen:
            return True
        self.seen[request_id] = now
        return False

    def _is_duplicate_dynamodb(self, request_id: str) -> bool:
        now = datetime.now(timezone.utc).timestamp()
        try:
            from botocore.exceptions import ClientError
            # Atomic conditional put: succeed only if PK does not exist
            self.dynamo_store.table.put_item(
                Item={
                    "PK": f"DEDUP#{request_id}",
                    "SK": f"DEDUP#{request_id}",
                    "request_id": request_id,
                    "ttl": int(now + self.ttl_seconds),
                },
                ConditionExpression="attribute_not_exists(PK)"
            )
            return False
        except Exception as e:
            from botocore.exceptions import ClientError
            if isinstance(e, ClientError) and e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return True
            logger.warning(f"DynamoDB conditional dedup check failed ({e}), falling back to local memory.")
            return self._is_duplicate_local(request_id)
