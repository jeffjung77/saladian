from functools import wraps
from django.shortcuts import render


def management_required(view):
    @wraps(view)
    def checked(request, *args, **kwargs):
        if not (request.user.is_staff or request.user.is_superuser):
            return render(request, 'ledger/permission_denied.html', status=403)
        return view(request, *args, **kwargs)
    return checked
