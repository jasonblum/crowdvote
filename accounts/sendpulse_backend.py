"""
SendPulse Email Backend for Django
Sends emails via SendPulse SMTP API
"""
import json
import requests
import logging
from django.core.mail.backends.base import BaseEmailBackend
from django.conf import settings
from django.core.mail import EmailMessage

logger = logging.getLogger(__name__)


class SendPulseEmailBackend(BaseEmailBackend):
    """
    Custom email backend for SendPulse API integration.
    
    Handles authentication, error cases, and rate limiting.
    """
    
    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.api_url = "https://api.sendpulse.com"
        self.access_token = None
    
    def get_access_token(self):
        """
        Get access token from SendPulse API using ID and Secret.
        """
        if self.access_token:
            return self.access_token
            
        try:
            url = f"{self.api_url}/oauth/access_token"
            data = {
                "grant_type": "client_credentials",
                "client_id": getattr(settings, 'SENDPULSE_API_ID', ''),
                "client_secret": getattr(settings, 'SENDPULSE_API_SECRET', '')
            }
            
            response = requests.post(url, data=data, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            self.access_token = result.get('access_token')
            
            if not self.access_token:
                logger.error("SendPulse: No access token received")
                return None
                
            logger.info("SendPulse: Successfully authenticated")
            return self.access_token
            
        except requests.exceptions.RequestException as e:
            logger.error(f"SendPulse authentication failed: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"SendPulse authentication response parsing failed: {e}")
            return None
    
    def send_messages(self, email_messages):
        """
        Send email messages via SendPulse API.
        
        Returns the number of successfully sent emails.
        """
        if not email_messages:
            return 0
            
        access_token = self.get_access_token()
        if not access_token:
            if not self.fail_silently:
                raise Exception("SendPulse: Authentication failed")
            return 0
        
        sent_count = 0
        
        for message in email_messages:
            try:
                success = self._send_single_message(message, access_token)
                if success:
                    sent_count += 1
                elif not self.fail_silently:
                    raise Exception(f"SendPulse: Failed to send email to {message.to}")
                    
            except Exception as e:
                logger.error(f"SendPulse: Error sending email: {e}")
                if not self.fail_silently:
                    raise
        
        return sent_count
    
    def _send_single_message(self, message, access_token):
        """
        Send a single email message via SendPulse API.
        """
        try:
            url = f"{self.api_url}/smtp/emails"
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            # Prepare email data according to SendPulse API format
            email_data = {
                "email": {
                    "html": message.body if message.content_subtype == 'html' else None,
                    "text": message.body if message.content_subtype == 'plain' else None,
                    "subject": message.subject,
                    "from": {
                        "name": getattr(settings, 'SENDPULSE_FROM_NAME', 'CrowdVote'),
                        "email": message.from_email or getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@crowdvote.com')
                    },
                    "to": [{"email": email} for email in message.to]
                }
            }
            
            # Add plain text version if HTML is provided
            if message.content_subtype == 'html' and not email_data["email"]["text"]:
                # Basic HTML to text conversion
                import re
                text_body = re.sub(r'<[^>]+>', '', message.body)
                email_data["email"]["text"] = text_body.strip()
            
            response = requests.post(url, json=email_data, headers=headers, timeout=30)
            
            # Handle different response codes
            if response.status_code == 200:
                logger.info(f"SendPulse: Email sent successfully to {message.to}")
                return True
            elif response.status_code == 429:
                # Rate limit exceeded
                logger.warning("SendPulse: Rate limit exceeded (monthly email limit reached)")
                return False
            elif response.status_code == 401:
                # Authentication failed
                logger.error("SendPulse: Authentication failed - check API credentials")
                self.access_token = None  # Reset token
                return False
            else:
                # Other errors
                logger.error(f"SendPulse: API error {response.status_code}: {response.text}")
                return False
                
        except requests.exceptions.Timeout:
            logger.error("SendPulse: Request timeout")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"SendPulse: Request failed: {e}")
            return False
        except Exception as e:
            logger.error(f"SendPulse: Unexpected error: {e}")
            return False
