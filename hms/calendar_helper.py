import os
import datetime
from django.conf import settings
from django.urls import reverse
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from .models import GoogleCredential
import logging

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/calendar.events']

def get_oauth_flow(request):
    """
    Constructs the Google OAuth Flow object.
    """
    client_id = os.getenv('GOOGLE_CLIENT_ID')
    client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
    
    # Check if credentials are set
    if not client_id or not client_secret or 'your_google_client_id' in client_id:
        logger.warning("Google OAuth credentials are not set in the environment variables.")
        return None

    client_config = {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs"
        }
    }
    
    # Construct redirect URI
    redirect_uri = request.build_absolute_uri(reverse('google_callback'))
    
    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )
    return flow

def get_calendar_service(user):
    """
    Returns a Google Calendar API service object for the given user,
    automatically refreshing the access token if it is expired.
    """
    try:
        cred_model = GoogleCredential.objects.get(user=user)
    except GoogleCredential.DoesNotExist:
        return None

    creds_dict = cred_model.to_dict()
    # Reconstruct google auth Credentials object
    # expiry is saved as ISO string, convert back to datetime
    expiry = None
    if creds_dict['expiry']:
        # Django timezone is offset-aware or native, google credentials expects datetime
        # Parse it back
        try:
            # handle formats like 2026-06-27T02:08:50.000Z or +00:00
            dt_str = creds_dict['expiry'].split('+')[0].split('.')[0]
            expiry = datetime.datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S")
        except Exception:
            expiry = datetime.datetime.now()

    creds = Credentials(
        token=creds_dict['token'],
        refresh_token=creds_dict['refresh_token'],
        token_uri=creds_dict['token_uri'],
        client_id=creds_dict['client_id'],
        client_secret=creds_dict['client_secret'],
        scopes=creds_dict['scopes'],
        expiry=expiry
    )

    # Check if expired and refresh
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            # Save refreshed credentials
            GoogleCredential.from_credentials(user, creds)
        except Exception as e:
            logger.error(f"Failed to refresh Google OAuth token for user {user.username}: {e}")
            return None

    try:
        service = build('calendar', 'v3', credentials=creds)
        return service
    except Exception as e:
        logger.error(f"Failed to build Google Calendar service for user {user.username}: {e}")
        return None

def create_appointment_events(booking):
    """
    Creates a Google Calendar event for both the patient and the doctor.
    """
    slot = booking.slot
    doctor = slot.doctor
    patient = booking.patient

    # Parse slot time and dates into ISO strings
    # Combine date and time
    start_dt = datetime.datetime.combine(slot.date, slot.start_time)
    end_dt = datetime.datetime.combine(slot.date, slot.end_time)

    # Convert to ISO format (assuming UTC or local timezone, here we specify local offset or Z)
    # We can format it as ISO standard: YYYY-MM-DDTHH:MM:SS
    # Let's assume standard local/UTC time format. We'll use the timezone setting.
    # Since we are local, let's format it simply with local timezone or without timezone if naive
    start_iso = start_dt.isoformat()
    end_iso = end_dt.isoformat()

    # Time zone representation
    time_zone = 'Asia/Kolkata'  # matching user's locale offset, or UTC

    # Event for Doctor: 'Appointment with <PatientName>'
    doctor_event_body = {
        'summary': f"Appointment with {patient.get_full_name() or patient.username}",
        'description': f"HMS Appointment booking ID: {booking.id}. Patient contact: {patient.email}",
        'start': {
            'dateTime': start_iso,
            'timeZone': time_zone,
        },
        'end': {
            'dateTime': end_iso,
            'timeZone': time_zone,
        },
    }

    # Event for Patient: 'Appointment with Dr. <DoctorName>'
    patient_event_body = {
        'summary': f"Appointment with Dr. {doctor.get_full_name() or doctor.username}",
        'description': f"HMS Appointment booking ID: {booking.id}. Doctor contact: {doctor.email}",
        'start': {
            'dateTime': start_iso,
            'timeZone': time_zone,
        },
        'end': {
            'dateTime': end_iso,
            'timeZone': time_zone,
        },
    }

    # Try creating doctor event
    doctor_service = get_calendar_service(doctor)
    if doctor_service:
        try:
            event = doctor_service.events().insert(calendarId='primary', body=doctor_event_body).execute()
            booking.google_event_id_doctor = event.get('id')
            logger.info(f"Created event on Doctor's calendar: {event.get('id')}")
        except Exception as e:
            logger.error(f"Error creating doctor calendar event: {e}")

    # Try creating patient event
    patient_service = get_calendar_service(patient)
    if patient_service:
        try:
            event = patient_service.events().insert(calendarId='primary', body=patient_event_body).execute()
            booking.google_event_id_patient = event.get('id')
            logger.info(f"Created event on Patient's calendar: {event.get('id')}")
        except Exception as e:
            logger.error(f"Error creating patient calendar event: {e}")

    # Save event IDs if created
    booking.save()
