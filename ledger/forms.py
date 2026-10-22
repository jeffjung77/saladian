from django import forms
from .models import Voucher


class VoucherForm(forms.ModelForm):
    class Meta:
        model = Voucher
        fields = ['date', 'kind', 'account', 'partner', 'amount', 'memo']
        widgets = {
            'date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'account': forms.TextInput(attrs={'list': 'accounts', 'placeholder': '예: 매출, 임차료, 재료비'}),
            'amount': forms.NumberInput(attrs={'min': 1, 'step': 1, 'placeholder': '0'}),
            'memo': forms.Textarea(attrs={'rows': 3, 'placeholder': '거래 내용을 입력하세요'}),
        }


class PeriodForm(forms.Form):
    start = forms.DateField(label='시작일', required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    end = forms.DateField(label='종료일', required=False, widget=forms.DateInput(attrs={'type': 'date'}))

    def clean(self):
        data = super().clean()
        if data.get('start') and data.get('end') and data['start'] > data['end']:
            raise forms.ValidationError('종료일은 시작일 이후여야 합니다.')
        return data
