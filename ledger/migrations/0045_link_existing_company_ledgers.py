import unicodedata
from django.conf import settings
from django.db import migrations


def link_existing(apps, schema_editor):
    alias = schema_editor.connection.alias
    User = apps.get_model(settings.AUTH_USER_MODEL)
    Company = apps.get_model('ledger', 'CompanyLedger')
    Membership = apps.get_model('ledger', 'LedgerMembership')
    profiles = {}
    for model in ('BusinessProfile', 'Subscription'):
        for profile in apps.get_model('ledger', model).objects.using(alias).all():
            if profile.company_name.strip():
                profiles[profile.user_id] = profile.company_name.strip()
    groups = {}
    for user in User.objects.using(alias).order_by('pk'):
        name = profiles.get(user.pk, '')
        key = ('name', ' '.join(unicodedata.normalize('NFKC', name).split()).casefold()) if name else ('user', user.pk)
        groups.setdefault(key, []).append((user, name))
    for members in groups.values():
        ids = [user.pk for user, name in members]
        if apps.get_model('ledger', 'OpeningBalanceBatch').objects.using(alias).filter(owner_id__in=ids).count() > 1:
            raise RuntimeError('Multiple opening balances for one company; review before linking.')
        years = list(apps.get_model('ledger', 'YearEndClosing').objects.using(alias).filter(owner_id__in=ids).values_list('year', flat=True))
        if len(years) != len(set(years)):
            raise RuntimeError('Duplicate year-end closing for one company; review before linking.')
        company = Company.objects.using(alias).create(name=members[0][1], anchor_id=ids[0])
        Membership.objects.using(alias).bulk_create([Membership(user_id=pk, company_id=company.pk) for pk in ids])


class Migration(migrations.Migration):
    dependencies = [('ledger', '0044_company_ledger_membership')]
    operations = [migrations.RunPython(link_existing, migrations.RunPython.noop)]
