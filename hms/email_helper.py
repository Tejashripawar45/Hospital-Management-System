import os
import requests
import logging

logger = logging.getLogger(__name__)

def trigger_email_service(trigger_type, recipient, data=None):
    """
    Triggers the Serverless Email Service running locally.
    
    trigger_type: SIGNUP_WELCOME or BOOKING_CONFIRMATION
    recipient: Recipient email address
    data: Context data for the email templates
    """
    if data is None:
        data = {}
        
    url = os.getenv('EMAIL_SERVICE_URL', 'http://localhost:3000/dev/send-email')
    
    payload = {
        'trigger_type': trigger_type,
        'recipient': recipient,
        'data': data
    }
    
    try:
        logger.info(f"Sending trigger {trigger_type} to {url} for recipient {recipient}")
        # Use a short timeout of 5 seconds to ensure we do not block user requests
        response = requests.post(url, json=payload, timeout=5)
        if response.status_code == 200:
            logger.info(f"Successfully triggered email service: {response.json()}")
            return True
        else:
            logger.warning(f"Email service returned status code {response.status_code}: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error communicating with local Serverless Email Service: {e}")
        return False
