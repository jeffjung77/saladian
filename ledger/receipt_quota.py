from .ledger_scope import member_ids
from .voucher_quota import limits_for, save_voucher, VoucherQuotaExceeded
from django.db import transaction
from django.db.models import F
from .models import ReceiptPhoto, ReceiptCreationUsage

LIMIT = 10


class ReceiptQuotaExceeded(Exception):
    pass


def is_limited(user):
    return limits_for(user)['photo'] is not None


def remaining_creations(user):
    usage = ReceiptCreationUsage.objects.filter(owner=user).first()
    used = usage.generated_count if usage else ReceiptPhoto.objects.filter(owner=user, status='completed').count()
    limit = limits_for(user)['photo']
    return max(0, limit - used) if limit is not None else None


@transaction.atomic
def create_receipt_voucher(item, user, form):
    claimed = ReceiptPhoto.objects.filter(pk=item.pk, owner_id__in=member_ids(user), status='review', voucher__isnull=True,
        ocr_text=item.ocr_text).update(status='completed')
    if not claimed:
        return None
    # Keep a permanent counter: deleting a voucher must not restore a free use.
    usage, _ = ReceiptCreationUsage.objects.get_or_create(owner=user,
        defaults={'generated_count': ReceiptPhoto.objects.filter(owner=user, status='completed').exclude(pk=item.pk).count()})
    counter = ReceiptCreationUsage.objects.filter(pk=usage.pk)
    if is_limited(user):
        counter = counter.filter(generated_count__lt=limits_for(user)['photo'])
    if not counter.update(generated_count=F('generated_count') + 1):
        raise ReceiptQuotaExceeded
    saved = form.save(commit=False)
    saved.owner = user
    saved.entry_type = 'expense'
    saved.kind = 'expense'
    saved.partner = form.cleaned_data['merchant']
    save_voucher(saved)
    ReceiptPhoto.objects.filter(pk=item.pk).update(voucher=saved)
    return saved
