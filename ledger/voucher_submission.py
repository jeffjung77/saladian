from functools import wraps
from uuid import UUID
from django.contrib import messages
from django.db import transaction, IntegrityError
from django.shortcuts import redirect
from .models import Voucher


def prevent_duplicate_submission(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        token = None
        if request.method == 'POST' and not kwargs.get('pk'):
            try:
                token = UUID(request.POST.get('submission_token', ''))
            except (ValueError, TypeError, AttributeError):
                pass
        def existing_response():
            saved = Voucher.objects.filter(owner=request.user, submission_token=token).first() if token else None
            if saved:
                messages.success(request, f'전표가 저장되었습니다. 전표번호는 {saved.pk} 번입니다.', extra_tags=f'voucher-saved-popup voucher-entry-{saved.entry_type}')
                return redirect('dashboard')
        existing = existing_response()
        if existing:
            return existing
        try:
            with transaction.atomic():
                return view(request, *args, **kwargs)
        except IntegrityError:
            existing = existing_response()
            if existing:
                return existing
            raise
    return wrapped
