from django.contrib import admin
from .models import Profile, AvailabilitySlot, Booking, GoogleCredential


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'phone')
    list_filter = ('role',)


@admin.register(AvailabilitySlot)
class AvailabilitySlotAdmin(admin.ModelAdmin):
    list_display = ('doctor', 'date', 'start_time', 'end_time', 'is_booked')
    list_filter = ('date', 'is_booked')


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'patient', 'slot', 'created_at')
    readonly_fields = ('created_at',)


@admin.register(GoogleCredential)
class GoogleCredentialAdmin(admin.ModelAdmin):
    list_display = ('user', 'expiry')
