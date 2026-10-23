from django.db import migrations


def link_existing(apps, schema_editor):
    Partner = apps.get_model('ledger', 'Counterparty')
    Voucher = apps.get_model('ledger', 'Voucher')
    alias = schema_editor.connection.alias
    source = Voucher.objects.using(alias).filter(owner__isnull=False, counterparty__isnull=True).exclude(partner='')
    keys = list(source.order_by().values_list('owner_id', 'partner').distinct())
    for owner_id, name in keys:
        partner, _ = Partner.objects.using(alias).get_or_create(owner_id=owner_id, name=name)
        source.filter(owner_id=owner_id, partner=name).update(counterparty=partner)


class Migration(migrations.Migration):
    dependencies = [('ledger', '0011_counterparty_voucher_counterparty_and_more')]
    operations = [migrations.RunPython(link_existing, migrations.RunPython.noop)]
