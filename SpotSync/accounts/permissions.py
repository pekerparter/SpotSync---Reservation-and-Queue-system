"""Business-scoped authorization shared by HTML and JSON staff endpoints."""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from .models import Business


def business_permission_required(permission=None, *, owner_only=False):
    def decorate(view):
        @wraps(view)
        @login_required
        def authorized(request, business_id, *args, **kwargs):
            business = get_object_or_404(Business, pk=business_id)
            user = request.user
            member = user.is_active and (
                user.is_superuser or (user.is_business_staff and user.business_id == business.pk)
            )
            allowed = member
            if owner_only:
                allowed = member and (user.is_superuser or user.staff_role == 'OWNER')
            elif permission:
                allowed = business.user_has_permission(user, permission)
            if not allowed:
                return JsonResponse({'success': False, 'message': 'Permission denied.'}, status=403)
            request.business = business
            return view(request, business_id, *args, **kwargs)

        return authorized

    return decorate


def can_assign_staff_role(actor, target, role):
    """Keep owner/manager restrictions consistent across add and edit endpoints."""
    if not isinstance(role, str) or role not in {'OWNER', 'MANAGER', 'WORKER'}:
        return False
    if target.pk == actor.pk and role != actor.staff_role:
        return False
    if actor.is_superuser or actor.staff_role == 'OWNER':
        return True
    return (
        actor.staff_role == 'MANAGER'
        and target.staff_role not in {'OWNER', 'MANAGER'}
        and role != 'OWNER'
    )
