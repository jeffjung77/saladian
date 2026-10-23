from django.contrib.auth import get_user_model
from django.test import TestCase
from .models import Counterparty


class AuthenticatedLedgerTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.user = get_user_model().objects.create_user(username='ledger_test_user')
        self.partner = Counterparty.objects.create(owner=self.user, name='거래처')
        self.client.force_login(self.user)
