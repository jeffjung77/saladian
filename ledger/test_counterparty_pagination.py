from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .models import Counterparty


class CounterpartyPaginationTests(TestCase):
    def test_page_sizes_search_and_owner_scope(self):
        owner = get_user_model().objects.create_user(username='page-owner', is_staff=True)
        other = get_user_model().objects.create_user(username='page-other')
        Counterparty.objects.bulk_create([Counterparty(owner=owner, name=f'Partner {n:02d}') for n in range(12)])
        Counterparty.objects.create(owner=other, name='Private')
        self.client.force_login(owner)
        url = reverse('counterparties')
        first = self.client.get(url, {'per_page': 5, 'q': 'Partner'})
        self.assertEqual(len(first.context['page']), 5)
        self.assertEqual(first.context['page'].paginator.count, 12)
        self.assertContains(first, 'per_page=5&amp;page=2')
        second = self.client.get(url, {'per_page': 5, 'page': 2})
        self.assertTrue(set(p.pk for p in first.context['page']).isdisjoint(p.pk for p in second.context['page']))
        self.assertEqual(len(self.client.get(url, {'per_page': 10}).context['page']), 10)
        self.assertEqual(len(self.client.get(url, {'per_page': 10, 'page': 2}).context['page']), 2)
        self.assertEqual(self.client.get(url, {'per_page': 'invalid'}).context['per_page'], 10)
