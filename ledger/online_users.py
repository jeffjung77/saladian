import time
from datetime import datetime, timezone as dt_timezone

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth import HASH_SESSION_KEY
from django.contrib.sessions.models import Session
from django.core.paginator import Paginator
from django.shortcuts import render
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .pagination import page_size
from .system_views import system_required


@never_cache
@system_required
@require_GET
def online_users(request):
    now = time.time()
    active = {}
    for session in Session.objects.filter(expire_date__gt=timezone.now()).iterator():
        data = session.get_decoded()
        try:
            user_id = int(data.get('_auth_user_id', ''))
            last = float(data['last_activity_at']) if data.get('last_activity_at') is not None else None
        except (TypeError, ValueError, OverflowError):
            continue
        if last is not None and not 0 <= now - last < settings.IDLE_TIMEOUT_SECONDS:
            continue
        active.setdefault(user_id, []).append((last, data.get(HASH_SESSION_KEY, '')))
    query = request.GET.get('q', '').strip()[:100]
    rows = []
    for user in get_user_model().objects.filter(pk__in=active, is_active=True).select_related('subscription', 'business_profile').order_by('username'):
        sessions = [last for last, auth_hash in active[user.pk]
                    if constant_time_compare(auth_hash, user.get_session_auth_hash())]
        if not sessions:
            continue
        profile = getattr(user, 'subscription', None) or getattr(user, 'business_profile', None)
        company = profile.company_name if profile else ''
        if query and query.casefold() not in (user.username + ' ' + company).casefold():
            continue
        rows.append({'username': user.username, 'company': company,
                     'grade': '시스템관리자' if user.is_superuser else '관리자' if user.is_staff else '사용자',
                     'last_activity': datetime.fromtimestamp(max(last for last in sessions if last is not None), dt_timezone.utc) if any(last is not None for last in sessions) else None,
                     'sessions': len(sessions)})
    page = Paginator(rows, page_size(request)).get_page(request.GET.get('page'))
    return render(request, 'ledger/online_users.html', {'page': page, 'q': query, 'checked_at': timezone.now()})
