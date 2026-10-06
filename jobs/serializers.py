import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers

from .models import (Application, CandidateProfile, EmployerProfile, Job,
                     Notification, Resume)

User = get_user_model()


class SignupSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    role = serializers.ChoiceField(choices=["employer", "candidate"])
    company_name = serializers.CharField(required=False, allow_blank=True)
    full_name = serializers.CharField(required=False, allow_blank=True)

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("This username is taken.")
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate(self, attrs):
        if attrs["role"] == "employer" and not attrs.get("company_name"):
            raise serializers.ValidationError({"company_name": "Required for employers."})
        if attrs["role"] == "candidate" and not attrs.get("full_name"):
            raise serializers.ValidationError({"full_name": "Required for candidates."})
        return attrs

    @transaction.atomic
    def create(self, data):
        user = User.objects.create_user(data["username"], data["email"], data["password"])
        if data["role"] == "employer":
            EmployerProfile.objects.create(user=user, company_name=data["company_name"])
        else:
            CandidateProfile.objects.create(user=user, full_name=data["full_name"])
        return user


class JobSerializer(serializers.ModelSerializer):
    company = serializers.CharField(source="employer.company_name", read_only=True)
    job_type_display = serializers.CharField(source="get_job_type_display", read_only=True)

    class Meta:
        model = Job
        fields = ["id", "title", "company", "description", "location", "job_type",
                  "job_type_display", "salary_min", "salary_max", "skills",
                  "is_active", "created_at"]
        read_only_fields = ["created_at"]

    def validate(self, attrs):
        lo = attrs.get("salary_min", getattr(self.instance, "salary_min", None))
        hi = attrs.get("salary_max", getattr(self.instance, "salary_max", None))
        if lo is not None and hi is not None and lo > hi:
            raise serializers.ValidationError("salary_min cannot be greater than salary_max.")
        return attrs


class JobBriefSerializer(serializers.ModelSerializer):
    company = serializers.CharField(source="employer.company_name", read_only=True)

    class Meta:
        model = Job
        fields = ["id", "title", "company", "location"]


class ResumeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resume
        fields = ["id", "title", "file", "uploaded_at"]
        read_only_fields = ["uploaded_at"]

    def validate_file(self, f):
        ext = os.path.splitext(f.name)[1].lower()
        if ext not in settings.RESUME_ALLOWED_EXTENSIONS:
            raise serializers.ValidationError("Upload a PDF, DOC or DOCX file.")
        if f.size > settings.RESUME_MAX_BYTES:
            raise serializers.ValidationError("File is larger than 5 MB.")
        return f


class CandidateSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = CandidateProfile
        fields = ["id", "full_name", "email", "phone", "skills"]


class ApplicationSerializer(serializers.ModelSerializer):
    job = JobBriefSerializer(read_only=True)
    candidate = CandidateSerializer(read_only=True)
    resume = ResumeSerializer(read_only=True)

    class Meta:
        model = Application
        fields = ["id", "job", "candidate", "resume", "cover_letter", "status",
                  "note", "applied_at", "updated_at"]


class ApplyInputSerializer(serializers.Serializer):
    resume = serializers.IntegerField(required=False)
    cover_letter = serializers.CharField(required=False, allow_blank=True)


class StatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["reviewing", "shortlisted", "rejected", "hired"])
    note = serializers.CharField(required=False, allow_blank=True)


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "message", "is_read", "created_at"]
