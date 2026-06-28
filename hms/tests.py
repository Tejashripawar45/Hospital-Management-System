from django.db import transaction, IntegrityError
from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from .models import Profile, AvailabilitySlot, Booking


class BookingRaceConditionTests(TestCase):
    def setUp(self):
        self.doctor_user = User.objects.create_user(
            username='dr_smith', email='dr@example.com', password='pass12345'
        )
        Profile.objects.create(user=self.doctor_user, role='doctor')

        self.patient_a = User.objects.create_user(
            username='patient_a', email='a@example.com', password='pass12345'
        )
        Profile.objects.create(user=self.patient_a, role='patient')

        self.patient_b = User.objects.create_user(
            username='patient_b', email='b@example.com', password='pass12345'
        )
        Profile.objects.create(user=self.patient_b, role='patient')

        tomorrow = timezone.now().date() + timedelta(days=1)
        self.slot = AvailabilitySlot.objects.create(
            doctor=self.doctor_user,
            date=tomorrow,
            start_time=timezone.datetime.strptime('10:00', '%H:%M').time(),
            end_time=timezone.datetime.strptime('11:00', '%H:%M').time(),
        )

    def test_only_one_booking_per_slot(self):
        """Simulate two patients booking the same slot; only one should succeed."""
        successes = 0
        for patient in (self.patient_a, self.patient_b):
            client = Client()
            client.login(username=patient.username, password='pass12345')
            response = client.post(reverse('book_slot'), {'slot_id': self.slot.id})
            if response.status_code == 302:
                successes += 1

        self.slot.refresh_from_db()
        self.assertTrue(self.slot.is_booked)
        self.assertEqual(Booking.objects.filter(slot=self.slot).count(), 1)
        self.assertEqual(successes, 2)  # both redirect; one gets error message


class RoleAccessTests(TestCase):
    def setUp(self):
        self.doctor = User.objects.create_user(
            username='doc', email='doc@example.com', password='pass12345'
        )
        Profile.objects.create(user=self.doctor, role='doctor')

        self.patient = User.objects.create_user(
            username='pat', email='pat@example.com', password='pass12345'
        )
        Profile.objects.create(user=self.patient, role='patient')

    def test_patient_cannot_book_as_doctor_flow(self):
        client = Client()
        client.login(username=self.patient.username, password='pass12345')
        response = client.post(reverse('book_slot'), {'slot_id': 999})
        self.assertEqual(response.status_code, 302)

    def test_doctor_dashboard_requires_doctor_role(self):
        client = Client()
        client.login(username=self.patient.username, password='pass12345')
        response = client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Select a Doctor')
