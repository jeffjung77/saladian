import re
from django import forms


class MoneyInput(forms.TextInput):
    """원 단위 금액 표시와 POST 값의 천 단위 구분자를 처리한다."""
    def __init__(self, attrs=None):
        attributes = {'inputmode': 'numeric', 'data-money': 'true', 'autocomplete': 'off'}
        attributes.update({key: value for key, value in (attrs or {}).items() if key not in ('min', 'step')})
        super().__init__(attributes)

    def format_value(self, value):
        value = super().format_value(value)
        if value is None:
            return None
        if re.fullmatch(r'-?[0-9]+', str(value)):
            sign = '-' if str(value).startswith('-') else ''
            digits = str(value).lstrip('-')
            return sign + re.sub(r'\B(?=(\d{3})+(?!\d))', ',', digits)
        return value

    def value_from_datadict(self, data, files, name):
        value = super().value_from_datadict(data, files, name)
        if isinstance(value, str) and re.fullmatch(r'-?[0-9]{1,3}(?:,[0-9]{3})+', value.strip()):
            return value.strip().replace(',', '')
        return value
