"""Stable company membership; editable company names are not access credentials."""
from django.db import transaction
from .models import CompanyLedger, LedgerMembership


def company_name(user):
    for relation in ('subscription', 'business_profile'):
        profile = getattr(user, relation, None)
        if profile and profile.company_name.strip():
            return profile.company_name.strip()
    return ''


def member_ids(user):
    if user is None or not user.is_authenticated:
        return []
    company_id = LedgerMembership.objects.filter(user=user).values_list('company_id', flat=True).first()
    if company_id is None:
        return [user.pk]
    return list(LedgerMembership.objects.filter(company_id=company_id).values_list('user_id', flat=True))


def anchor_user(user):
    membership = LedgerMembership.objects.select_related('company__anchor').filter(user=user).first()
    return membership.company.anchor if membership else user


@transaction.atomic
def ensure_membership(user):
    from django.contrib.auth import get_user_model
    get_user_model().objects.select_for_update().get(pk=user.pk)
    membership = LedgerMembership.objects.filter(user=user).first()
    if membership:
        if membership.company.memberships.count() == 1:
            name = company_name(user)
            if membership.company.name != name:
                CompanyLedger.objects.filter(pk=membership.company_id).update(name=name)
        return membership
    company = CompanyLedger.objects.create(name=company_name(user), anchor=user)
    return LedgerMembership.objects.create(user=user, company=company)
