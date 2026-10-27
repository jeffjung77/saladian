import secrets
from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_not_required
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render, redirect
from django.views.decorators.http import require_GET, require_http_methods
from django.views.decorators.cache import never_cache
from ledger.models import BusinessProfile


def desktop_context(request):
    return {'desktop_mode': True}


class SetupForm(UserCreationForm):
    company_name = forms.CharField(label='업체명', max_length=150)
    class Meta:
        model = get_user_model()
        fields = ['username', 'company_name', 'password1', 'password2']


@login_not_required
@never_cache
@require_http_methods(['GET', 'POST'])
def setup(request):
    User = get_user_model()
    if User.objects.exists():
        return redirect('login')
    form = SetupForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            if User.objects.exists():
                return redirect('login')
            user = form.save(commit=False)
            user.is_staff = True
            user.is_superuser = False
            user.save()
            BusinessProfile.objects.create(user=user, company_name=form.cleaned_data['company_name'],
                business_number='', contact_name='', contact_phone='')
        login(request, user)
        return redirect('voucher_entry')
    return render(request, 'desktop/setup.html', {'form': form})


@login_not_required
@require_GET
def health(request):
    if not settings.DESKTOP_LAUNCH_TOKEN or not secrets.compare_digest(request.headers.get('X-BPMS-Token', ''), settings.DESKTOP_LAUNCH_TOKEN):
        return HttpResponseForbidden()
    return JsonResponse({'application': 'BPMS Easybook Personal', 'ready': True})

