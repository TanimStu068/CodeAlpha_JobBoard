from django.conf import settings
from django.db import models


class EmployerProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name="employer_profile")
    company_name = models.CharField(max_length=200)
    website = models.URLField(blank=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.company_name


class CandidateProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name="candidate_profile")
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=30, blank=True)
    skills = models.CharField(max_length=300, blank=True, help_text="Comma-separated")
    bio = models.TextField(blank=True)

    def __str__(self):
        return self.full_name


def resume_path(instance, filename):
    return f"resumes/user_{instance.candidate.user_id}/{filename}"


class Resume(models.Model):
    candidate = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE,
                                  related_name="resumes")
    title = models.CharField(max_length=120)
    file = models.FileField(upload_to=resume_path)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.candidate} - {self.title}"


class Job(models.Model):
    FULL_TIME, PART_TIME, CONTRACT, INTERNSHIP, REMOTE = (
        "full_time", "part_time", "contract", "internship", "remote")
    JOB_TYPES = [
        (FULL_TIME, "Full time"), (PART_TIME, "Part time"), (CONTRACT, "Contract"),
        (INTERNSHIP, "Internship"), (REMOTE, "Remote"),
    ]

    employer = models.ForeignKey(EmployerProfile, on_delete=models.CASCADE, related_name="jobs")
    title = models.CharField(max_length=200)
    description = models.TextField()
    location = models.CharField(max_length=150)
    job_type = models.CharField(max_length=20, choices=JOB_TYPES, default=FULL_TIME)
    salary_min = models.PositiveIntegerField(null=True, blank=True)
    salary_max = models.PositiveIntegerField(null=True, blank=True)
    skills = models.CharField(max_length=300, blank=True, help_text="Comma-separated")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} @ {self.employer.company_name}"


class Application(models.Model):
    APPLIED, REVIEWING, SHORTLISTED, REJECTED, HIRED, WITHDRAWN = (
        "applied", "reviewing", "shortlisted", "rejected", "hired", "withdrawn")
    STATUS_CHOICES = [
        (APPLIED, "Applied"), (REVIEWING, "Reviewing"), (SHORTLISTED, "Shortlisted"),
        (REJECTED, "Rejected"), (HIRED, "Hired"), (WITHDRAWN, "Withdrawn"),
    ]

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="applications")
    candidate = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE,
                                  related_name="applications")
    resume = models.ForeignKey(Resume, on_delete=models.SET_NULL, null=True, blank=True)
    cover_letter = models.TextField(blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=APPLIED)
    note = models.TextField(blank=True, help_text="Message from the employer")
    applied_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-applied_at"]
        constraints = [
            models.UniqueConstraint(fields=["job", "candidate"], name="one_application_per_job")
        ]

    def __str__(self):
        return f"{self.candidate} -> {self.job} ({self.status})"


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="notifications")
    message = models.CharField(max_length=300)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user}: {self.message[:40]}"
