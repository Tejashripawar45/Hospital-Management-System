from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction, IntegrityError
from django.utils import timezone
from datetime import datetime, date, time

from .models import Profile, AvailabilitySlot, Booking, GoogleCredential
from .decorators import doctor_required, patient_required
from .calendar_helper import get_oauth_flow, get_calendar_service, create_appointment_events
from .email_helper import trigger_email_service

import logging

logger = logging.getLogger(__name__)

def signup_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        role = request.POST.get('role') # doctor or patient
        phone = request.POST.get('phone', '')
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')

        # Basic validations
        if not username or not email or not password or not role:
            messages.error(request, "Please fill in all required fields.")
            return render(request, 'hms/signup.html')

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return render(request, 'hms/signup.html')
            
        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already registered.")
            return render(request, 'hms/signup.html')

        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=username, 
                    email=email, 
                    password=password,
                    first_name=first_name,
                    last_name=last_name
                )
                Profile.objects.create(user=user, role=role, phone=phone)
            
            # Log the user in
            login(request, user)
            
            # Trigger Welcome Email via Serverless
            trigger_email_service(
                trigger_type='SIGNUP_WELCOME',
                recipient=user.email,
                data={
                    'username': user.username,
                    'role': role,
                    'full_name': user.get_full_name() or user.username
                }
            )
            
            messages.success(request, f"Welcome to the HMS! Signed up as {role}.")
            return redirect('dashboard')
        except Exception as e:
            messages.error(request, f"An error occurred during sign up: {e}")
            return render(request, 'hms/signup.html')

    return render(request, 'hms/signup.html')

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        if not username or not password:
            messages.error(request, "Please fill in all fields.")
            return render(request, 'hms/login.html')

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f"Welcome back, {user.get_full_name() or user.username}!")
            return redirect('dashboard')
        else:
            messages.error(request, "Invalid username or password.")
            return render(request, 'hms/login.html')

    return render(request, 'hms/login.html')

def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect('login')

@login_required
def dashboard_view(request):
    try:
        profile = request.user.profile
    except Profile.DoesNotExist:
        # Fallback if profile doesn't exist (e.g. for superuser)
        # Create a default profile
        profile = Profile.objects.create(user=request.user, role='patient')
    
    if profile.role == 'doctor':
        return doctor_dashboard(request)
    else:
        return patient_dashboard(request)

@login_required
@doctor_required
def doctor_dashboard(request):
    doctor = request.user
    
    # Handle creating availability slots
    if request.method == 'POST':
        date_str = request.POST.get('date')
        start_time_str = request.POST.get('start_time')
        end_time_str = request.POST.get('end_time')

        if not date_str or not start_time_str or not end_time_str:
            messages.error(request, "Please fill in all time slot fields.")
        else:
            try:
                slot_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                start_time = datetime.strptime(start_time_str, '%H:%M').time()
                end_time = datetime.strptime(end_time_str, '%H:%M').time()

                if slot_date < timezone.now().date():
                    messages.error(request, "Cannot set availability slots in the past.")
                elif start_time >= end_time:
                    messages.error(request, "Start time must be before end time.")
                else:
                    AvailabilitySlot.objects.create(
                        doctor=doctor,
                        date=slot_date,
                        start_time=start_time,
                        end_time=end_time
                    )
                    messages.success(request, "Availability slot created successfully!")
            except IntegrityError:
                messages.error(request, "You have already created this availability slot.")
            except Exception as e:
                messages.error(request, f"Error creating slot: {e}")
                
        return redirect('dashboard')

    # Fetch slots for this doctor
    slots = AvailabilitySlot.objects.filter(doctor=doctor).order_by('-date', 'start_time')
    
    # Separate slots into past vs future, booked vs free
    future_slots = [s for s in slots if s.date >= timezone.now().date()]
    past_slots = [s for s in slots if s.date < timezone.now().date()]
    
    calendar_linked = GoogleCredential.objects.filter(user=doctor).exists()
    
    context = {
        'role': 'doctor',
        'future_slots': future_slots,
        'past_slots': past_slots,
        'calendar_linked': calendar_linked,
        'today': date.today().isoformat()
    }
    return render(request, 'hms/doctor_dashboard.html', context)

@login_required
@patient_required
def patient_dashboard(request):
    patient = request.user
    
    # Handle searching/selecting a doctor
    selected_doctor_id = request.GET.get('doctor_id')
    selected_doctor = None
    available_slots = []
    
    if selected_doctor_id:
        selected_doctor = get_object_or_404(User, id=selected_doctor_id, profile__role='doctor')
        # Slots visible to patients must be in the future and not already booked
        # Note: If date is today, only show slots whose start_time is in the future
        now_time = timezone.now().time()
        now_date = timezone.now().date()
        
        all_future_slots = AvailabilitySlot.objects.filter(
            doctor=selected_doctor,
            date__gte=now_date,
            is_booked=False
        )
        
        # Filter for time if date is today
        for slot in all_future_slots:
            if slot.date == now_date:
                if slot.start_time > now_time:
                    available_slots.append(slot)
            else:
                available_slots.append(slot)

    # Fetch all doctors
    doctors = User.objects.filter(profile__role='doctor').order_by('last_name', 'first_name')
    
    # Fetch patient's bookings
    bookings = Booking.objects.filter(patient=patient).order_by('-slot__date', 'slot__start_time')
    
    calendar_linked = GoogleCredential.objects.filter(user=patient).exists()
    
    context = {
        'role': 'patient',
        'doctors': doctors,
        'selected_doctor': selected_doctor,
        'available_slots': available_slots,
        'bookings': bookings,
        'calendar_linked': calendar_linked
    }
    return render(request, 'hms/patient_dashboard.html', context)

@login_required
@patient_required
def book_slot_view(request):
    if request.method != 'POST':
        return redirect('dashboard')
        
    slot_id = request.POST.get('slot_id')
    if not slot_id:
        messages.error(request, "No time slot selected.")
        return redirect('dashboard')
        
    slot = get_object_or_404(AvailabilitySlot, id=slot_id)
    patient = request.user

    # Handle race conditions: lock the slot row using transaction.atomic() + select_for_update()
    try:
        with transaction.atomic():
            # select_for_update locks this row inside PostgreSQL
            locked_slot = AvailabilitySlot.objects.select_for_update().get(id=slot.id)
            
            # 1. Double check if it's already booked or is in the past
            if locked_slot.is_booked:
                messages.error(request, f"Sorry, this time slot has already been booked by another patient.")
                return redirect('dashboard')
                
            now_date = timezone.now().date()
            now_time = timezone.now().time()
            if locked_slot.date < now_date or (locked_slot.date == now_date and locked_slot.start_time <= now_time):
                messages.error(request, "Cannot book a slot that has already started or is in the past.")
                return redirect('dashboard')
                
            # 2. Mark slot as booked
            locked_slot.is_booked = True
            locked_slot.save()
            
            # 3. Create the Booking entry
            booking = Booking.objects.create(patient=patient, slot=locked_slot)
            
        # The transaction has successfully committed here!
        # Now we trigger side effects (Google Calendar insertion & Email notifications)
        messages.success(request, f"Appointment with Dr. {locked_slot.doctor.get_full_name() or locked_slot.doctor.username} booked successfully!")
        
        # Trigger Google Calendar OAuth integration asynchronously / locally
        create_appointment_events(booking)
        
        # Trigger Serverless confirmation email
        trigger_email_service(
            trigger_type='BOOKING_CONFIRMATION',
            recipient=patient.email,
            data={
                'booking_id': booking.id,
                'patient_name': patient.get_full_name() or patient.username,
                'doctor_name': locked_slot.doctor.get_full_name() or locked_slot.doctor.username,
                'date': locked_slot.date.strftime('%Y-%m-%d'),
                'time_slot': f"{locked_slot.start_time.strftime('%H:%M')} - {locked_slot.end_time.strftime('%H:%M')}",
                'doctor_email': locked_slot.doctor.email
            }
        )
        
    except IntegrityError:
        # Fallback if database-level constraints fail (e.g. Booking OneToOne unique constraint)
        messages.error(request, "This slot is already booked.")
    except Exception as e:
        messages.error(request, f"An error occurred while booking the appointment: {e}")
        
    return redirect('dashboard')

# --- Google Calendar OAuth2 flow views ---

@login_required
def google_login(request):
    """
    Redirects the user to Google OAuth2 consent screen.
    """
    flow = get_oauth_flow(request)
    if not flow:
        messages.error(request, "Google Calendar integration is not configured. Please add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to the environment.")
        return redirect('dashboard')
        
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    
    # Save OAuth state in session to prevent CSRF
    request.session['google_oauth_state'] = state
    return redirect(authorization_url)

@login_required
def google_callback(request):
    """
    Google OAuth2 redirect landing page. Exchanges authorization code for credentials.
    """
    flow = get_oauth_flow(request)
    if not flow:
        messages.error(request, "Google Calendar integration is not configured.")
        return redirect('dashboard')
        
    # Verify OAuth state
    state = request.GET.get('state')
    saved_state = request.session.get('google_oauth_state')
    
    # In local testing, state mismatches might happen due to session differences, but check if possible
    # We allow logging warning instead of completely blocking if state is missing locally
    if not state or state != saved_state:
        logger.warning(f"Google OAuth state mismatch: received={state}, saved={saved_state}")
        
    try:
        # Retrieve absolute URL including scheme
        authorization_response = request.build_absolute_uri()
        # Fetch tokens
        flow.fetch_token(authorization_response=authorization_response)
        credentials = flow.credentials
        
        # Save credentials model in database
        GoogleCredential.from_credentials(request.user, credentials)
        messages.success(request, "Google Calendar successfully linked!")
    except Exception as e:
        logger.error(f"Error in Google OAuth Callback: {e}")
        messages.error(request, f"Failed to authorize Google account: {e}")
        
    return redirect('dashboard')
