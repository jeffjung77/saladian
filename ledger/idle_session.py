import time
from django.conf import settings
from django.contrib.auth import logout
from django.contrib.auth.views import redirect_to_login
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST


class IdleSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path in ['/deployment/status/', '/maintenance/']:
            return self.get_response(request)
        if request.user.is_authenticated:
            now = time.time()
            previous = request.session.get('last_activity_at', now)
            if now - previous >= settings.IDLE_TIMEOUT_SECONDS:
                logout(request)
                if request.path == '/accounts/activity/':
                    return JsonResponse({'expired': True}, status=401)
                return redirect_to_login(request.get_full_path())
            request.session['last_activity_at'] = now
            request.session.set_expiry(settings.IDLE_TIMEOUT_SECONDS)
        response = self.get_response(request)
        # Login authenticates inside the view, after the request-side check.
        if request.user.is_authenticated and 'last_activity_at' not in request.session:
            request.session['last_activity_at'] = time.time()
            request.session.set_expiry(settings.IDLE_TIMEOUT_SECONDS)
        return response


@login_required
@require_POST
def activity(request):
    return JsonResponse({'active': True})
