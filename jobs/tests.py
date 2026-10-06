import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APIClient, APITestCase

from .models import Application, CandidateProfile, EmployerProfile, Job, Notification

User = get_user_model()
TMP_MEDIA = tempfile.mkdtemp()


def pdf(name="cv.pdf", size=100):
    return SimpleUploadedFile(name, b"%PDF-1.4 " + b"x" * size, content_type="application/pdf")


@override_settings(MEDIA_ROOT=TMP_MEDIA)
class JobBoardTests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.emp_user = User.objects.create_user("acme", "hr@acme.com", "pass12345")
        self.employer = EmployerProfile.objects.create(user=self.emp_user, company_name="Acme")
        self.other_emp_user = User.objects.create_user("beta", "hr@beta.com", "pass12345")
        self.other_employer = EmployerProfile.objects.create(user=self.other_emp_user, company_name="Beta")
        self.cand_user = User.objects.create_user("sara", "sara@x.com", "pass12345")
        self.candidate = CandidateProfile.objects.create(user=self.cand_user, full_name="Sara Khan")
        self.job = Job.objects.create(
            employer=self.employer, title="Django Developer", description="APIs",
            location="Chattogram", job_type="full_time", salary_min=30000,
            salary_max=60000, skills="python,django")
        self.as_emp = APIClient(); self.as_emp.force_authenticate(self.emp_user)
        self.as_other = APIClient(); self.as_other.force_authenticate(self.other_emp_user)
        self.as_cand = APIClient(); self.as_cand.force_authenticate(self.cand_user)

    def upload_resume(self):
        return self.as_cand.post("/api/resumes/", {"title": "CV", "file": pdf()}, format="multipart")

    # ----- auth
    def test_signup_roles(self):
        r = self.client.post("/api/auth/signup/", {
            "username": "newco", "email": "a@b.com", "password": "longpass123",
            "role": "employer", "company_name": "NewCo"})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["role"], "employer")
        r = self.client.post("/api/auth/signup/", {
            "username": "jo", "email": "j@b.com", "password": "longpass123", "role": "candidate"})
        self.assertEqual(r.status_code, 400)  # full_name missing
        r = self.client.post("/api/auth/login/", {"username": "newco", "password": "longpass123"})
        self.assertEqual(r.json()["role"], "employer")

    # ----- jobs
    def test_public_can_browse_but_not_post(self):
        self.assertEqual(self.client.get("/api/jobs/").json()["count"], 1)
        self.assertEqual(self.client.post("/api/jobs/", {}).status_code, 401)

    def test_candidate_cannot_post_job(self):
        self.assertEqual(self.as_cand.post("/api/jobs/", {}).status_code, 403)

    def test_employer_posts_and_validates_salary(self):
        body = {"title": "QA", "description": "Test", "location": "Dhaka",
                "job_type": "full_time", "salary_min": 100, "salary_max": 50}
        self.assertEqual(self.as_emp.post("/api/jobs/", body).status_code, 400)
        body["salary_max"] = 200
        self.assertEqual(self.as_emp.post("/api/jobs/", body).status_code, 201)

    def test_employer_cannot_edit_others_job(self):
        r = self.as_other.patch(f"/api/jobs/{self.job.id}/", {"title": "Hacked"})
        self.assertEqual(r.status_code, 404)
        r = self.as_emp.patch(f"/api/jobs/{self.job.id}/", {"title": "Senior Django Developer"})
        self.assertEqual(r.status_code, 200)

    def test_search_filters(self):
        Job.objects.create(employer=self.other_employer, title="Node Intern", description="x",
                           location="Remote", job_type="internship", salary_max=10000, skills="node")
        get = lambda qs: self.client.get(f"/api/jobs/?{qs}").json()["count"]
        self.assertEqual(get("q=django"), 1)
        self.assertEqual(get("location=chattogram"), 1)
        self.assertEqual(get("job_type=internship"), 1)
        self.assertEqual(get("skills=python,django"), 1)
        self.assertEqual(get("company=beta"), 1)
        self.assertEqual(get("min_salary=50000"), 1)
        self.assertEqual(get("min_salary=abc"), 2)  # bad value ignored

    def test_inactive_jobs_hidden(self):
        self.job.is_active = False
        self.job.save()
        self.assertEqual(self.client.get("/api/jobs/").json()["count"], 0)
        self.assertEqual(self.client.get(f"/api/jobs/{self.job.id}/").status_code, 404)
        self.assertEqual(self.as_emp.get(f"/api/jobs/{self.job.id}/").status_code, 200)

    # ----- resumes
    def test_resume_upload_validation(self):
        self.assertEqual(self.upload_resume().status_code, 201)
        bad = SimpleUploadedFile("evil.exe", b"MZ")
        r = self.as_cand.post("/api/resumes/", {"title": "x", "file": bad}, format="multipart")
        self.assertEqual(r.status_code, 400)
        big = pdf(size=5 * 1024 * 1024 + 1)
        r = self.as_cand.post("/api/resumes/", {"title": "big", "file": big}, format="multipart")
        self.assertEqual(r.status_code, 400)

    def test_employer_cannot_upload_resume(self):
        r = self.as_emp.post("/api/resumes/", {"title": "CV", "file": pdf()}, format="multipart")
        self.assertEqual(r.status_code, 403)

    # ----- applications
    def test_apply_requires_resume(self):
        r = self.as_cand.post(f"/api/jobs/{self.job.id}/apply/", {"cover_letter": "Hi"})
        self.assertEqual(r.status_code, 400)

    def test_apply_notifies_employer_and_blocks_duplicates(self):
        self.upload_resume()
        r = self.as_cand.post(f"/api/jobs/{self.job.id}/apply/", {"cover_letter": "Hi"})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Notification.objects.filter(user=self.emp_user).count(), 1)
        r = self.as_cand.post(f"/api/jobs/{self.job.id}/apply/", {})
        self.assertEqual(r.status_code, 409)

    def test_employer_updates_status_and_candidate_is_notified(self):
        self.upload_resume()
        app_id = self.as_cand.post(f"/api/jobs/{self.job.id}/apply/", {}).json()["id"]
        r = self.as_emp.patch(f"/api/applications/{app_id}/status/",
                              {"status": "shortlisted", "note": "Interview Monday"})
        self.assertEqual(r.status_code, 200)
        tracked = self.as_cand.get("/api/applications/").json()["results"][0]
        self.assertEqual(tracked["status"], "shortlisted")
        self.assertEqual(tracked["note"], "Interview Monday")
        self.assertTrue(Notification.objects.filter(user=self.cand_user).exists())

    def test_other_employer_cannot_change_status(self):
        self.upload_resume()
        app_id = self.as_cand.post(f"/api/jobs/{self.job.id}/apply/", {}).json()["id"]
        r = self.as_other.patch(f"/api/applications/{app_id}/status/", {"status": "hired"})
        self.assertEqual(r.status_code, 404)

    def test_invalid_status_rejected(self):
        self.upload_resume()
        app_id = self.as_cand.post(f"/api/jobs/{self.job.id}/apply/", {}).json()["id"]
        r = self.as_emp.patch(f"/api/applications/{app_id}/status/", {"status": "banana"})
        self.assertEqual(r.status_code, 400)

    def test_withdraw(self):
        self.upload_resume()
        app_id = self.as_cand.post(f"/api/jobs/{self.job.id}/apply/", {}).json()["id"]
        r = self.as_cand.delete(f"/api/applications/{app_id}/")
        self.assertEqual(r.json()["status"], "withdrawn")
        r = self.as_emp.patch(f"/api/applications/{app_id}/status/", {"status": "hired"})
        self.assertEqual(r.status_code, 400)

    def test_employer_sees_applications_for_own_job_only(self):
        self.upload_resume()
        self.as_cand.post(f"/api/jobs/{self.job.id}/apply/", {})
        r = self.as_emp.get(f"/api/jobs/{self.job.id}/applications/")
        self.assertEqual(r.json()["count"], 1)
        self.assertEqual(self.as_other.get(f"/api/jobs/{self.job.id}/applications/").status_code, 404)

    # ----- notifications & reports
    def test_notifications_mark_read(self):
        Notification.objects.create(user=self.emp_user, message="hello")
        self.assertEqual(self.as_emp.get("/api/notifications/?unread=true").json()["count"], 1)
        self.as_emp.post("/api/notifications/read/")
        self.assertEqual(self.as_emp.get("/api/notifications/?unread=true").json()["count"], 0)

    def test_employer_stats(self):
        self.upload_resume()
        self.as_cand.post(f"/api/jobs/{self.job.id}/apply/", {})
        stats = self.as_emp.get("/api/stats/employer/").json()
        self.assertEqual(stats["total_applications"], 1)
        self.assertEqual(stats["applications_by_status"]["applied"], 1)
        self.assertEqual(self.as_cand.get("/api/stats/employer/").status_code, 403)

    def test_admin_stats_staff_only(self):
        self.assertEqual(self.as_emp.get("/api/stats/admin/").status_code, 403)
        staff = User.objects.create_user("root", password="pass12345", is_staff=True)
        c = APIClient(); c.force_authenticate(staff)
        self.assertEqual(c.get("/api/stats/admin/").json()["jobs"], 1)
