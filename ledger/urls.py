from django.urls import path
from . import views
from . import auth_views
from . import audit_views
from . import company_views

urlpatterns = [
    path('system/companies/', company_views.company_list, name='company_list'),
    path('system/companies/<int:company_id>/', company_views.company_detail, name='company_detail'),
    path('system/logs/', audit_views.audit_logs, name='audit_logs'),
    path('system/subscriptions/', auth_views.subscription_list, name='subscription_list'),
    path('system/subscriptions/<int:pk>/edit/', auth_views.subscription_edit, name='subscription_edit'),
    path('accounts/profile/', auth_views.member_profile, name='member_profile'),
    path('accounts/registration/', auth_views.member_registration, name='member_registration'),
    path('system/members/', auth_views.member_list, name='member_list'),
    path('system/members/new/', auth_views.system_signup, name='system_signup'),
    path('system/members/<int:pk>/grade/', auth_views.member_grade, name='member_grade'),
    path('', views.business_overview, name='business_overview'),
    path('partners/<int:pk>/certificate/', views.counterparty_certificate, name='counterparty_certificate'),
    path('partners/', views.counterparties, name='counterparties'),
    path('partners/new/', views.counterparty_edit, name='counterparty_new'),
    path('partners/options/', views.counterparty_options, name='counterparty_options'),
    path('partners/<int:pk>/edit/', views.counterparty_edit, name='counterparty_edit'),
    path('accounts/ledger/', views.account_ledger, name='account_ledger'),
    path('reports/balance-sheet/', views.balance_sheet, name='balance_sheet'),
    path('reports/income-statement/', views.income_statement, name='income_statement'),
    path('accounts/', views.accounts, name='accounts'),
    path('accounts/new/', views.account_new, name='account_new'),
    path('accounts/<str:code>/status/', views.account_status, name='account_status'),
    path('partners/ledger/', views.partner_ledger, name='partner_ledger'),
    path('vouchers/', views.voucher_entry, name='voucher_entry'),
    path('vouchers/summary/', views.dashboard, name='dashboard'),
    path('vouchers/new/', views.edit, name='voucher_new'),
    path('vouchers/sales/new/', views.edit, {'entry_type': 'sales'}, name='sales_new'),
    path('vouchers/expenses/new/', views.edit, {'entry_type': 'expense'}, name='expense_new'),
    path('vouchers/<int:pk>/edit/', views.edit, name='voucher_edit'),
    path('vouchers/<int:pk>/delete/', views.delete, name='voucher_delete'),
]
