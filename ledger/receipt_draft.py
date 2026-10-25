from .account_fields import AccountEntryField
"""Conservative OCR suggestions. Missing or ambiguous values require manual review."""
import re
from datetime import date
from decimal import Decimal
from .forms import VoucherForm
from .models import Counterparty
from django import forms
from .widgets import MoneyInput


def extract_draft(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    result = {}
    dates = set()
    for year, month, day in re.findall(r'(?<!\d)(20\d{2})[./년\-]\s*(\d{1,2})[./월\-]\s*(\d{1,2})(?!\d)', text):
        try:
            dates.add(date(int(year), int(month), int(day)))
        except ValueError:
            pass
    if len(dates) == 1:
        result['date'] = dates.pop()
    labels = {'amount': r'공\s*급\s*가\s*액|과\s*세\s*금\s*액',
              'vat_amount': r'부\s*가\s*세|부\s*가\s*가\s*치\s*세|VAT',
              'receipt_total': r'합\s*계|총\s*액|결\s*제\s*금\s*액|승\s*인\s*금\s*액|TOTAL'}
    for field, pattern in labels.items():
        values = set()
        for i, line in enumerate(lines):
            match = re.search(pattern, line, re.I)
            if not match:
                continue
            tail = line[match.end():].strip(' :：₩원')
            if not tail and i + 1 < len(lines):
                tail = lines[i+1].strip(' :：₩원')
            if re.fullmatch(r'\d[\d,]*\s*원?', tail):
                value = Decimal(re.sub(r'[^0-9]', '', tail))
                if value <= 99999999999999:
                    values.add(value)
        if len(values) == 1:
            result[field] = values.pop()
    # Derive supply only when total and VAT are both explicitly present.
    if 'amount' not in result and 'receipt_total' in result and 'vat_amount' in result:
        amount = result['receipt_total'] - result['vat_amount']
        if amount > 0:
            result['amount'] = amount
    for line in lines:
        match = re.match(r'(?:가맹점명|상호명?|매장명)\s*[:：]\s*(.+)', line)
        if match:
            result['merchant'] = match[1][:100]
            break
    result['possible_cancel'] = bool(re.search(r'취소|환불|CANCEL|REFUND', text, re.I))
    return result


class ReceiptExpenseForm(VoucherForm):
    merchant = forms.CharField(label='가맹점명', max_length=100)
    receipt_total = forms.DecimalField(label='영수증 결제합계(원)', min_value=1, max_digits=14, decimal_places=0, widget=MoneyInput())
    confirmed = forms.BooleanField(label='원본 영수증과 거래일·가맹점·금액·계정을 확인했습니다. 취소 영수증이 아닌 비용 거래입니다.')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['vat_amount'].required = True
        self.fields['date'].initial = None
        for name in ('account_master', 'settlement_account'):
            original = self.fields[name]
            self.fields[name] = AccountEntryField(queryset=original.queryset, required=original.required,
                label=original.label, help_text=original.help_text,
                widget=forms.TextInput(attrs={'list': f'{name}-suggestions', 'autocomplete': 'off',
                    'placeholder': '계정코드 또는 계정과목명 직접 입력'}))

    def clean(self):
        data = super().clean()
        amount, vat, total = data.get('amount'), data.get('vat_amount'), data.get('receipt_total')
        if amount is not None and vat is not None and total is not None and amount + vat != total:
            self.add_error('receipt_total', '공급가액과 부가세의 합계가 영수증 결제합계와 일치해야 합니다.')
        if data.get('counterparty') and data.get('merchant') != data['counterparty'].name:
            self.add_error('merchant', '선택한 거래처명과 가맹점명을 일치시켜 주세요.')
        return data


def draft_initial(item, user):
    data = extract_draft(item.ocr_text)
    data.pop('possible_cancel', None)
    data.update(vat_document='D03', vat_deduction='C09', vat_reason='영수증 OCR 초안: 부가세 구분 및 공제 여부 확인 필요')
    # Do not silently inherit today's date or zero VAT for unrecognized fields.
    data.setdefault('date', None)
    data.setdefault('vat_amount', None)
    if data.get('merchant'):
        candidates = list(Counterparty.objects.filter(owner=user, name=data['merchant'])[:2])
        if len(candidates) == 1:
            data['counterparty'] = candidates[0].pk
        data['memo'] = data['merchant']
    return data
