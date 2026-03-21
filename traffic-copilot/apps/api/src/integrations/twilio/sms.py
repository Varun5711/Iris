"""
Twilio SMS integration — thin async wrapper around the sync Twilio REST client.

Uses asyncio.to_thread so the sync HTTP call doesn't block the event loop.
Gracefully degrades when Twilio credentials are not configured.
"""

from __future__ import annotations

import asyncio
import structlog

from src.core.config import settings

logger = structlog.get_logger(__name__)


def _send_sms_sync(to: str, message: str) -> dict:
    """Blocking Twilio send — called via asyncio.to_thread."""
    try:
        from twilio.rest import Client  # type: ignore[import-untyped]
    except ImportError:
        return {"sent": False, "error": "twilio package not installed"}

    account_sid = settings.twilio_account_sid
    auth_token = settings.twilio_auth_token
    from_number = settings.twilio_from_number

    if not account_sid or not auth_token:
        logger.warning("sms: Twilio credentials not configured — skipping SMS")
        return {"sent": False, "error": "Twilio credentials not configured"}

    try:
        client = Client(account_sid, auth_token)

        # Auto-discover from_number if not configured.
        if not from_number:
            numbers = client.incoming_phone_numbers.list(limit=1)
            if not numbers:
                return {"sent": False, "error": "No Twilio phone numbers found on account"}
            from_number = numbers[0].phone_number
            logger.info("sms: using auto-discovered from_number", from_number=from_number)

        msg = client.messages.create(body=message, from_=from_number, to=to)
        logger.info("sms: sent", to=to, sid=msg.sid)
        return {"sent": True, "sid": msg.sid, "to": to}
    except Exception as exc:
        logger.warning("sms: Twilio send failed", to=to, error=str(exc))
        return {"sent": False, "error": str(exc)}


async def send_sms(to: str, message: str) -> dict:
    """Async Twilio SMS send. Never raises — returns error dict on failure."""
    return await asyncio.to_thread(_send_sms_sync, to, message)
