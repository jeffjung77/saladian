from uuid import uuid4
from datetime import datetime, time, timedelta
from django.conf import settings
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.utils import timezone
from .models import Notice


@receiver(user_logged_in, dispatch_uid='ledger.notice_login_cycle')
def notice_login_cycle(sender, request, **kwargs):
    request.session['notice_login_cycle'] = uuid4().hex


def notice_context(request):
    if not request.user.is_authenticated or getattr(settings, 'DESKTOP_MODE', False):
        return {}
    notices = list(Notice.objects.active())
    if not notices:
        return {}
    cycle = request.session.get('notice_login_cycle')
    if not cycle:
        cycle = uuid4().hex
        request.session['notice_login_cycle'] = cycle
    tomorrow = timezone.localdate() + timedelta(days=1)
    today_until = timezone.make_aware(datetime.combine(tomorrow, time.min)).timestamp() * 1000
    return {'popup_notices': notices, 'notice_popup_cycle': f'{request.user.pk}:{cycle}',
            'notice_snooze_config': {'user': str(request.user.pk), 'todayUntil': int(today_until)}}
