def calendar_context(request):
    """Expose Google Calendar link status to all templates."""
    linked = False
    if request.user.is_authenticated:
        linked = hasattr(request.user, 'google_credential')
    return {'calendar_linked': linked}
