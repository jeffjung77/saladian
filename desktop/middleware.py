from django.contrib.auth import get_user_model
from django.http import HttpResponseNotFound
from django.shortcuts import redirect


class PersonalEditionMiddleware:
    """Hide and deny subscription, public signup, board and system-management routes."""
    allowed = {'desktop_setup', 'desktop_health', 'login', 'logout', 'business_overview',
        'voucher_entry', 'dashboard', 'sales_new', 'expense_new', 'voucher_new', 'voucher_edit', 'voucher_delete',
        'income_statement', 'balance_sheet', 'account_ledger', 'partner_ledger',
        'accounts', 'account_new', 'account_status', 'counterparties', 'counterparty_new', 'counterparty_edit',
        'counterparty_certificate', 'counterparty_options', 'receipt_home', 'receipt_history', 'receipt_detail',
        'receipt_photo', 'receipt_analyze', 'receipt_expense', 'desktop_password'}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        name = request.resolver_match.url_name
        if name not in self.allowed:
            return HttpResponseNotFound('개인 PC용에서는 제공하지 않는 기능입니다.')
        if name not in ('desktop_setup', 'desktop_health') and not get_user_model().objects.exists():
            return redirect('desktop_setup')
        if name == 'business_overview' and not request.user.is_authenticated:
            return redirect('login')

