from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Ministry


@admin.register(Ministry)
class MinistryAdmin(admin.ModelAdmin):
    list_display = ('name', 'abbreviation', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'abbreviation')


class CustomUserAdmin(UserAdmin):
    model = CustomUser
    # Fields to display in admin list view
    list_display = ('email', 'username', 'first_name', 'last_name', 'ministry', 'is_staff', 'is_active' , 'trial', 'waiting_period')
    list_filter = ('is_staff', 'is_active', 'ministry')
    
    # Fields for add/edit form
    fieldsets = (
        (None, {'fields': ('email', 'username', 'first_name', 'last_name', 'password' , 'trial', 'waiting_period')}),
        ('Permissions', {'fields': ('is_staff', 'is_active', 'is_superuser', 'groups', 'user_permissions')}),
        ('Additional Info', {'fields': ('photo','bio','excellence','ministry','token','tokenExpiration','is_first_time')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'first_name', 'last_name', 'password1', 'password2', 'is_staff', 'is_active' , 'trial', 'waiting_period')}
        ),
    )
    
    search_fields = ('email', 'username')
    ordering = ('email',)

# Register your CustomUser with the custom admin
admin.site.register(CustomUser, CustomUserAdmin)
