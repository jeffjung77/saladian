from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('vouchers/new/', views.edit, name='voucher_new'),
    path('vouchers/<int:pk>/edit/', views.edit, name='voucher_edit'),
    path('vouchers/<int:pk>/delete/', views.delete, name='voucher_delete'),
]
