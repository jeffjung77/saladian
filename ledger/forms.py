from .ledger_scope import member_ids, anchor_user
from .account_fields import AccountEntryField
from django import forms
from decimal import Decimal
from .models import Voucher, Account, Counterparty
import re
import uuid
from .vat import VAT_FIELDS, VAT_CHOICES, TRADE_CHOICES, DOCUMENT_CHOICES, DEDUCTION_CHOICES
from .widgets import MoneyInput
from .account_settings import visible_accounts, selectable_accounts, CATEGORIES


class AccountForm(forms.ModelForm):
    category = forms.ChoiceField(label='소분류', choices=[('', '분류 선택')] + [(category, f'{element} · {category}') for category, element in CATEGORIES.items()])

    def clean_code(self):
        code = self.cleaned_data['code']
        if not re.fullmatch(r'[0-9]{4}', code):
            raise forms.ValidationError('계정코드는 숫자 4자리로 입력하세요.')
        return code

    def save(self, commit=True):
        account = super().save(commit=False)
        account.element = CATEGORIES[self.cleaned_data['category']]
        if commit:
            account.save()
        return account

    class Meta:
        model = Account
        fields = ['code', 'name', 'category', 'section']
        help_texts = {'code': '중복되지 않는 숫자 4자리를 입력하세요.', 'section': '필요한 경우 유동자산·비유동자산 등의 중분류를 입력하세요.'}


class VatFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ('vat_amount', 'vat_deductible'):
            self.fields[name].widget = MoneyInput(attrs={'min': 0, 'step': 1})

    def clean(self):
        data = super().clean()
        for name in ('vat_amount', 'vat_deductible'):
            if name not in self.errors:
                data[name] = data.get(name) or Decimal(0)
        tax, deductible = data.get('vat_amount', 0), data.get('vat_deductible', 0)
        code, trade = data.get('vat_code'), data.get('vat_trade')
        if not code:
            if any(data.get(name) for name in VAT_FIELDS[1:] if name != 'vat_trade' or not self.fields['vat_trade'].disabled):
                self.add_error('vat_code', '부가세 정보를 입력하려면 부가세 코드를 선택하세요.')
            return data
        if not trade:
            self.add_error('vat_trade', '매출 또는 매입을 선택하세요.')
        if not data.get('vat_document') and code != 'X':
            self.add_error('vat_document', '증빙 종류를 선택하세요.')
        if not code.startswith('T') and tax:
            self.add_error('vat_amount', '면세·영세율·대상 외 거래의 부가세 금액은 0원이어야 합니다.')
        deduction = data.get('vat_deduction')
        if trade == 'S':
            if deduction or deductible:
                self.add_error('vat_deduction', '매출에는 매입세액 공제 구분을 입력하지 않습니다.')
        elif trade == 'P':
            if not deduction:
                self.add_error('vat_deduction', '매입세액 공제 구분을 선택하세요.')
            if not code.startswith('T') and deduction != 'C04':
                self.add_error('vat_deduction', '부가세가 없는 매입은 C04를 선택하세요.')
            if deduction in ('C04', 'C09') and tax:
                self.add_error('vat_deduction', '부가세가 있으면 공제·불공제·공통매입 안분을 확정한 뒤 저장하세요.')
            if deduction in ('C02', 'C03') and not data.get('vat_reason'):
                self.add_error('vat_reason', '불공제 또는 안분 사유를 입력하세요.')
        if deductible and deduction != 'C03':
            self.add_error('vat_deductible', '공통매입 안분(C03)인 경우에만 입력하세요.')
        if tax is not None and deductible is not None and deductible > tax:
            self.add_error('vat_deductible', '공제할 세액은 부가세 금액을 초과할 수 없습니다.')
        return data


class CounterpartyForm(forms.ModelForm):
    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.owner = self.instance.owner if self.instance.pk else user
        for name in ('name', 'business_number', 'representative', 'address'):
            self.fields[name].required = True

    def clean_business_certificate(self):
        uploaded = self.cleaned_data.get('business_certificate')
        if uploaded and hasattr(uploaded, 'content_type'):
            if not uploaded.name.lower().endswith('.pdf') or uploaded.size > 10 * 1024 * 1024:
                raise forms.ValidationError('10MB 이하의 PDF 파일을 첨부해 주세요.')
            signature = uploaded.read(5)
            uploaded.seek(0)
            if signature != b'%PDF-':
                raise forms.ValidationError('올바른 PDF 파일을 첨부해 주세요.')
        return uploaded

    def clean_name(self):
        name = self.cleaned_data['name']
        if Counterparty.objects.filter(owner_id__in=member_ids(self.instance.owner), name=name).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('이미 등록된 거래처명입니다.')
        return name

    def clean_business_number(self):
        value = self.cleaned_data['business_number']
        if not value:
            return ''
        if not re.fullmatch(r'(?:[0-9]{10}|[0-9]{3}-[0-9]{2}-[0-9]{5})', value):
            raise forms.ValidationError('숫자 10자리 또는 123-45-67890 형식으로 입력하세요.')
        digits = value.replace('-', '')
        return f'{digits[:3]}-{digits[3:5]}-{digits[5:]}'

    class Meta:
        model = Counterparty
        fields = ['kind', 'name', 'business_number', 'representative', 'contact_name', 'phone', 'email', 'address', 'bank_name', 'bank_account', 'memo', 'business_certificate']
        widgets = {'business_certificate': forms.FileInput(attrs={'accept': '.pdf,application/pdf'}), 'memo': forms.Textarea(attrs={'rows': 3}), 'phone': forms.TextInput(attrs={'type': 'tel'})}


class CounterpartySelectionMixin:
    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields['counterparty'].queryset = Counterparty.objects.filter(owner_id__in=member_ids(user)) if user is not None and user.is_authenticated else Counterparty.objects.none()
        self.fields['counterparty'].empty_label = '거래처 미지정'

    def save(self, commit=True):
        voucher = super().save(commit=False)
        voucher.partner = voucher.counterparty.name if voucher.counterparty_id else ''
        if commit:
            voucher.save()
        return voucher


class VoucherForm(CounterpartySelectionMixin, VatFormMixin, forms.ModelForm):
    submission_token = forms.UUIDField(required=False, initial=uuid.uuid4, widget=forms.HiddenInput)
    memo = forms.CharField(label='적요', required=False, max_length=200,
        widget=forms.Textarea(attrs={'rows': 3, 'maxlength': 200, 'placeholder': '거래 내용을 입력하세요 (최대 200자)', 'style': 'resize:vertical'}))
    vat_enabled = forms.BooleanField(label='부가세 입력', required=False)
    account_master = AccountEntryField(label='계정과목', queryset=Account.objects.all(), widget=forms.TextInput(attrs={'autocomplete': 'off', 'placeholder': '계정코드 또는 계정과목명 직접 입력', 'list': 'voucher-account-options'}))
    settlement_account = AccountEntryField(label='상대계정', queryset=Account.objects.filter(element__in=['자산', '부채', '자본']), widget=forms.TextInput(attrs={'autocomplete': 'off', 'placeholder': '계정코드 또는 계정과목명 직접 입력', 'list': 'voucher-settlement-options'}), help_text='수입은 상대계정 차변 / 선택 계정과목 대변, 지출은 선택 계정과목 차변 / 상대계정 대변으로 재무제표에 반영합니다.')

    def __init__(self, *args, entry_type=Voucher.EntryType.OTHER, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['account_master'].display_code_and_name = True
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
            self.order_fields(['date', 'kind', 'counterparty', 'settlement_account', 'account_master', 'amount', 'memo', 'vat_enabled'] + VAT_FIELDS)
            self.fields['kind'].widget = forms.HiddenInput()
            self.initial['kind'] = self.fields['kind'].initial
            self.fields['vat_trade'].initial = 'S' if entry_type == Voucher.EntryType.SALES else 'P'
            self.initial['vat_trade'] = self.fields['vat_trade'].initial
            self.fields['vat_trade'].disabled = True
        self.fields['amount'].label = '공급가액 / 부가세 제외 금액(원)'
        for name in ('account_master', 'settlement_account'):
            existing = getattr(self.instance, f'{name}_id') if self.instance.pk else None
            allowed = selectable_accounts(self.user, [existing])
            self.fields[name].queryset = self.fields[name].queryset.filter(pk__in=allowed)
        if not self.instance.pk and not self.fields['account_master'].queryset.filter(pk=self.initial.get('account_master')).exists():
            self.initial.pop('account_master', None)
        if not self.is_bound:
            self.initial['vat_enabled'] = any(self.initial.get(name) for name in VAT_FIELDS if name != 'vat_trade')
        elif self.data.get('_vat_toggle_present') == '1' and not self.fields['vat_enabled'].to_python(self.data.get('vat_enabled')):
            for name in VAT_FIELDS:
                self.fields[name].disabled = True
                self.initial[name] = 0 if name in ('vat_amount', 'vat_deductible') else ''

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
        if data.get('vat_code') and data.get('vat_trade') != ('S' if data.get('kind') == Voucher.Kind.INCOME else 'P'):
            self.add_error('vat_trade', '수입은 매출, 지출은 매입으로 선택하세요.')
        if data.get('amount') and data.get('vat_amount') and data['amount'] + data['vat_amount'] > Decimal('99999999999999'):
            self.add_error('vat_amount', '공급가액과 부가세 합계는 99,999,999,999,999원 이하여야 합니다.')
        if not data.get('vat_code'):
            # Disabled trade selectors may have their default value on legacy non-VAT entries.
            data['vat_trade'] = ''
        return data

    class Meta:
        model = Voucher
        fields = ['date', 'kind', 'account_master', 'settlement_account', 'counterparty', 'amount'] + VAT_FIELDS + ['memo']
        widgets = {
            'date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'amount': MoneyInput(attrs={'min': 1, 'step': 1, 'placeholder': '0'}),
            'memo': forms.Textarea(attrs={'rows': 3, 'placeholder': '거래 내용을 입력하세요'}),
        }


class JournalHeaderForm(CounterpartySelectionMixin, forms.ModelForm):
    submission_token = forms.UUIDField(required=False, initial=uuid.uuid4, widget=forms.HiddenInput)
    memo = forms.CharField(label='적요', required=False, max_length=50,
        widget=forms.Textarea(attrs={'rows': 1, 'maxlength': 50, 'placeholder': '거래 내용을 입력하세요 (최대 50자)', 'style': 'resize:vertical'}))
    class Meta:
        model = Voucher
        fields = ['date', 'counterparty', 'memo', 'is_closing']
        help_texts = {'is_closing': '수익·비용을 이익잉여금으로 대체하는 결산전표에만 선택하세요. 대차대조표에는 반영하고 손익계산서에서는 제외합니다.'}
        widgets = {
            'date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'memo': forms.Textarea(attrs={'rows': 2}),
        }


class JournalRowForm(VatFormMixin, forms.Form):
    vat_enabled = forms.BooleanField(label='부가세 입력?', required=False,
        widget=forms.CheckboxInput(attrs={'aria-label': '부가세 입력 여부'}))
    vat_code = forms.ChoiceField(label='부가세 코드', choices=[('', '선택 안 함')] + VAT_CHOICES, required=False)
    vat_trade = forms.ChoiceField(label='부가세 매출·매입', choices=[('', '선택 안 함')] + TRADE_CHOICES, required=False)
    vat_document = forms.ChoiceField(label='증빙 종류', choices=[('', '선택 안 함')] + DOCUMENT_CHOICES, required=False)
    vat_deduction = forms.ChoiceField(label='매입세액 공제 구분', choices=[('', '선택 안 함')] + DEDUCTION_CHOICES, required=False)
    vat_amount = forms.DecimalField(label='부가세 금액(원)', required=False, min_value=0, max_digits=14, decimal_places=0)
    vat_deductible = forms.DecimalField(label='공통매입 중 공제할 세액(원)', required=False, min_value=0, max_digits=14, decimal_places=0)
    vat_reason = forms.CharField(label='불공제·안분 사유 / 검토 메모', max_length=300, required=False)
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.initial['vat_enabled'] = any(self.initial.get(name) for name in VAT_FIELDS)
        elif not self.fields['vat_enabled'].to_python(self.data.get(self.add_prefix('vat_enabled'))):
            # Hidden unchecked inputs must not persist stale or forged tax data.
            for field in VAT_FIELDS:
                self.fields[field].disabled = True
                self.initial[field] = 0 if field in ('vat_amount', 'vat_deductible') else ''
        for side in ('debit', 'credit'):
            name = f'{side}_account'
            self.fields[name].queryset = selectable_accounts(user, [self.initial.get(name)])
            self.fields[name].account_code = self.data.get(self.add_prefix(f'{side}_code'), '') if self.is_bound else ''
            self.fields[name].widget.attrs['list'] = f'{self.prefix}-{side}-suggestions'
            if not self.is_bound and self.initial.get(name):
                account = self.fields[name].queryset.filter(pk=self.initial[name]).first()
                if account:
                    self.initial[f'{side}_code'] = account.pk
                    self.initial[f'{side}_name'] = account.name
    debit_code = forms.CharField(label='차변 계정코드', max_length=4, required=False, widget=forms.TextInput(attrs={'inputmode': 'numeric', 'placeholder': '계정코드'}))
    debit_name = forms.CharField(label='차변 계정과목명 검색', max_length=100, required=False, widget=forms.TextInput(attrs={'placeholder': '계정과목명 직접 입력', 'autocomplete': 'off'}))
    credit_code = forms.CharField(label='대변 계정코드', max_length=4, required=False, widget=forms.TextInput(attrs={'inputmode': 'numeric', 'placeholder': '계정코드'}))
    credit_name = forms.CharField(label='대변 계정과목명 검색', max_length=100, required=False, widget=forms.TextInput(attrs={'placeholder': '계정과목명 직접 입력', 'autocomplete': 'off'}))
    debit_account = AccountEntryField(label='차변 계정과목', queryset=Account.objects.all(), required=False, widget=forms.TextInput(attrs={'autocomplete': 'off', 'placeholder': '계정과목명 직접 입력'}))
    debit_amount = forms.DecimalField(label='차변 금액', required=False, min_value=1, max_digits=14, decimal_places=0, widget=MoneyInput(attrs={'min': 1, 'step': 1}))
    credit_account = AccountEntryField(label='대변 계정과목', queryset=Account.objects.all(), required=False, widget=forms.TextInput(attrs={'autocomplete': 'off', 'placeholder': '계정과목명 직접 입력'}))
    credit_amount = forms.DecimalField(label='대변 금액', required=False, min_value=1, max_digits=14, decimal_places=0, widget=MoneyInput(attrs={'min': 1, 'step': 1}))
    memo = forms.CharField(label='라인 적요', required=False, max_length=50,
        widget=forms.Textarea(attrs={'rows': 1, 'maxlength': 50, 'placeholder': '이 행의 공통 거래 내용 (최대 50자)', 'style': 'resize:vertical'}))

    def clean(self):
        data = super().clean()
        if data.get('vat_enabled') and not data.get('vat_code'):
            self.add_error('vat_code', '부가세 코드를 선택하세요.')
        for side in ['debit', 'credit']:
            account, amount = data.get(f'{side}_account'), data.get(f'{side}_amount')
            code, name = data.get(f'{side}_code'), data.get(f'{side}_name')
            available = self.fields[f'{side}_account'].queryset
            if code:
                candidate = available.filter(pk=code).first()
                if not candidate:
                    self.add_error(f'{side}_code', '선택할 수 없는 계정코드입니다.')
                elif account and account.pk != candidate.pk:
                    self.add_error(f'{side}_code', '계정코드와 선택한 계정과목이 일치하지 않습니다.')
                else:
                    account = candidate
            if name:
                if account:
                    if name not in (account.pk, account.name, str(account)):
                        self.add_error(f'{side}_name', '계정과목명과 선택한 계정이 일치하지 않습니다.')
                else:
                    candidates = list(available.filter(pk=name)[:1]) or list(available.filter(name=name)[:2])
                    if len(candidates) == 1:
                        account = candidates[0]
                    else:
                        self.add_error(f'{side}_name', '목록에서 계정과목을 선택하거나 정확한 계정코드를 입력하세요.')
            if account:
                data[f'{side}_account'] = account
            if account is not None and amount is None and f'{side}_amount' not in self.errors:
                self.add_error(f'{side}_amount', '계정과목에 해당하는 금액을 입력하세요.')
            if amount is not None and account is None and f'{side}_account' not in self.errors:
                self.add_error(f'{side}_account', '금액에 해당하는 계정과목을 선택하세요.')
        if data.get('memo') and not any(data.get(f'{side}_{field}') for side in ['debit', 'credit'] for field in ['account', 'amount']):
            self.add_error('memo', '적요만 입력할 수 없습니다. 해당 행에 계정과 금액도 입력하세요.')
        if any(data.get(name) for name in VAT_FIELDS) and not (data.get('debit_account') or data.get('credit_account')):
            self.add_error('vat_code', '부가세 정보를 입력한 행에 계정과 금액도 입력하세요.')
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
        tax_rows = [form.cleaned_data for form in self.forms if form.cleaned_data.get('vat_code')]
        if tax_rows:
            for trade, account, side in [('S', '2107', 'credit'), ('P', '1209', 'debit')]:
                selected = [data for data in tax_rows if data['vat_trade'] == trade]
                if not selected:
                    continue
                expected = sum((data['vat_amount'] if trade == 'S' or data['vat_deduction'] == 'C01' else
                    data['vat_deductible'] if data['vat_deduction'] == 'C03' else Decimal(0) for data in selected), Decimal(0))
                actual = sum((form.cleaned_data.get(f'{side}_amount') or Decimal(0) for form in self.forms
                    if getattr(form.cleaned_data.get(f'{side}_account'), 'pk', None) == account), Decimal(0))
                opposite = 'debit' if side == 'credit' else 'credit'
                reversed_tax = any(getattr(form.cleaned_data.get(f'{opposite}_account'), 'pk', None) == account for form in self.forms)
                if actual != expected or reversed_tax:
                    raise forms.ValidationError(f'행별 부가세 합계에 맞춰 분개에 {account} 계정을 {"대변" if side == "credit" else "차변"} {expected:,.0f}원으로 입력하세요. 부가세는 자동 추가되지 않습니다.')


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
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['account'].queryset = visible_accounts(user)
    field_order = ['account', 'start', 'end']
    account = forms.ModelChoiceField(label='계정과목', queryset=Account.objects.all(), empty_label='계정코드 · 계정과목을 선택하세요')


class PartnerLedgerForm(PeriodForm):
    partner = forms.ChoiceField(label='거래처', choices=())

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        vouchers = Voucher.objects.filter(owner_id__in=member_ids(user)) if user is not None and user.is_authenticated else Voucher.objects.none()
        masters = Counterparty.objects.filter(owner_id__in=member_ids(user)) if user is not None and user.is_authenticated else Counterparty.objects.none()
        names = vouchers.filter(counterparty__isnull=True).exclude(partner='').order_by('partner').values_list('partner', flat=True).distinct()
        self.fields['partner'].choices = [('', '거래처를 선택하세요'), ('unassigned:', '거래처 미입력')] + [(f'master:{partner.pk}', partner.name) for partner in masters] + [('name:' + name, name + ' (기존 입력)') for name in names]
