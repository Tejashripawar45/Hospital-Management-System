from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib import messages

def doctor_required(view_func):
    def _wrapped_view_func(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        try:
            if request.user.profile.role == 'doctor':
                return view_func(request, *args, **kwargs)
        except Exception:
            pass
        messages.error(request, "Access Denied: Only doctors can access this page.")
        return redirect('dashboard')
    return _wrapped_view_func

def patient_required(view_func):
    def _wrapped_view_func(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        try:
            if request.user.profile.role == 'patient':
                return view_func(request, *args, **kwargs)
        except Exception:
            pass
        messages.error(request, "Access Denied: Only patients can access this page.")
        return redirect('dashboard')
    return _wrapped_view_func
