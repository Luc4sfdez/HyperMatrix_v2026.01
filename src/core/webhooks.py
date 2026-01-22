"""
HyperMatrix v2026 - Webhooks Manager
Sends notifications about scan events to external services.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Dict, Optional, Any, Callable
from collections import deque

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

logger = logging.getLogger(__name__)


class WebhookEvent(str, Enum):
    """Webhook event types."""
    SCAN_STARTED = "scan.started"
    SCAN_PROGRESS = "scan.progress"
    SCAN_COMPLETED = "scan.completed"
    SCAN_FAILED = "scan.failed"
    MERGE_REQUESTED = "merge.requested"
    MERGE_COMPLETED = "merge.completed"
    MERGE_FAILED = "merge.failed"
    BATCH_STARTED = "batch.started"
    BATCH_COMPLETED = "batch.completed"
    DEAD_CODE_DETECTED = "analysis.dead_code"
    CLONES_DETECTED = "analysis.clones"
    HIGH_SIMILARITY = "analysis.high_similarity"


@dataclass
class WebhookConfig:
    """Configuration for a webhook endpoint."""
    id: str
    url: str
    events: List[WebhookEvent]
    secret: Optional[str] = None
    enabled: bool = True
    retry_count: int = 3
    timeout_seconds: int = 30
    headers: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WebhookDelivery:
    """Record of a webhook delivery attempt."""
    id: str
    webhook_id: str
    event: WebhookEvent
    payload: Dict[str, Any]
    timestamp: datetime
    status_code: Optional[int] = None
    response: Optional[str] = None
    success: bool = False
    attempts: int = 0
    error: Optional[str] = None
    duration_ms: Optional[float] = None


@dataclass
class WebhookPayload:
    """Standard webhook payload structure."""
    event: str
    timestamp: str
    delivery_id: str
    data: Dict[str, Any]


class WebhookManager:
    """
    Manages webhook registrations and deliveries.

    Features:
    - Register multiple webhook endpoints
    - Filter events per endpoint
    - Secure payloads with HMAC signatures
    - Retry failed deliveries
    - Track delivery history
    """

    def __init__(self, config_path: Optional[str] = None):
        self.webhooks: Dict[str, WebhookConfig] = {}
        self.delivery_history: deque = deque(maxlen=1000)
        self.config_path = config_path
        self._delivery_callbacks: List[Callable] = []

        if config_path:
            self._load_config(config_path)

    def register_webhook(self, config: WebhookConfig) -> bool:
        """Register a new webhook endpoint."""
        if not config.url or not config.events:
            logger.warning(f"Invalid webhook config: {config.id}")
            return False

        self.webhooks[config.id] = config
        logger.info(f"Registered webhook: {config.id} -> {config.url}")
        return True

    def unregister_webhook(self, webhook_id: str) -> bool:
        """Remove a webhook endpoint."""
        if webhook_id in self.webhooks:
            del self.webhooks[webhook_id]
            logger.info(f"Unregistered webhook: {webhook_id}")
            return True
        return False

    def enable_webhook(self, webhook_id: str) -> bool:
        """Enable a webhook."""
        if webhook_id in self.webhooks:
            self.webhooks[webhook_id].enabled = True
            return True
        return False

    def disable_webhook(self, webhook_id: str) -> bool:
        """Disable a webhook."""
        if webhook_id in self.webhooks:
            self.webhooks[webhook_id].enabled = False
            return True
        return False

    async def send_event(
        self,
        event: WebhookEvent,
        data: Dict[str, Any],
        sync: bool = False
    ) -> List[WebhookDelivery]:
        """
        Send an event to all registered webhooks that listen for it.

        Args:
            event: The event type
            data: Event data payload
            sync: If True, wait for all deliveries to complete

        Returns:
            List of delivery records
        """
        if not AIOHTTP_AVAILABLE:
            logger.warning("aiohttp not available, webhooks disabled")
            return []

        # Find webhooks that listen for this event
        target_webhooks = [
            wh for wh in self.webhooks.values()
            if wh.enabled and event in wh.events
        ]

        if not target_webhooks:
            return []

        # Create delivery tasks
        tasks = [
            self._deliver_webhook(wh, event, data)
            for wh in target_webhooks
        ]

        if sync:
            deliveries = await asyncio.gather(*tasks, return_exceptions=True)
            return [d for d in deliveries if isinstance(d, WebhookDelivery)]
        else:
            # Fire and forget
            for task in tasks:
                asyncio.create_task(task)
            return []

    def send_event_sync(self, event: WebhookEvent, data: Dict[str, Any]) -> None:
        """Synchronous wrapper for send_event (fire and forget)."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.send_event(event, data))
            else:
                loop.run_until_complete(self.send_event(event, data, sync=True))
        except RuntimeError:
            # No event loop
            asyncio.run(self.send_event(event, data, sync=True))

    async def _deliver_webhook(
        self,
        webhook: WebhookConfig,
        event: WebhookEvent,
        data: Dict[str, Any]
    ) -> WebhookDelivery:
        """Deliver a webhook with retries."""
        delivery_id = self._generate_delivery_id()
        timestamp = datetime.utcnow()

        payload = {
            "event": event.value,
            "timestamp": timestamp.isoformat() + "Z",
            "delivery_id": delivery_id,
            "data": data,
        }

        delivery = WebhookDelivery(
            id=delivery_id,
            webhook_id=webhook.id,
            event=event,
            payload=payload,
            timestamp=timestamp,
        )

        headers = {
            "Content-Type": "application/json",
            "X-HyperMatrix-Event": event.value,
            "X-HyperMatrix-Delivery": delivery_id,
            **webhook.headers,
        }

        # Add signature if secret is configured
        if webhook.secret:
            payload_bytes = json.dumps(payload).encode('utf-8')
            signature = hmac.new(
                webhook.secret.encode('utf-8'),
                payload_bytes,
                hashlib.sha256
            ).hexdigest()
            headers["X-HyperMatrix-Signature"] = f"sha256={signature}"

        # Attempt delivery with retries
        for attempt in range(webhook.retry_count):
            delivery.attempts = attempt + 1
            start_time = time.time()

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        webhook.url,
                        json=payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=webhook.timeout_seconds)
                    ) as response:
                        delivery.status_code = response.status
                        delivery.response = await response.text()
                        delivery.duration_ms = (time.time() - start_time) * 1000

                        if 200 <= response.status < 300:
                            delivery.success = True
                            logger.info(
                                f"Webhook delivered: {webhook.id} -> {event.value} "
                                f"(status={response.status})"
                            )
                            break
                        else:
                            delivery.error = f"HTTP {response.status}: {delivery.response[:200]}"

            except asyncio.TimeoutError:
                delivery.error = "Request timed out"
                delivery.duration_ms = (time.time() - start_time) * 1000
            except aiohttp.ClientError as e:
                delivery.error = str(e)
                delivery.duration_ms = (time.time() - start_time) * 1000
            except Exception as e:
                delivery.error = str(e)
                delivery.duration_ms = (time.time() - start_time) * 1000
                logger.exception(f"Webhook delivery error: {webhook.id}")

            if attempt < webhook.retry_count - 1:
                # Exponential backoff
                await asyncio.sleep(2 ** attempt)

        # Record delivery
        self.delivery_history.append(delivery)

        # Notify callbacks
        for callback in self._delivery_callbacks:
            try:
                callback(delivery)
            except Exception:
                pass

        return delivery

    def get_delivery_history(
        self,
        webhook_id: Optional[str] = None,
        event: Optional[WebhookEvent] = None,
        limit: int = 100
    ) -> List[WebhookDelivery]:
        """Get webhook delivery history with optional filters."""
        history = list(self.delivery_history)

        if webhook_id:
            history = [d for d in history if d.webhook_id == webhook_id]

        if event:
            history = [d for d in history if d.event == event]

        return history[-limit:]

    def get_webhook_stats(self, webhook_id: str) -> Dict[str, Any]:
        """Get statistics for a webhook."""
        deliveries = [d for d in self.delivery_history if d.webhook_id == webhook_id]

        if not deliveries:
            return {
                "total_deliveries": 0,
                "success_rate": 0.0,
                "avg_duration_ms": 0.0,
            }

        successful = sum(1 for d in deliveries if d.success)
        durations = [d.duration_ms for d in deliveries if d.duration_ms]

        return {
            "total_deliveries": len(deliveries),
            "successful": successful,
            "failed": len(deliveries) - successful,
            "success_rate": successful / len(deliveries) if deliveries else 0.0,
            "avg_duration_ms": sum(durations) / len(durations) if durations else 0.0,
            "last_delivery": deliveries[-1].timestamp.isoformat() if deliveries else None,
        }

    def on_delivery(self, callback: Callable[[WebhookDelivery], None]):
        """Register a callback for delivery events."""
        self._delivery_callbacks.append(callback)

    def _generate_delivery_id(self) -> str:
        """Generate a unique delivery ID."""
        import uuid
        return str(uuid.uuid4())

    def _load_config(self, path: str):
        """Load webhook configuration from file."""
        config_path = Path(path)
        if not config_path.exists():
            return

        try:
            import yaml
            with open(config_path) as f:
                config = yaml.safe_load(f)

            for wh_config in config.get('webhooks', []):
                webhook = WebhookConfig(
                    id=wh_config['id'],
                    url=wh_config['url'],
                    events=[WebhookEvent(e) for e in wh_config.get('events', [])],
                    secret=wh_config.get('secret'),
                    enabled=wh_config.get('enabled', True),
                    retry_count=wh_config.get('retry_count', 3),
                    timeout_seconds=wh_config.get('timeout_seconds', 30),
                    headers=wh_config.get('headers', {}),
                )
                self.register_webhook(webhook)

        except Exception as e:
            logger.error(f"Failed to load webhook config: {e}")

    def save_config(self, path: str):
        """Save webhook configuration to file."""
        import yaml

        config = {
            'webhooks': [
                {
                    'id': wh.id,
                    'url': wh.url,
                    'events': [e.value for e in wh.events],
                    'secret': wh.secret,
                    'enabled': wh.enabled,
                    'retry_count': wh.retry_count,
                    'timeout_seconds': wh.timeout_seconds,
                    'headers': wh.headers,
                }
                for wh in self.webhooks.values()
            ]
        }

        with open(path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)

    def list_webhooks(self) -> List[Dict[str, Any]]:
        """List all registered webhooks."""
        return [
            {
                'id': wh.id,
                'url': wh.url,
                'events': [e.value for e in wh.events],
                'enabled': wh.enabled,
                'stats': self.get_webhook_stats(wh.id),
            }
            for wh in self.webhooks.values()
        ]


# Convenience functions for common events
def notify_scan_started(manager: WebhookManager, scan_id: str, path: str):
    """Notify that a scan has started."""
    manager.send_event_sync(WebhookEvent.SCAN_STARTED, {
        'scan_id': scan_id,
        'path': path,
    })


def notify_scan_completed(
    manager: WebhookManager,
    scan_id: str,
    files_analyzed: int,
    issues_found: int
):
    """Notify that a scan has completed."""
    manager.send_event_sync(WebhookEvent.SCAN_COMPLETED, {
        'scan_id': scan_id,
        'files_analyzed': files_analyzed,
        'issues_found': issues_found,
    })


def notify_merge_completed(
    manager: WebhookManager,
    files: List[str],
    target: str,
    success: bool
):
    """Notify that a merge has completed."""
    event = WebhookEvent.MERGE_COMPLETED if success else WebhookEvent.MERGE_FAILED
    manager.send_event_sync(event, {
        'files': files,
        'target': target,
        'success': success,
    })
