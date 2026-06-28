from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('accounts/signup/', views.signup_view, name='signup'),
    path('accounts/login/', views.login_view, name='login'),
    path('accounts/logout/', views.logout_view, name='logout'),
    
    # Dashboard & Booking
    path('', views.dashboard_view, name='dashboard'),
    path('book/', views.book_slot_view, name='book_slot'),
    
    # Google OAuth
    path('accounts/google/login/', views.google_login, name='google_login'),
    path('accounts/google/callback/', views.google_callback, name='google_callback'),
]
