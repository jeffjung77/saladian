from importlib import import_module
from types import SimpleNamespace
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from django.db.models.deletion import ProtectedError
from django.test import Client
from django.test import override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from tempfile import TemporaryDirectory
from django.urls import reverse
from .models import Counterparty, Voucher
from .test_helpers import AuthenticatedLedgerTestCase
from .tests import journal_data


class CounterpartyTests(AuthenticatedLedgerTestCase):
    def setUp(self):
        super().setUp()
        self.user.is_staff = True
        self.user.save(update_fields=['is_staff'])

    def test_generated_numbers_are_unique_stable_and_readonly(self):
        numbers = set()
        for kind in Counterparty.Kind.values:
            response = self.client.post(reverse('counterparty_new'), self.data(name=f'유형{kind}', kind=kind, number='CP999999'))
            self.assertEqual(response.status_code, 302)
            partner = Counterparty.objects.get(owner=self.user, name=f'유형{kind}')
            self.assertEqual(partner.kind, kind)
            self.assertEqual(partner.number, f'CP{partner.pk:06d}')
            numbers.add(partner.number)
        self.assertEqual(len(numbers), 4)
        original = partner.number
        self.client.post(reverse('counterparty_edit', args=[partner.pk]), self.data(name='변경', kind='1', number='CP000000'))
        partner.refresh_from_db()
        self.assertEqual(partner.number, original)
        self.assertEqual(partner.kind, '1')
        response = self.client.get(reverse('counterparties'), {'q': original})
        self.assertContains(response, original)
        self.assertContains(response, '1. 고객')
        self.assertEqual(response.context['page'].paginator.count, 1)
        self.assertContains(self.client.get(reverse('counterparty_edit', args=[partner.pk])), original)

    def test_kind_required_and_rejects_unknown_choice(self):
        for kind in ['', '5', 'customer']:
            response = self.client.post(reverse('counterparty_new'), self.data(kind=kind))
            self.assertIn('kind', response.context['form'].errors)
        self.assertEqual(self.partner.kind, Counterparty.Kind.OTHER)

    def test_certificate_upload_download_replace_and_access(self):
        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            url = reverse('counterparty_new')
            pdf = b'%PDF-1.4\ncertificate\n%%EOF'
            response = self.client.post(url, self.data(business_certificate=SimpleUploadedFile('certificate.pdf', pdf, content_type='application/pdf')))
            self.assertEqual(response.status_code, 302)
            partner = Counterparty.objects.get(name='새 거래처')
            download = reverse('counterparty_certificate', args=[partner.pk])
            response = self.client.get(download)
            self.assertEqual(b''.join(response.streaming_content), pdf)
            response.close()
            self.assertEqual(Client().get(download).status_code, 302)
            other = get_user_model().objects.create_user(username='download-other', is_staff=True)
            client = Client()
            client.force_login(other)
            self.assertEqual(client.get(download).status_code, 404)
            edit = reverse('counterparty_edit', args=[partner.pk])
            old_name = partner.business_certificate.name
            self.client.post(edit, self.data())
            partner.refresh_from_db()
            self.assertEqual(partner.business_certificate.name, old_name)
            self.client.post(edit, self.data(business_certificate=SimpleUploadedFile('new.pdf', pdf)))
            partner.refresh_from_db()
            self.assertNotEqual(partner.business_certificate.name, old_name)
            self.assertContains(self.client.get(edit), download)
            for name, content in [('fake.pdf', b'not a pdf'), ('file.txt', pdf), ('large.pdf', b'%PDF-' + b'0' * (10 * 1024 * 1024))]:
                response = self.client.post(edit, self.data(business_certificate=SimpleUploadedFile(name, content)))
                self.assertIn('business_certificate', response.context['form'].errors)

    def data(self, **overrides):
        result = {'kind': '1', 'name': '새 거래처', 'business_number': '1234567890', 'representative': '대표',
                  'contact_name': '담당자', 'phone': '010-1234-5678', 'email': 'partner@example.test',
                  'address': '서울', 'memo': '거래처 메모'}
        result.update(overrides)
        return result

    def voucher_data(self, **overrides):
        data = {'date': '2026-10-23', 'account_master': '5001', 'settlement_account': '1101',
                'amount': '1000', 'counterparty': self.partner.pk}
        data.update(overrides)
        return data

    def test_register_edit_search_and_duplicate_name(self):
        response = self.client.post(reverse('counterparty_new'), self.data())
        self.assertRedirects(response, reverse('counterparties'))
        partner = Counterparty.objects.get(owner=self.user, name='새 거래처')
        self.assertEqual(partner.business_number, '123-45-67890')
        self.assertEqual(partner.phone, '010-1234-5678')
        self.assertContains(self.client.get(reverse('counterparties'), {'q': '새 거래처'}), 'partner@example.test')
        response = self.client.post(reverse('counterparty_new'), self.data())
        self.assertIn('name', response.context['form'].errors)
        self.client.post(reverse('counterparty_edit', args=[partner.pk]), self.data(name='변경한 거래처'))
        partner.refresh_from_db()
        self.assertEqual(partner.name, '변경한 거래처')
        response = self.client.post(reverse('counterparty_edit', args=[partner.pk]), self.data(name=self.partner.name))
        self.assertIn('name', response.context['form'].errors)

    def test_optional_details_required_name_and_invalid_formats(self):
        for field in ['name', 'business_number', 'representative', 'address']:
            response = self.client.post(reverse('counterparty_new'), self.data(**{field: ''}))
            self.assertIn(field, response.context['form'].errors)
        for data, field in [(self.data(name='   '), 'name'), (self.data(business_number='123'), 'business_number'), (self.data(email='invalid'), 'email')]:
            response = self.client.post(reverse('counterparty_new'), data)
            self.assertIn(field, response.context['form'].errors)

    def test_all_entry_screens_select_from_master_and_support_refresh(self):
        for name in ['sales_new', 'expense_new', 'voucher_new']:
            response = self.client.get(reverse(name))
            self.assertContains(response, 'id="id_counterparty"')
            self.assertContains(response, self.partner.name)
            self.assertContains(response, reverse('counterparty_new'))
            self.assertContains(response, reverse('counterparty_options'))
        self.assertRedirects(self.client.post(reverse('sales_new'), self.voucher_data()), reverse('dashboard'))
        voucher = Voucher.objects.get()
        self.assertEqual(voucher.counterparty_id, self.partner.pk)
        self.assertEqual(voucher.partner, self.partner.name)
        response = self.client.get(reverse('voucher_edit', args=[voucher.pk]))
        self.assertEqual(response.context['form'].initial['counterparty'], self.partner.pk)
        self.client.post(reverse('voucher_new'), journal_data(counterparty=self.partner.pk))
        self.assertEqual(Voucher.objects.latest('pk').counterparty_id, self.partner.pk)
        self.client.post(reverse('voucher_edit', args=[voucher.pk]), self.voucher_data(counterparty=''))
        voucher.refresh_from_db()
        self.assertIsNone(voucher.counterparty_id)
        self.assertEqual(voucher.partner, '')

    def test_owner_isolation_for_master_options_edit_and_forged_selection(self):
        other_user = get_user_model().objects.create_user(username='other', is_staff=True)
        other = Counterparty.objects.create(owner=other_user, name='타인 거래처', phone='02-1234-5678')
        Counterparty.objects.create(owner=other_user, name=self.partner.name)
        response = self.client.get(reverse('counterparties'))
        self.assertNotContains(response, '타인 거래처')
        options = self.client.get(reverse('counterparty_options'))
        self.assertEqual([p['id'] for p in options.json()['counterparties']], [self.partner.pk])
        self.assertIn('no-store', options.headers['Cache-Control'])
        for method in [self.client.get, self.client.post]:
            self.assertEqual(method(reverse('counterparty_edit', args=[other.pk])).status_code, 404)
        response = self.client.post(reverse('sales_new'), self.voucher_data(counterparty=other.pk))
        self.assertIn('counterparty', response.context['form'].errors)
        response = self.client.post(reverse('voucher_new'), journal_data(counterparty=other.pk))
        self.assertIn('counterparty', response.context['form'].errors)
        self.assertFalse(Voucher.objects.exists())
        response = self.client.get(reverse('partner_ledger'), {'partner': f'master:{other.pk}'})
        self.assertTrue(response.context['form'].errors)
        self.client.post(reverse('counterparty_new'), self.data(owner=other_user.pk))
        self.assertEqual(Counterparty.objects.get(name='새 거래처').owner_id, self.user.pk)

    def test_renaming_preserves_voucher_and_ledger_identity(self):
        self.client.post(reverse('sales_new'), self.voucher_data())
        voucher = Voucher.objects.get()
        original_name = voucher.partner
        self.client.post(reverse('counterparty_edit', args=[self.partner.pk]), self.data(name='새 이름'))
        voucher.refresh_from_db()
        self.assertEqual(voucher.partner, original_name)
        self.assertEqual(voucher.partner_label, '새 이름')
        self.assertContains(self.client.get(reverse('dashboard')), '새 이름')
        response = self.client.get(reverse('partner_ledger'), {'partner': f'master:{self.partner.pk}'})
        self.assertEqual(response.context['income'], 1000)
        self.assertEqual(response.context['partner_name'], '새 이름')
        with self.assertRaises(ProtectedError):
            self.partner.delete()

    def test_legacy_backfill_and_later_assignment_preserve_separation(self):
        other_user = get_user_model().objects.create_user(username='second_owner')
        originals = [Voucher.objects.create(owner=owner, date='2026-10-23', kind='income', account='매출', amount=100, partner='기존 거래처') for owner in [self.user, self.user, other_user, None]]
        link = import_module('ledger.migrations.0012_link_existing_counterparties').link_existing
        link(apps, SimpleNamespace(connection=connection))
        for voucher in originals:
            voucher.refresh_from_db()
        self.assertEqual(originals[0].counterparty_id, originals[1].counterparty_id)
        self.assertNotEqual(originals[0].counterparty_id, originals[2].counterparty_id)
        self.assertIsNone(originals[3].counterparty_id)
        self.assertEqual(originals[0].partner, '기존 거래처')
        self.assertEqual(originals[0].amount, 100)
        count = Counterparty.objects.count()
        link(apps, SimpleNamespace(connection=connection))
        self.assertEqual(Counterparty.objects.count(), count)
        from io import StringIO
        call_command('assign_legacy_vouchers', username=self.user.username, apply=True, stdout=StringIO())
        originals[3].refresh_from_db()
        self.assertEqual(originals[3].counterparty_id, originals[0].counterparty_id)

    def test_registration_csrf_and_anonymous_access(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(reverse('counterparty_new'), self.data()).status_code, 403)
        client.logout()
        for name in ['counterparties', 'counterparty_new', 'counterparty_options']:
            self.assertEqual(client.get(reverse(name)).status_code, 302)
