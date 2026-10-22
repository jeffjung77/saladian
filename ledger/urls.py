from django.urls import path
from . import views

urlpatterns = [
    path('accounts/ledger/', views.account_ledger, name='account_ledger'),
    path('reports/balance-sheet/', views.balance_sheet, name='balance_sheet'),
    path('reports/income-statement/', views.income_statement, name='income_statement'),
    path('accounts/', views.accounts, name='accounts'),
    path('partners/ledger/', views.partner_ledger, name='partner_ledger'),
    path('', views.dashboard, name='dashboard'),
    path('vouchers/new/', views.edit, name='voucher_new'),
    path('vouchers/sales/new/', views.edit, {'entry_type': 'sales'}, name='sales_new'),
    path('vouchers/expenses/new/', views.edit, {'entry_type': 'expense'}, name='expense_new'),
    path('vouchers/<int:pk>/edit/', views.edit, name='voucher_edit'),
    path('vouchers/<int:pk>/delete/', views.delete, name='voucher_delete'),
]
