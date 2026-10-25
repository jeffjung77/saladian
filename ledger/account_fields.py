from django import forms


class AccountEntryField(forms.ModelChoiceField):
    """Resolve typed codes or exact names against this field's allowed accounts."""
    def to_python(self, value):
        if value in self.empty_values:
            return None
        text = str(value).strip()
        account = self.queryset.filter(pk=text).first()
        if account:
            return account
        if ' · ' in text:
            code, name = text.split(' · ', 1)
            account = self.queryset.filter(pk=code.strip(), name=name.strip()).first()
            if account:
                return account
        matches = list(self.queryset.filter(name=text)[:2])
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise forms.ValidationError('같은 이름의 계정이 여러 개입니다. 계정코드를 입력하세요.')
        raise forms.ValidationError('사용 가능한 계정코드 또는 정확한 계정과목명을 입력하세요.')


