from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from ledger.models import Voucher, Counterparty


class Command(BaseCommand):
    help = '사용자가 지정되지 않은 기존 전표만 명시한 계정에 연결합니다. 기본값은 미리보기입니다.'

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True)
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        try:
            user = get_user_model().objects.get(username=options['username'], is_active=True)
        except get_user_model().DoesNotExist as exc:
            raise CommandError('활성 사용자 계정을 찾을 수 없습니다. 먼저 회원가입 또는 createsuperuser를 실행하세요.') from exc
        legacy = Voucher.objects.filter(owner__isnull=True)
        if not options['apply']:
            self.stdout.write(f'미리보기: 기존 전표 {legacy.count()}건 → {user.username}. 반영하려면 --apply를 추가하세요.')
            return
        with transaction.atomic():
            count = legacy.update(owner=user)
            unlinked = Voucher.objects.filter(owner=user, counterparty__isnull=True).exclude(partner='')
            for name in list(unlinked.order_by().values_list('partner', flat=True).distinct()):
                partner, _ = Counterparty.objects.get_or_create(owner=user, name=name)
                unlinked.filter(partner=name).update(counterparty=partner)
        self.stdout.write(self.style.SUCCESS(f'기존 전표 {count}건을 {user.username} 계정에 연결했습니다.'))
