from django.urls import path
from . import views
from . import auth_views
from . import audit_views
from . import company_views
from . import board_views
from . import receipt_views
from . import vision_usage_views

urlpatterns = [
    path('receipts/', receipt_views.receipt_home, name='receipt_home'),
    path('receipts/history/', receipt_views.receipt_history, name='receipt_history'),
    path('receipts/<int:pk>/', receipt_views.receipt_detail, name='receipt_detail'),
    path('receipts/<int:pk>/analyze/', receipt_views.receipt_analyze, name='receipt_analyze'),
    path('receipts/<int:pk>/expense/', receipt_views.receipt_expense, name='receipt_expense'),
    path('receipts/<int:pk>/photo/', receipt_views.receipt_photo, name='receipt_photo'),
    path('board/<int:pk>/comments/new/', board_views.board_comment_new, name='board_comment_new'),
    path('board/comments/<int:pk>/delete/', board_views.board_comment_delete, name='board_comment_delete'),
    path('board/attachments/<int:pk>/', board_views.board_attachment, name='board_attachment'),
    path('board/', board_views.board_list, name='board_list'),
    path('board/new/', board_views.board_edit, name='board_new'),
    path('board/<int:pk>/', board_views.board_detail, name='board_detail'),
    path('board/<int:pk>/edit/', board_views.board_edit, name='board_edit'),
    path('board/<int:pk>/delete/', board_views.board_delete, name='board_delete'),
    path('system/companies/', company_views.company_list, name='company_list'),
    path('system/companies/vision-usage/', vision_usage_views.vision_usage, name='vision_usage'),
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
