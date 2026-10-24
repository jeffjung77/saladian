from django.db import migrations


def copy_completed(apps, schema_editor):
    Profile = apps.get_model('ledger', 'BusinessProfile')
    Subscription = apps.get_model('ledger', 'Subscription')
    alias = schema_editor.connection.alias
    names = ['company_name', 'business_number', 'business_address', 'business_phone', 'contact_name', 'contact_phone']
    for profile in Profile.objects.using(alias).select_related('user').iterator():
        values = {name: getattr(profile, name) for name in names}
        values['email'] = profile.user.email
        if all(str(value or '').strip() for value in values.values()):
            Subscription.objects.using(alias).get_or_create(user_id=profile.user_id, defaults=values)


class Migration(migrations.Migration):
    dependencies = [('ledger', '0021_subscription')]
    operations = [migrations.RunPython(copy_completed, migrations.RunPython.noop)]
