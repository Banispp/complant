from django.contrib import admin
from .models import UserProfile, ComplaintCategory, Complaint, ComplaintResponse, ComplaintStatusHistory, AcademicClass


@admin.register(AcademicClass)
class AcademicClassAdmin(admin.ModelAdmin):
    list_display = ('name', 'department', 'mentor', 'created_at')
    list_filter = ('department',)
    search_fields = ('name', 'department', 'mentor__username', 'mentor__first_name', 'mentor__last_name')


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'academic_class', 'department', 'phone', 'created_at')
    list_filter = ('role', 'academic_class', 'department')
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name', 'department')


@admin.register(ComplaintCategory)
class ComplaintCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')


class ComplaintResponseInline(admin.TabularInline):
    model = ComplaintResponse
    extra = 0
    readonly_fields = ('responder', 'message', 'created_at')
    can_delete = False


class ComplaintStatusHistoryInline(admin.TabularInline):
    model = ComplaintStatusHistory
    extra = 0
    readonly_fields = ('old_status', 'new_status', 'changed_by', 'comment', 'created_at')
    can_delete = False


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ('complaint_id', 'title', 'user', 'category', 'current_level', 'priority', 'status', 'assigned_to', 'created_at')
    list_filter = ('status', 'current_level', 'priority', 'category', 'created_at')
    search_fields = ('complaint_id', 'title', 'description', 'user__username', 'user__email')
    readonly_fields = ('complaint_id', 'created_at', 'updated_at', 'resolved_at', 'closed_at')
    inlines = [ComplaintResponseInline, ComplaintStatusHistoryInline]


@admin.register(ComplaintResponse)
class ComplaintResponseAdmin(admin.ModelAdmin):
    list_display = ('complaint', 'responder', 'created_at')
    search_fields = ('complaint__complaint_id', 'responder__username', 'message')
    readonly_fields = ('created_at',)


@admin.register(ComplaintStatusHistory)
class ComplaintStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ('complaint', 'old_status', 'new_status', 'changed_by', 'created_at')
    list_filter = ('new_status', 'created_at')
    search_fields = ('complaint__complaint_id', 'changed_by__username', 'comment')
    readonly_fields = ('created_at',)
