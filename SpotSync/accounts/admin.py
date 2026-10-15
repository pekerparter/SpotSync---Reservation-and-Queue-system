from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Business, BusinessRolePermission, Category, CustomUser, Queue


class BusinessRolePermissionInline(admin.TabularInline):
    model = BusinessRolePermission
    extra = 1

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    fieldsets = (
        (None, {'fields': ('username', 'email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'phone_number')}),
        ('Business Info', {'fields': ('staff_role', 'business')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important Dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'phone_number', 'password1', 'password2'),
        }),
    )
    list_display = ('email', 'username', 'staff_role', 'business', 'is_staff')
    list_filter = ('staff_role', 'business', 'is_staff')
    search_fields = ('email', 'username', 'first_name', 'last_name')
    ordering = ('email',)

@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ('name', 'address', 'phone_number')
    inlines = [BusinessRolePermissionInline]

@admin.register(BusinessRolePermission)
class BusinessRolePermissionAdmin(admin.ModelAdmin):
    list_display = ('business', 'role', 'can_edit_info', 'can_edit_staff', 'can_display_customers', 'can_edit_service', 'can_edit_availability')

admin.site.register(Category)
admin.site.register(Queue)