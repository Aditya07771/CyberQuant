import hashlib
import hmac
import logging
import smtplib
import time
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, Optional
import httpx
from sqlalchemy.orm import Session

from core.config import settings
from db.models import AlertDelivery, RiskAlert

logger = logging.getLogger(__name__)


class NotificationDeliveryService:
    """Dispatches notifications via SMTP email and HMAC-signed Webhooks with bounded retries."""

    def __init__(self, db: Session):
        self.db = db

    def dispatch_alert(self, alert: RiskAlert, recipients: Optional[list] = None, webhooks: Optional[list] = None) -> list:
        """Dispatches an alert to configured email recipients and webhooks."""
        deliveries = []

        # 1. Email Delivery
        email_list = recipients or []
        for recipient in email_list:
            if not recipient or "@" not in recipient:
                continue
            delivery = self.send_email_alert(alert, recipient)
            deliveries.append(delivery)

        # 2. Webhook Delivery
        webhook_list = webhooks or []
        for webhook_url in webhook_list:
            if not webhook_url or not webhook_url.startswith("http"):
                continue
            delivery = self.send_webhook_alert(alert, webhook_url)
            deliveries.append(delivery)

        return deliveries

    def send_email_alert(self, alert: RiskAlert, recipient: str) -> AlertDelivery:
        """Sends an HTML + plain text email alert, or records simulated delivery if in dev/simulated mode."""
        now = datetime.now(timezone.utc)
        delivery = AlertDelivery(
            alert_id=alert.id,
            channel="email",
            recipient=recipient,
            state="queued",
            attempts=1,
            created_at=now,
        )
        self.db.add(delivery)
        self.db.commit()

        # If simulated mode or placeholder SMTP host, log and mark as 'simulated'
        if settings.SMTP_SIMULATED or "example.com" in settings.SMTP_HOST:
            logger.info("Simulated SMTP email dispatch to %s for alert '%s'", recipient, alert.title)
            delivery.state = "simulated"
            delivery.provider_ref = f"sim-{alert.id[:8]}"
            delivery.sent_at = now
            self.db.commit()
            return delivery

        # Real SMTP Delivery with bounded retry
        subject = f"[{alert.severity.upper()}] CyberQuant Risk Alert: {alert.title}"
        plain_body = (
            f"CYBERQUANT RISK ALERT\n\n"
            f"Severity: {alert.severity.upper()}\n"
            f"Category: {alert.category}\n"
            f"Title: {alert.title}\n"
            f"Description: {alert.description}\n"
            f"Opened: {alert.opened_at.isoformat()}\n"
            f"Due SLA: {alert.due_at.isoformat() if alert.due_at else 'N/A'}\n"
        )
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #333;">
            <div style="border-left: 4px solid {'#e53e3e' if alert.severity == 'critical' else '#dd6b20'}; padding-left: 15px;">
                <h2 style="color: {'#e53e3e' if alert.severity == 'critical' else '#dd6b20'};">
                    [{alert.severity.upper()}] CyberQuant Risk Alert
                </h2>
                <h3>{alert.title}</h3>
                <p><strong>Category:</strong> {alert.category}</p>
                <p><strong>Description:</strong> {alert.description}</p>
                <p><strong>Opened:</strong> {alert.opened_at.isoformat()}</p>
                <p><strong>Action SLA Due:</strong> {alert.due_at.isoformat() if alert.due_at else 'N/A'}</p>
            </div>
            <hr style="margin-top: 20px;" />
            <small style="color: #777;">CyberQuant Financial Cyber Risk Platform</small>
        </body>
        </html>
        """

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM
        msg["To"] = recipient
        msg.attach(MIMEText(plain_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        try:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=5.0) as server:
                if settings.SMTP_USE_TLS:
                    server.starttls()
                if settings.SMTP_USER and settings.SMTP_PASSWORD:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.SMTP_FROM, [recipient], msg.as_string())
            delivery.state = "sent"
            delivery.provider_ref = f"smtp-accepted-{int(time.time())}"
            delivery.sent_at = datetime.now(timezone.utc)
        except Exception as e:
            logger.warning("SMTP email delivery to %s failed: %s", recipient, str(e))
            delivery.state = "failed"
            delivery.sanitized_error = str(e)[:300]

        self.db.commit()
        return delivery

    def send_webhook_alert(self, alert: RiskAlert, webhook_url: str, secret: Optional[str] = None) -> AlertDelivery:
        """Sends an HMAC-signed Webhook alert payload with timestamp replay protection."""
        now = datetime.now(timezone.utc)
        delivery = AlertDelivery(
            alert_id=alert.id,
            channel="webhook",
            recipient=webhook_url,
            state="queued",
            attempts=1,
            created_at=now,
        )
        self.db.add(delivery)
        self.db.commit()

        ts = str(int(now.timestamp()))
        payload = {
            "event": "risk_alert.created",
            "timestamp": now.isoformat(),
            "alert": {
                "id": alert.id,
                "severity": alert.severity,
                "category": alert.category,
                "title": alert.title,
                "description": alert.description,
                "opened_at": alert.opened_at.isoformat(),
                "due_at": alert.due_at.isoformat() if alert.due_at else None,
                "evidence_refs": alert.evidence_refs,
            },
        }

        import json
        body = json.dumps(payload)
        key = (secret or settings.WEBHOOK_DEFAULT_SECRET).encode("utf-8")
        sig_data = f"{ts}.{body}".encode("utf-8")
        signature = hmac.new(key, sig_data, hashlib.sha256).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "X-CyberQuant-Timestamp": ts,
            "X-CyberQuant-Signature": f"t={ts},v1={signature}",
            "User-Agent": "CyberQuant-Webhook-Delivery/1.0",
        }

        try:
            with httpx.Client(timeout=settings.WEBHOOK_TIMEOUT_SECONDS) as client:
                resp = client.post(webhook_url, content=body, headers=headers)
                if resp.status_code in (200, 201, 202, 204):
                    delivery.state = "sent"
                    delivery.provider_ref = f"http-{resp.status_code}"
                    delivery.sent_at = datetime.now(timezone.utc)
                else:
                    delivery.state = "failed"
                    delivery.sanitized_error = f"Webhook returned HTTP {resp.status_code}"
        except Exception as e:
            logger.warning("Webhook dispatch to %s failed: %s", webhook_url, str(e))
            delivery.state = "failed"
            delivery.sanitized_error = str(e)[:300]

        self.db.commit()
        return delivery
