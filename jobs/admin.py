from django.contrib import admin

from .models import (Application, CandidateProfile, EmployerProfile, Job,
                     Notification, Resume)


@admin.register(EmployerProfile)
class EmployerAdmin(admin.ModelAdmin):
    list_display = ("company_name", "user", "website")
    search_fields = ("company_name", "user__username")


@admin.register(CandidateProfile)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ("full_name", "user", "phone", "skills")
    search_fields = ("full_name", "user__username", "skills")


@admin.register(Resume)
class ResumeAdmin(admin.ModelAdmin):
    list_display = ("title", "candidate", "uploaded_at")


class ApplicationInline(admin.TabularInline):
    model = Application
    extra = 0
    fields = ("candidate", "status", "applied_at")
    readonly_fields = ("applied_at",)


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("title", "employer", "location", "job_type", "is_active", "created_at")
    list_filter = ("job_type", "is_active", "location")
    search_fields = ("title", "employer__company_name", "skills")
    inlines = [ApplicationInline]


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("candidate", "job", "status", "applied_at")
    list_filter = ("status",)
    search_fields = ("candidate__full_name", "job__title")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "message", "is_read", "created_at")
    list_filter = ("is_read",)
