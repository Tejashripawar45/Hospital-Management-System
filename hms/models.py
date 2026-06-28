from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime

class Profile(models.Model):
    ROLE_CHOICES = (
        ('doctor', 'Doctor'),
        ('patient', 'Patient'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    phone = models.CharField(max_length=15, blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} ({self.role})"

class AvailabilitySlot(models.Model):
    doctor = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'profile__role': 'doctor'}, related_name='slots')
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_booked = models.BooleanField(default=False)

    class Meta:
        unique_together = ('doctor', 'date', 'start_time', 'end_time')
        ordering = ['date', 'start_time']

    def __str__(self):
        return f"Dr. {self.doctor.last_name or self.doctor.username}: {self.date} {self.start_time}-{self.end_time} ({'Booked' if self.is_booked else 'Available'})"

class Booking(models.Model):
    patient = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'profile__role': 'patient'}, related_name='bookings')
    slot = models.OneToOneField(AvailabilitySlot, on_delete=models.CASCADE, related_name='booking')
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Store Google Calendar Event IDs if events were created
    google_event_id_patient = models.CharField(max_length=255, blank=True, null=True)
    google_event_id_doctor = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"Booking {self.id}: {self.patient.username} with Dr. {self.slot.doctor.username} at {self.slot.date} {self.slot.start_time}"

class GoogleCredential(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='google_credential')
    token = models.TextField()
    refresh_token = models.TextField(null=True, blank=True)
    token_uri = models.CharField(max_length=255)
    client_id = models.CharField(max_length=255)
    client_secret = models.CharField(max_length=255)
    scopes = models.TextField() # Space-separated list of scopes
    expiry = models.DateTimeField()

    def to_dict(self):
        return {
            'token': self.token,
            'refresh_token': self.refresh_token,
            'token_uri': self.token_uri,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'scopes': self.scopes.split(' ') if self.scopes else [],
            'expiry': self.expiry.isoformat() if self.expiry else None
        }

    @classmethod
    def from_credentials(cls, user, creds):
        # Update or create from a google.oauth2.credentials.Credentials object
        obj, created = cls.objects.update_or_create(
            user=user,
            defaults={
                'token': creds.token,
                'refresh_token': creds.refresh_token or (cls.objects.get(user=user).refresh_token if cls.objects.filter(user=user).exists() else None),
                'token_uri': creds.token_uri,
                'client_id': creds.client_id,
                'client_secret': creds.client_secret,
                'scopes': ' '.join(creds.scopes),
                'expiry': creds.expiry
            }
        )
        return obj
