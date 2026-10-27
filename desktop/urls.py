from django.urls import path, include
from django.contrib.auth.views import PasswordChangeView
from . import views

urlpatterns = [
    path('desktop/setup/', views.setup, name='desktop_setup'),
    path('desktop/health/', views.health, name='desktop_health'),
    path('desktop/password/', PasswordChangeView.as_view(template_name='desktop/password.html', success_url='/vouchers/'), name='desktop_password'),
    path('', include('config.urls')),
]

