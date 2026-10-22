from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone


class Voucher(models.Model):
    class Kind(models.TextChoices):
        INCOME = 'income', '수입'
        EXPENSE = 'expense', '지출'

    date = models.DateField('전표일자', default=timezone.localdate)
    kind = models.CharField('구분', max_length=10, choices=Kind.choices)
    account = models.CharField('계정과목', max_length=80)
    partner = models.CharField('거래처', max_length=100, blank=True)
    amount = models.DecimalField('금액(원)', max_digits=14, decimal_places=0, validators=[MinValueValidator(1)])
    memo = models.CharField('적요', max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-pk']
        constraints = [models.CheckConstraint(condition=models.Q(amount__gt=0), name='voucher_amount_positive')]

# Create your models here.
