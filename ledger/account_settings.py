from .ledger_scope import member_ids
from django.db.models import Q
from .models import Account, AccountPreference


def visible_accounts(user):
    if user is None or not user.is_authenticated:
        return Account.objects.filter(owner__isnull=True)
    return Account.objects.filter(Q(owner__isnull=True) | Q(owner_id__in=member_ids(user)))


def selectable_accounts(user, existing=()):
    accounts = visible_accounts(user)
    if user is None or not user.is_authenticated:
        return accounts
    disabled = AccountPreference.objects.filter(owner_id__in=member_ids(user), is_active=False).values('account_id')
    return accounts.filter(~Q(pk__in=disabled) | Q(pk__in=[code for code in existing if code]))


CATEGORIES = {
    '당좌자산': '자산', '재고자산': '자산', '투자자산': '자산', '유형자산': '자산',
    '무형자산': '자산', '기타비유동자산': '자산', '유동부채': '부채', '비유동부채': '부채',
    '자본금': '자본', '자본잉여금': '자본', '자본조정': '자본', '이익잉여금(또는 결손금)': '자본',
    '매출액': '수익', '매출원가': '비용', '판매비와관리비': '비용',
    '영업외수익': '수익', '영업외비용': '비용', '법인세비용': '비용',
}
