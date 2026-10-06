from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from jobs.models import EmployerProfile, Job

User = get_user_model()


class Command(BaseCommand):
    help = "Create a demo employer (demo_employer / demo12345) with sample jobs."

    def handle(self, *args, **options):
        user, created = User.objects.get_or_create(
            username="demo_employer", defaults={"email": "hr@example.com"})
        if created:
            user.set_password("demo12345")
            user.save()
        emp, _ = EmployerProfile.objects.get_or_create(
            user=user, defaults={"company_name": "Demo Tech Ltd"})
        samples = [
            ("Backend Developer", "Build REST APIs with Django.", "Chattogram", "full_time", 40000, 70000, "python,django,sql"),
            ("Node.js Intern", "Learn Express and MongoDB.", "Remote", "internship", 5000, 10000, "node,express,mongodb"),
            ("DevOps Engineer", "CI/CD and cloud infrastructure.", "Dhaka", "contract", 60000, 100000, "docker,aws,linux"),
        ]
        for title, desc, loc, jt, lo, hi, skills in samples:
            Job.objects.get_or_create(employer=emp, title=title, defaults=dict(
                description=desc, location=loc, job_type=jt,
                salary_min=lo, salary_max=hi, skills=skills))
        self.stdout.write(self.style.SUCCESS("Demo employer and jobs created."))
