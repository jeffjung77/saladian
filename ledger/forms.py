from django import forms
from decimal import Decimal
from .models import Voucher, Account


class VoucherForm(forms.ModelForm):
    account_master = forms.ModelChoiceField(label='계정과목', queryset=Account.objects.all(), empty_label='계정코드 · 계정과목을 선택하세요')
    settlement_account = forms.ModelChoiceField(label='상대계정', queryset=Account.objects.filter(element__in=['자산', '부채', '자본']), empty_label='현금·예금·외상계정 등을 선택하세요', help_text='수입은 상대계정 차변 / 선택 계정과목 대변, 지출은 선택 계정과목 차변 / 상대계정 대변으로 재무제표에 반영합니다.')

    def __init__(self, *args, entry_type=Voucher.EntryType.OTHER, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.entry_type = entry_type
        self.fields['kind'].choices = [(Voucher.Kind.INCOME, '수입'), (Voucher.Kind.EXPENSE, '지출')]
        if entry_type == Voucher.EntryType.SALES:
            self.fields['account_master'].queryset = Account.objects.filter(category='매출액')
            self.fields['kind'].initial = Voucher.Kind.INCOME
            self.fields['kind'].disabled = True
            if not self.instance.pk:
                self.initial['account_master'] = '5001'
        elif entry_type == Voucher.EntryType.EXPENSE:
            self.fields['account_master'].queryset = Account.objects.filter(category__in=['매출원가', '판매비와관리비', '영업외비용', '법인세비용'])
            self.fields['kind'].initial = Voucher.Kind.EXPENSE
            self.fields['kind'].disabled = True
        if entry_type in (Voucher.EntryType.SALES, Voucher.EntryType.EXPENSE):
            self.initial['kind'] = self.fields['kind'].initial

    def save(self, commit=True):
        voucher = super().save(commit=False)
        voucher.account = voucher.account_master.name
        if commit:
            voucher.save()
        return voucher

    def clean(self):
        data = super().clean()
        if data.get('account_master') and data.get('settlement_account') and data['account_master'] == data['settlement_account']:
            self.add_error('settlement_account', '상대계정은 계정과목과 다르게 선택하세요.')
        return data

    class Meta:
        model = Voucher
        fields = ['date', 'kind', 'account_master', 'settlement_account', 'partner', 'amount', 'memo']
        widgets = {
            'date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'amount': forms.NumberInput(attrs={'min': 1, 'step': 1, 'placeholder': '0'}),
            'memo': forms.Textarea(attrs={'rows': 3, 'placeholder': '거래 내용을 입력하세요'}),
        }


class JournalHeaderForm(forms.ModelForm):
    class Meta:
        model = Voucher
        fields = ['date', 'partner', 'memo', 'is_closing']
        help_texts = {'is_closing': '수익·비용을 이익잉여금으로 대체하는 결산전표에만 선택하세요. 대차대조표에는 반영하고 손익계산서에서는 제외합니다.'}
        widgets = {
            'date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'memo': forms.Textarea(attrs={'rows': 2}),
        }


class JournalRowForm(forms.Form):
    debit_account = forms.ModelChoiceField(label='차변 계정과목', queryset=Account.objects.all(), required=False, empty_label='계정과목 선택')
    debit_amount = forms.DecimalField(label='차변 금액', required=False, min_value=1, max_digits=14, decimal_places=0, widget=forms.NumberInput(attrs={'min': 1, 'step': 1}))
    credit_account = forms.ModelChoiceField(label='대변 계정과목', queryset=Account.objects.all(), required=False, empty_label='계정과목 선택')
    credit_amount = forms.DecimalField(label='대변 금액', required=False, min_value=1, max_digits=14, decimal_places=0, widget=forms.NumberInput(attrs={'min': 1, 'step': 1}))
    memo = forms.CharField(label='라인 적요', required=False, max_length=1000, widget=forms.TextInput(attrs={'placeholder': '이 행의 공통 거래 내용 (선택)'}))

    def clean(self):
        data = super().clean()
        for side in ['debit', 'credit']:
            account, amount = data.get(f'{side}_account'), data.get(f'{side}_amount')
            if account is not None and amount is None and f'{side}_amount' not in self.errors:
                self.add_error(f'{side}_amount', '계정과목에 해당하는 금액을 입력하세요.')
            if amount is not None and account is None and f'{side}_account' not in self.errors:
                self.add_error(f'{side}_account', '금액에 해당하는 계정과목을 선택하세요.')
        if data.get('memo') and not any(data.get(f'{side}_{field}') for side in ['debit', 'credit'] for field in ['account', 'amount']):
            self.add_error('memo', '적요만 입력할 수 없습니다. 해당 행에 계정과 금액도 입력하세요.')
        return data


class BaseJournalRows(forms.BaseFormSet):
    def clean(self):
        super().clean()
        if self.total_form_count() != 5:
            raise forms.ValidationError('입력 화면은 차변·대변 각각 5행이어야 합니다.')
        if any(self.errors):
            return
        self.debit_total = sum((form.cleaned_data.get('debit_amount') or Decimal(0) for form in self.forms), Decimal(0))
        self.credit_total = sum((form.cleaned_data.get('credit_amount') or Decimal(0) for form in self.forms), Decimal(0))
        if not self.debit_total or not self.credit_total:
            raise forms.ValidationError('차변과 대변을 각각 한 건 이상 입력하세요.')
        if self.debit_total != self.credit_total:
            raise forms.ValidationError('차변 합계와 대변 합계가 일치해야 저장할 수 있습니다.')
        if self.debit_total > Decimal('99999999999999'):
            raise forms.ValidationError('전표 합계는 99,999,999,999,999원 이하여야 합니다.')


JournalRows = forms.formset_factory(JournalRowForm, formset=BaseJournalRows, extra=5, max_num=5, validate_max=True, absolute_max=5)


class PeriodForm(forms.Form):
    start = forms.DateField(label='시작일', required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    end = forms.DateField(label='종료일', required=False, widget=forms.DateInput(attrs={'type': 'date'}))

    def clean(self):
        data = super().clean()
        if data.get('start') and data.get('end') and data['start'] > data['end']:
            raise forms.ValidationError('종료일은 시작일 이후여야 합니다.')
        return data


class BalanceSheetForm(forms.Form):
    as_of = forms.DateField(label='기준일', widget=forms.DateInput(attrs={'type': 'date'}))


class IncomeStatementForm(PeriodForm):
    start = forms.DateField(label='시작일', widget=forms.DateInput(attrs={'type': 'date'}))
    end = forms.DateField(label='종료일', widget=forms.DateInput(attrs={'type': 'date'}))


class AccountLedgerForm(IncomeStatementForm):
    field_order = ['account', 'start', 'end']
    account = forms.ModelChoiceField(label='계정과목', queryset=Account.objects.all(), empty_label='계정코드 · 계정과목을 선택하세요')


class PartnerLedgerForm(PeriodForm):
    partner = forms.ChoiceField(label='거래처', choices=())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        names = Voucher.objects.exclude(partner='').order_by('partner').values_list('partner', flat=True).distinct()
        self.fields['partner'].choices = [('', '거래처를 선택하세요'), ('unassigned:', '거래처 미입력')] + [('name:' + name, name) for name in names]
