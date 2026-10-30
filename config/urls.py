"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from ledger.auth_views import LedgerLoginView, LedgerLogoutView, signup, check_username
from ledger.idle_session import activity

urlpatterns = [
    path('accounts/activity/', activity, name='session_activity'),
    path('accounts/login/', LedgerLoginView.as_view(), name='login'),
    path('accounts/logout/', LedgerLogoutView.as_view(), name='logout'),
    path('accounts/signup/', signup, name='signup'),
    path('accounts/check-username/', check_username, name='check_username'),
    path('', include('ledger.urls')),
    path('admin/', admin.site.urls),
]
