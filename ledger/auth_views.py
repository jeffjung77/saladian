from .pagination import page_size
from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_not_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm, UsernameField, PasswordChangeForm
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render, get_object_or_404
from django.views.decorators.http import require_http_methods
from django import forms
from django.db import transaction
from django.db import IntegrityError
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from django.core.paginator import Paginator
from django.db.models import Q
import re
from .models import BusinessProfile, Subscription


class UsernameAvailabilityForm(forms.ModelForm):
    class Meta:
        model = get_user_model()
        fields = ('username',)
        field_classes = {'username': UsernameField}

    def clean_username(self):
        username = self.cleaned_data['username']
        if self._meta.model.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('이미 사용 중인 아이디입니다. 다른 아이디를 입력하세요.')
        return username


@login_not_required
@require_GET
@never_cache
def check_username(request):
    form = UsernameAvailabilityForm({'username': request.GET.get('username', '')})
    if form.is_valid():
        return JsonResponse({'available': True, 'username': form.cleaned_data['username'], 'message': '사용 가능한 아이디입니다.'})
    return JsonResponse({'available': False, 'message': str(form.errors['username'][0])})


class RegistrationForm(UserCreationForm):
    grade = forms.ChoiceField(label='사용자 등급', choices=[('1', '1. 사용자'), ('2', '2. 관리자'), ('3', '3. 시스템관리자')], initial='1')
    email = forms.EmailField(label='이메일', required=True, max_length=254, widget=forms.EmailInput(attrs={'autocomplete': 'email'}))
    company_name = forms.CharField(label='업체명', max_length=150, widget=forms.TextInput(attrs={'autocomplete': 'organization'}))
    business_number = forms.CharField(label='사업자등록번호', max_length=12, help_text='숫자 10자리 또는 123-45-67890 형식으로 입력하세요.', widget=forms.TextInput(attrs={'placeholder': '123-45-67890', 'inputmode': 'numeric'}))
    contact_name = forms.CharField(label='담당자', max_length=100, widget=forms.TextInput(attrs={'autocomplete': 'name'}))
    contact_phone = forms.CharField(label='담당자 연락처', max_length=30, widget=forms.TextInput(attrs={'type': 'tel', 'autocomplete': 'tel', 'placeholder': '010-1234-5678'}))

    field_order = ['username', 'grade', 'email', 'company_name', 'business_number', 'contact_name', 'contact_phone', 'password1', 'password2']

    def __init__(self, *args, can_assign_grade=False, public_signup=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].help_text = '비밀번호는 대소문자, 숫자, 특수문자의 조합으로 8자리아상으로 구성을 추천합니다.'
        if public_signup:
            for name in ('company_name', 'business_number', 'contact_name', 'email', 'contact_phone'):
                self.fields[name].required = False
        if not can_assign_grade:
            self.fields['grade'].disabled = True
            self.fields['grade'].help_text = '사용자로 등록됩니다. 관리자·시스템관리자 등급은 시스템관리자만 지정할 수 있습니다.'

    def clean_business_number(self):
        value = self.cleaned_data['business_number']
        if not value and not self.fields['business_number'].required:
            return ''
        if not re.fullmatch(r'(?:[0-9]{10}|[0-9]{3}-[0-9]{2}-[0-9]{5})', value):
            raise forms.ValidationError('사업자등록번호는 숫자 10자리 또는 123-45-67890 형식으로 입력하세요.')
        digits = value.replace('-', '')
        return f'{digits[:3]}-{digits[3:5]}-{digits[5:]}'

    def clean_contact_phone(self):
        value = self.cleaned_data['contact_phone']
        if not value and not self.fields['contact_phone'].required:
            return ''
        if not re.fullmatch(r'\+?[0-9 ()-]+', value) or not 8 <= len(re.sub(r'[^0-9]', '', value)) <= 15:
            raise forms.ValidationError('연락처는 숫자 8~15자리로 입력하세요. +, 하이픈, 공백, 괄호를 사용할 수 있습니다.')
        return value

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        grade = self.cleaned_data['grade']
        user.is_staff = grade in ('2', '3')
        user.is_superuser = grade == '3'
        if commit:
            user.save()
            self.save_m2m()
            BusinessProfile.objects.create(user=user, **{name: self.cleaned_data[name] for name in ['company_name', 'business_number', 'contact_name', 'contact_phone']})
        return user

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ('username', 'email')
        labels = {'username': '아이디'}
        widgets = {'username': forms.TextInput(attrs={'autocomplete': 'username', 'autofocus': True})}


class LoginForm(AuthenticationForm):
    username = forms.CharField(label='아이디', max_length=150, widget=forms.TextInput(attrs={'autofocus': True, 'autocomplete': 'username'}))


class LedgerLoginView(LoginView):
    template_name = 'registration/login.html'
    authentication_form = LoginForm
    redirect_authenticated_user = True


class LedgerLogoutView(LogoutView):
    next_page = 'login'


@login_not_required
@require_http_methods(['GET', 'POST'])
def signup(request, system_mode=False):
    if request.user.is_authenticated and not system_mode:
        return redirect('voucher_entry')
    form = RegistrationForm(request.POST if request.method == 'POST' else None,
                            can_assign_grade=system_mode and request.user.is_superuser,
                            public_signup=not system_mode)
    if request.method == 'POST' and form.is_valid():
        try:
            form.save()
        except IntegrityError:
            if not get_user_model().objects.filter(username__iexact=form.cleaned_data['username']).exists():
                raise
            form.add_error('username', '이미 사용 중인 아이디입니다. 다른 아이디를 입력하세요.')
        else:
            if system_mode:
                messages.success(request, '신규 회원을 등록했습니다.')
                return redirect('member_list')
            messages.success(request, '사용자 등록이 완료되었습니다. 등록한 아이디와 비밀번호로 로그인하세요.')
            return redirect('login')
    return render(request, 'registration/signup.html', {'form': form, 'system_mode': system_mode})


@never_cache
@require_http_methods(['GET', 'POST'])
def system_signup(request):
    if not request.user.is_superuser:
        return render(request, 'ledger/permission_denied.html', status=403)
    return signup(request, system_mode=True)


@never_cache
@require_GET
def member_list(request):
    if not request.user.is_superuser:
        return render(request, 'ledger/permission_denied.html', status=403)
    query = request.GET.get('q', '').strip()[:100]
    members = get_user_model().objects.order_by('-date_joined', '-pk')
    total = members.count()
    active = members.filter(is_active=True).count()
    if query:
        members = members.filter(username__icontains=query)
    page = Paginator(members, page_size(request)).get_page(request.GET.get('page'))
    return render(request, 'ledger/member_list.html', {'page': page, 'q': query, 'total': total, 'active': active, 'inactive': total-active})


class MemberGradeForm(forms.Form):
    grade = forms.ChoiceField(label='사용자 등급', choices=RegistrationForm.base_fields['grade'].choices)


class MemberProfileForm(forms.ModelForm):
    email = forms.EmailField(label='이메일', required=True, max_length=254)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = True
        self.fields['contact_phone'].widget = forms.TextInput(attrs={'type': 'tel'})
        self.fields['business_phone'].widget = forms.TextInput(attrs={'type': 'tel'})

    clean_business_number = RegistrationForm.clean_business_number
    clean_contact_phone = RegistrationForm.clean_contact_phone

    def clean_business_phone(self):
        value = self.cleaned_data['business_phone']
        if not re.fullmatch(r'\+?[0-9 ()-]+', value) or not 8 <= len(re.sub(r'[^0-9]', '', value)) <= 15:
            raise forms.ValidationError('전화번호는 숫자 8~15자리로 입력하세요. +, 하이픈, 공백, 괄호를 사용할 수 있습니다.')
        return value

    class Meta:
        model = Subscription
        fields = ['company_name', 'business_number', 'business_type', 'business_category', 'business_address', 'business_phone', 'email', 'contact_name', 'contact_phone']
        labels = {'contact_phone': '담당자 전화번호'}


@never_cache
@require_http_methods(['GET', 'POST'])
def member_profile(request):
    form = PasswordChangeForm(request.user, request.POST if request.method == 'POST' else None)
    form.fields['new_password1'].help_text = '비밀번호는 대소문자, 숫자, 특수문자의 조합으로 8자리아상으로 구성을 추천합니다.'
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, '비밀번호를 변경했습니다.')
        return redirect('member_profile')
    return render(request, 'ledger/member_profile.html', {'form': form})


@never_cache
@require_http_methods(['GET', 'POST'])
def member_registration(request):
    profile = Subscription.objects.filter(user=request.user).first()
    initial = {}
    if profile is None:
        legacy = BusinessProfile.objects.filter(user=request.user).first()
        if legacy:
            initial = {name: getattr(legacy, name) for name in ['company_name', 'business_number', 'business_address', 'business_phone', 'contact_name', 'contact_phone']}
        initial['email'] = request.user.email
        profile = Subscription(user=request.user)
    form = MemberProfileForm(request.POST if request.method == 'POST' else None, instance=profile, initial=initial)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            profile = form.save(commit=False)
            profile.user = request.user
            profile.save()
            request._audit_target = str(profile.pk)
        messages.success(request, '사용등록 정보를 저장했습니다.')
        return redirect('member_registration')
    return render(request, 'ledger/member_registration.html', {'form': form})


@never_cache
@require_GET
def subscription_list(request):
    if not request.user.is_superuser:
        return render(request, 'ledger/permission_denied.html', status=403)
    query = request.GET.get('q', '').strip()[:100]
    subscriptions = Subscription.objects.select_related('user')
    total = subscriptions.count()
    if query:
        subscriptions = subscriptions.filter(Q(user__username__icontains=query) | Q(company_name__icontains=query) |
            Q(business_number__icontains=query) | Q(contact_name__icontains=query) | Q(email__icontains=query))
    page = Paginator(subscriptions, page_size(request)).get_page(request.GET.get('page'))
    return render(request, 'ledger/subscription_list.html', {'page': page, 'q': query, 'total': total})


@never_cache
@require_http_methods(['GET', 'POST'])
def subscription_edit(request, pk):
    if not request.user.is_superuser:
        return render(request, 'ledger/permission_denied.html', status=403)
    subscription = get_object_or_404(Subscription.objects.select_related('user'), pk=pk)
    form = MemberProfileForm(request.POST if request.method == 'POST' else None, instance=subscription)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, '구독 등록정보를 수정했습니다.')
        return redirect('subscription_list')
    return render(request, 'ledger/subscription_edit.html', {'form': form, 'subscription': subscription})


@never_cache
@require_http_methods(['GET', 'POST'])
def member_grade(request, pk):
    if not request.user.is_superuser:
        return render(request, 'ledger/permission_denied.html', status=403)
    member = get_object_or_404(get_user_model(), pk=pk)
    initial = '3' if member.is_superuser else '2' if member.is_staff else '1'
    form = MemberGradeForm(request.POST if request.method == 'POST' else None, initial={'grade': initial})
    if request.method == 'POST' and form.is_valid():
        grade = form.cleaned_data['grade']
        with transaction.atomic():
            # Serialize changes to existing system administrators before checking the last one.
            administrators = list(get_user_model().objects.select_for_update().filter(is_superuser=True, is_active=True).order_by('pk'))
            member = get_object_or_404(get_user_model().objects.select_for_update(), pk=pk)
            if member.is_active and member.is_superuser and grade != '3' and len(administrators) <= 1:
                form.add_error('grade', '마지막 활성 시스템관리자의 등급은 변경할 수 없습니다. 다른 시스템관리자를 먼저 지정하세요.')
            else:
                member.is_staff = grade in ('2', '3')
                member.is_superuser = grade == '3'
                member.save(update_fields=['is_staff', 'is_superuser'])
                messages.success(request, f'{member.username}님의 등급을 {dict(form.fields["grade"].choices)[grade]}로 변경했습니다.')
                return redirect('business_overview' if member.pk == request.user.pk and grade != '3' else 'member_list')
    return render(request, 'ledger/member_grade.html', {'member': member, 'form': form})
