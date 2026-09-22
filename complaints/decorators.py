from functools import wraps
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib import messages


def admin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        is_admin = (
            request.user.is_superuser or 
            request.user.is_staff or 
            (hasattr(request.user, 'profile') and request.user.profile.is_admin())
        )
        if not is_admin:
            raise PermissionDenied("You do not have administrative privileges to view this page.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def staff_or_authority_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')

        can_manage = (
            request.user.is_superuser or 
            request.user.is_staff or 
            (hasattr(request.user, 'profile') and request.user.profile.can_manage_complaints())
        )
        if not can_manage:
            raise PermissionDenied("You do not have authority privileges to perform this action.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def active_user_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not request.user.is_active:
            messages.error(request, "Your account has been deactivated. Please contact support.")
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return _wrapped_view
