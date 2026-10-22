from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone


class Account(models.Model):
    code = models.CharField('계정코드', max_length=4, primary_key=True)
    name = models.CharField('계정과목', max_length=80)
    category = models.CharField('소분류', max_length=80)
    section = models.CharField('중분류', max_length=80, blank=True)
    element = models.CharField('대분류', max_length=20, blank=True)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f'{self.code} · {self.name}'


class Voucher(models.Model):
    class EntryType(models.TextChoices):
        SALES = 'sales', '매출입력'
        EXPENSE = 'expense', '비용입력'
        OTHER = 'other', '기타전표'

    class Kind(models.TextChoices):
        INCOME = 'income', '수입'
        EXPENSE = 'expense', '지출'
        JOURNAL = 'journal', '차변·대변'

    date = models.DateField('전표일자', default=timezone.localdate)
    entry_type = models.CharField('입력유형', max_length=10, choices=EntryType.choices, default=EntryType.OTHER)
    kind = models.CharField('구분', max_length=10, choices=Kind.choices)
    account = models.CharField('계정과목', max_length=80)
    account_master = models.ForeignKey(Account, verbose_name='계정과목', on_delete=models.PROTECT, null=True, blank=True)
    partner = models.CharField('거래처', max_length=100, blank=True)
    settlement_account = models.ForeignKey(Account, verbose_name='상대계정', related_name='settled_vouchers', on_delete=models.PROTECT, null=True, blank=True)
    is_closing = models.BooleanField('손익대체 결산전표', default=False)
    amount = models.DecimalField('금액(원)', max_digits=14, decimal_places=0, validators=[MinValueValidator(1)])
    memo = models.CharField('적요', max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_journal(self):
        return self.kind == self.Kind.JOURNAL

    class Meta:
        ordering = ['-date', '-pk']
        constraints = [models.CheckConstraint(condition=models.Q(amount__gt=0), name='voucher_amount_positive')]

# Create your models here.


class JournalLine(models.Model):
    class Side(models.TextChoices):
        DEBIT = 'debit', '차변'
        CREDIT = 'credit', '대변'

    voucher = models.ForeignKey(Voucher, related_name='journal_lines', on_delete=models.CASCADE)
    row = models.PositiveSmallIntegerField('행 번호')
    side = models.CharField('차대구분', max_length=6, choices=Side.choices)
    account = models.ForeignKey(Account, on_delete=models.PROTECT, verbose_name='계정과목')
    memo = models.CharField('라인 적요', max_length=1000, blank=True)
    amount = models.DecimalField('금액(원)', max_digits=14, decimal_places=0, validators=[MinValueValidator(1)])

    class Meta:
        ordering = ['row', 'side']
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name='journal_line_amount_positive'),
            models.CheckConstraint(condition=models.Q(row__gte=1, row__lte=5), name='journal_line_five_rows'),
            models.CheckConstraint(condition=models.Q(side__in=['debit', 'credit']), name='journal_line_valid_side'),
            models.UniqueConstraint(fields=['voucher', 'row', 'side'], name='journal_line_unique_side_row'),
        ]
