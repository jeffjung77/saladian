from django.db import transaction
from django.db.models import F
from .models import Voucher, VoucherQuota, VoucherCreationUsage


class VoucherQuotaExceeded(Exception):
    pass


def limits_for(user):
    from django.conf import settings
    if getattr(settings, 'DESKTOP_MODE', False):
        return dict(sales=None, expense=None, other=None, photo=None)
    policy = VoucherQuota.objects.filter(owner=user).first()
    if policy:
        return {key: getattr(policy, key + '_limit') for key in ('sales', 'expense', 'other', 'photo')}
    return dict(sales=None, expense=None, other=None, photo=None if user.is_staff or user.is_superuser else 10)


@transaction.atomic
def save_voucher(voucher):
    if voucher._state.adding:
        usage, _ = VoucherCreationUsage.objects.get_or_create(owner=voucher.owner, entry_type=voucher.entry_type,
            defaults={'generated_count': Voucher.objects.filter(owner=voucher.owner, entry_type=voucher.entry_type, opening_batch__isnull=True, closing_batch__isnull=True).count()})
        counter = VoucherCreationUsage.objects.filter(pk=usage.pk)
        limit = limits_for(voucher.owner)[voucher.entry_type]
        if limit is not None:
            counter = counter.filter(generated_count__lt=limit)
        if not counter.update(generated_count=F('generated_count') + 1):
            raise VoucherQuotaExceeded(f'전표 생성 한도({limit}건)에 도달하여 전표를 저장할 수 없습니다. 시스템관리자에게 문의하세요.')
    voucher.save()
