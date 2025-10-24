"""
Webhook handlers for email delivery tracking.
"""

import hashlib
import hmac
import json
import logging
from typing import Any, Dict

from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .services import track_email_event

logger = logging.getLogger(__name__)


def verify_webhook_signature(request, secret_key: str) -> bool:
    """
    Verify webhook signature for security.
    """
    if not secret_key:
        return True  # Skip verification if no secret configured

    signature = request.headers.get("X-Signature") or request.headers.get("Signature")
    if not signature:
        return False

    # Calculate expected signature
    body = request.body
    expected_signature = hmac.new(secret_key.encode("utf-8"), body, hashlib.sha256).hexdigest()

    # Compare signatures
    return hmac.compare_digest(signature, expected_signature)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(require_http_methods(["POST"]), name="dispatch")
class SendGridWebhookView(View):
    """
    Webhook handler for SendGrid email events.
    """

    def post(self, request):
        """Handle SendGrid webhook events"""
        try:
            # Verify signature if configured
            if hasattr(settings, "EMAIL_WEBHOOK_SECRET") and settings.EMAIL_WEBHOOK_SECRET:
                if not verify_webhook_signature(request, settings.EMAIL_WEBHOOK_SECRET):
                    logger.warning("Invalid webhook signature from SendGrid")
                    return HttpResponseBadRequest("Invalid signature")

            # Parse events
            events = json.loads(request.body)
            if not isinstance(events, list):
                events = [events]

            processed_count = 0

            for event in events:
                try:
                    self._process_sendgrid_event(event)
                    processed_count += 1
                except Exception as e:
                    logger.error(f"Failed to process SendGrid event: {str(e)}")

            logger.info(f"Processed {processed_count} SendGrid webhook events")

            return HttpResponse("OK")

        except json.JSONDecodeError:
            logger.error("Invalid JSON in SendGrid webhook")
            return HttpResponseBadRequest("Invalid JSON")
        except Exception as e:
            logger.error(f"SendGrid webhook error: {str(e)}")
            return HttpResponseBadRequest("Webhook processing failed")

    def _process_sendgrid_event(self, event: Dict[str, Any]):
        """Process a single SendGrid event"""
        event_type = event.get("event")
        message_id = event.get("sg_message_id")
        timestamp = event.get("timestamp")

        if not message_id or not event_type:
            logger.warning("SendGrid event missing required fields")
            return

        # Convert timestamp
        event_timestamp = None
        if timestamp:
            event_timestamp = timezone.datetime.fromtimestamp(timestamp, tz=timezone.utc)

        # Map SendGrid events to our status
        event_mapping = {
            "delivered": "delivered",
            "open": "opened",
            "click": "clicked",
            "bounce": "bounced",
            "dropped": "failed",
            "deferred": "failed",
            "blocked": "failed",
            "spamreport": "complained",
            "unsubscribe": "unsubscribed",
            "group_unsubscribe": "unsubscribed",
        }

        mapped_event = event_mapping.get(event_type)
        if mapped_event:
            # Extract additional data
            kwargs = {}
            if event_type == "bounce":
                kwargs["bounce_reason"] = event.get("reason", "")
            elif event_type in ["dropped", "deferred", "blocked"]:
                kwargs["error_message"] = event.get("reason", "")

            track_email_event(
                message_id=message_id, event_type=mapped_event, timestamp=event_timestamp, **kwargs
            )


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(require_http_methods(["POST"]), name="dispatch")
class MailgunWebhookView(View):
    """
    Webhook handler for Mailgun email events.
    """

    def post(self, request):
        """Handle Mailgun webhook events"""
        try:
            # Verify signature if configured
            if hasattr(settings, "EMAIL_WEBHOOK_SECRET") and settings.EMAIL_WEBHOOK_SECRET:
                if not self._verify_mailgun_signature(request):
                    logger.warning("Invalid webhook signature from Mailgun")
                    return HttpResponseBadRequest("Invalid signature")

            # Parse event data
            event_data = request.POST.dict()

            self._process_mailgun_event(event_data)

            logger.info("Processed Mailgun webhook event")

            return HttpResponse("OK")

        except Exception as e:
            logger.error(f"Mailgun webhook error: {str(e)}")
            return HttpResponseBadRequest("Webhook processing failed")

    def _verify_mailgun_signature(self, request) -> bool:
        """Verify Mailgun webhook signature"""
        token = request.POST.get("token", "")
        timestamp = request.POST.get("timestamp", "")
        signature = request.POST.get("signature", "")

        if not all([token, timestamp, signature]):
            return False

        # Calculate expected signature
        expected_signature = hmac.new(
            settings.EMAIL_WEBHOOK_SECRET.encode("utf-8"),
            f"{timestamp}{token}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(signature, expected_signature)

    def _process_mailgun_event(self, event_data: Dict[str, str]):
        """Process a single Mailgun event"""
        event_type = event_data.get("event")
        message_id = event_data.get("Message-Id")
        timestamp = event_data.get("timestamp")

        if not message_id or not event_type:
            logger.warning("Mailgun event missing required fields")
            return

        # Convert timestamp
        event_timestamp = None
        if timestamp:
            try:
                event_timestamp = timezone.datetime.fromtimestamp(float(timestamp), tz=timezone.utc)
            except (ValueError, TypeError):
                pass

        # Map Mailgun events to our status
        event_mapping = {
            "delivered": "delivered",
            "opened": "opened",
            "clicked": "clicked",
            "bounced": "bounced",
            "dropped": "failed",
            "complained": "complained",
            "unsubscribed": "unsubscribed",
        }

        mapped_event = event_mapping.get(event_type)
        if mapped_event:
            # Extract additional data
            kwargs = {}
            if event_type == "bounced":
                kwargs["bounce_reason"] = event_data.get("reason", "")
            elif event_type == "dropped":
                kwargs["error_message"] = event_data.get("reason", "")

            track_email_event(
                message_id=message_id, event_type=mapped_event, timestamp=event_timestamp, **kwargs
            )


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(require_http_methods(["POST"]), name="dispatch")
class PostmarkWebhookView(View):
    """
    Webhook handler for Postmark email events.
    """

    def post(self, request):
        """Handle Postmark webhook events"""
        try:
            # Parse event data
            event_data = json.loads(request.body)

            self._process_postmark_event(event_data)

            logger.info("Processed Postmark webhook event")

            return HttpResponse("OK")

        except json.JSONDecodeError:
            logger.error("Invalid JSON in Postmark webhook")
            return HttpResponseBadRequest("Invalid JSON")
        except Exception as e:
            logger.error(f"Postmark webhook error: {str(e)}")
            return HttpResponseBadRequest("Webhook processing failed")

    def _process_postmark_event(self, event_data: Dict[str, Any]):
        """Process a single Postmark event"""
        record_type = event_data.get("RecordType")
        message_id = event_data.get("MessageID")
        received_at = event_data.get("ReceivedAt")

        if not message_id or not record_type:
            logger.warning("Postmark event missing required fields")
            return

        # Convert timestamp
        event_timestamp = None
        if received_at:
            try:
                event_timestamp = timezone.datetime.fromisoformat(
                    received_at.replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                pass

        # Map Postmark events to our status
        event_mapping = {
            "Delivery": "delivered",
            "Open": "opened",
            "Click": "clicked",
            "Bounce": "bounced",
            "SpamComplaint": "complained",
            "SubscriptionChange": "unsubscribed",
        }

        mapped_event = event_mapping.get(record_type)
        if mapped_event:
            # Extract additional data
            kwargs = {}
            if record_type == "Bounce":
                kwargs["bounce_reason"] = event_data.get("Description", "")

            track_email_event(
                message_id=str(message_id),
                event_type=mapped_event,
                timestamp=event_timestamp,
                **kwargs,
            )


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(require_http_methods(["POST"]), name="dispatch")
class SESWebhookView(View):
    """
    Webhook handler for Amazon SES email events via SNS.
    """

    def post(self, request):
        """Handle SES webhook events via SNS"""
        try:
            # Parse SNS message
            sns_data = json.loads(request.body)

            # Handle SNS subscription confirmation
            if sns_data.get("Type") == "SubscriptionConfirmation":
                logger.info("SNS subscription confirmation received")
                return HttpResponse("OK")

            # Handle SNS notification
            if sns_data.get("Type") == "Notification":
                message = json.loads(sns_data.get("Message", "{}"))
                self._process_ses_event(message)

            logger.info("Processed SES webhook event")

            return HttpResponse("OK")

        except json.JSONDecodeError:
            logger.error("Invalid JSON in SES webhook")
            return HttpResponseBadRequest("Invalid JSON")
        except Exception as e:
            logger.error(f"SES webhook error: {str(e)}")
            return HttpResponseBadRequest("Webhook processing failed")

    def _process_ses_event(self, event_data: Dict[str, Any]):
        """Process a single SES event"""
        event_type = event_data.get("eventType")
        mail = event_data.get("mail", {})
        message_id = mail.get("messageId")
        timestamp = event_data.get("timestamp")

        if not message_id or not event_type:
            logger.warning("SES event missing required fields")
            return

        # Convert timestamp
        event_timestamp = None
        if timestamp:
            try:
                event_timestamp = timezone.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        # Map SES events to our status
        event_mapping = {
            "send": "sent",
            "delivery": "delivered",
            "open": "opened",
            "click": "clicked",
            "bounce": "bounced",
            "complaint": "complained",
        }

        mapped_event = event_mapping.get(event_type)
        if mapped_event:
            # Extract additional data
            kwargs = {}
            if event_type == "bounce":
                bounce = event_data.get("bounce", {})
                kwargs["bounce_reason"] = bounce.get("bounceSubType", "")
            elif event_type == "complaint":
                complaint = event_data.get("complaint", {})
                kwargs["error_message"] = complaint.get("complaintFeedbackType", "")

            track_email_event(
                message_id=message_id, event_type=mapped_event, timestamp=event_timestamp, **kwargs
            )
