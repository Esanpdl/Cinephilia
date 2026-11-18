from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.core.exceptions import ValidationError

from .models import Profile, is_main_admin_user

User = get_user_model()


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = "Profile"
    fields = ["display_name", "bio", "is_film_student", "is_main_admin"]
    readonly_fields = ["is_main_admin"]


class CustomUserAdmin(BaseUserAdmin):
    inlines = [ProfileInline]

    def delete_model(self, request, obj):
        if is_main_admin_user(obj):
            raise ValidationError("The main administrator cannot be deleted.")
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            if is_main_admin_user(obj):
                raise ValidationError("The main administrator cannot be deleted.")
        super().delete_queryset(request, queryset)

    def save_model(self, request, obj, form, change):
        original = User.objects.select_related('profile').filter(pk=obj.pk).first() if change else None
        if original and is_main_admin_user(original):
            # Guard privileges from being revoked
            obj.is_staff = True
            obj.is_superuser = True
            obj.is_active = True
        super().save_model(request, obj, form, change)


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    readonly_fields = ["is_main_admin"]
    list_display = ["user", "display_name", "is_main_admin", "is_film_student", "created_at"]
    list_filter = ["is_main_admin", "is_film_student"]
    search_fields = ["user__username", "user__email", "display_name"]

    def has_delete_permission(self, request, obj=None):
        return False if obj and obj.is_main_admin else super().has_delete_permission(request, obj)
