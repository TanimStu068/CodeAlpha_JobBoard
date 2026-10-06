from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from django.contrib.auth import get_user_model

from .models import Application, Job, Notification, Resume
from .permissions import IsCandidate, IsEmployer
from .serializers import (ApplicationSerializer, ApplyInputSerializer, JobSerializer,
                          NotificationSerializer, ResumeSerializer, SignupSerializer,
                          StatusUpdateSerializer)

User = get_user_model()


def role_of(user):
    if getattr(user, "employer_profile", None):
        return "employer"
    if getattr(user, "candidate_profile", None):
        return "candidate"
    return "admin" if user.is_staff else "none"


def notify(user, message):
    Notification.objects.create(user=user, message=message[:300])


# ------------------------------------------------------------------- auth
class SignupView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        s = SignupSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = s.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"username": user.username, "role": role_of(user), "token": token.key},
                        status=status.HTTP_201_CREATED)


class LoginView(ObtainAuthToken):
    def post(self, request, *args, **kwargs):
        s = self.serializer_class(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        user = s.validated_data["user"]
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "role": role_of(user)})


# ------------------------------------------------------------------- jobs
def filter_jobs(qs, p):
    q = p.get("q")
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q)
                       | Q(skills__icontains=q) | Q(employer__company_name__icontains=q))
    if p.get("location"):
        qs = qs.filter(location__icontains=p["location"])
    if p.get("job_type"):
        qs = qs.filter(job_type=p["job_type"])
    if p.get("company"):
        qs = qs.filter(employer__company_name__icontains=p["company"])
    for skill in filter(None, (s.strip() for s in p.get("skills", "").split(","))):
        qs = qs.filter(skills__icontains=skill)
    try:
        if p.get("min_salary"):
            v = int(p["min_salary"])
            qs = qs.filter(Q(salary_max__gte=v) | Q(salary_min__gte=v))
        if p.get("max_salary"):
            qs = qs.filter(salary_min__lte=int(p["max_salary"]))
    except ValueError:
        pass
    ordering = p.get("ordering")
    if ordering in ("created_at", "-created_at", "salary_max", "-salary_max"):
        qs = qs.order_by(ordering)
    return qs.distinct()


class JobListCreateView(generics.ListCreateAPIView):
    serializer_class = JobSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), IsEmployer()]
        return [AllowAny()]

    def get_queryset(self):
        qs = Job.objects.filter(is_active=True).select_related("employer")
        return filter_jobs(qs, self.request.query_params)

    def perform_create(self, serializer):
        serializer.save(employer=self.request.user.employer_profile)


class JobDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = JobSerializer

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [AllowAny()]
        return [IsAuthenticated(), IsEmployer()]

    def get_queryset(self):
        qs = Job.objects.select_related("employer")
        user = self.request.user
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            emp = getattr(user, "employer_profile", None) if user.is_authenticated else None
            return qs.filter(Q(is_active=True) | Q(employer=emp)) if emp else qs.filter(is_active=True)
        return qs.filter(employer=user.employer_profile)  # only own jobs are editable


class MyJobsView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsEmployer]
    serializer_class = JobSerializer

    def get_queryset(self):
        return Job.objects.filter(employer=self.request.user.employer_profile)


class JobApplicationsView(generics.ListAPIView):
    """Employer: applications received for one of their jobs."""
    permission_classes = [IsAuthenticated, IsEmployer]
    serializer_class = ApplicationSerializer

    def get_queryset(self):
        job = get_object_or_404(Job, pk=self.kwargs["pk"], employer=self.request.user.employer_profile)
        qs = job.applications.select_related("job__employer", "candidate__user", "resume")
        st = self.request.query_params.get("status")
        return qs.filter(status=st) if st else qs


# ---------------------------------------------------------------- resumes
class ResumeListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsCandidate]
    serializer_class = ResumeSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        return Resume.objects.filter(candidate=self.request.user.candidate_profile)

    def perform_create(self, serializer):
        serializer.save(candidate=self.request.user.candidate_profile)


class ResumeDetailView(generics.RetrieveDestroyAPIView):
    permission_classes = [IsAuthenticated, IsCandidate]
    serializer_class = ResumeSerializer

    def get_queryset(self):
        return Resume.objects.filter(candidate=self.request.user.candidate_profile)


# ------------------------------------------------------------ applications
class ApplyView(APIView):
    permission_classes = [IsAuthenticated, IsCandidate]

    def post(self, request, pk):
        s = ApplyInputSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        candidate = request.user.candidate_profile
        job = get_object_or_404(Job, pk=pk, is_active=True)

        if Application.objects.filter(job=job, candidate=candidate).exists():
            return Response({"error": "You have already applied to this job."},
                            status=status.HTTP_409_CONFLICT)

        resume_id = s.validated_data.get("resume")
        if resume_id:
            resume = candidate.resumes.filter(pk=resume_id).first()
            if not resume:
                return Response({"error": "Resume not found."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            resume = candidate.resumes.first()  # latest upload
            if not resume:
                return Response({"error": "Upload a resume before applying."},
                                status=status.HTTP_400_BAD_REQUEST)

        app = Application.objects.create(
            job=job, candidate=candidate, resume=resume,
            cover_letter=s.validated_data.get("cover_letter", ""))
        notify(job.employer.user,
               f"{candidate.full_name} applied for {job.title}.")
        return Response(ApplicationSerializer(app, context={"request": request}).data,
                        status=status.HTTP_201_CREATED)


class MyApplicationsView(generics.ListAPIView):
    """Candidate: track my applications."""
    permission_classes = [IsAuthenticated, IsCandidate]
    serializer_class = ApplicationSerializer

    def get_queryset(self):
        qs = Application.objects.filter(candidate=self.request.user.candidate_profile) \
            .select_related("job__employer", "candidate__user", "resume")
        st = self.request.query_params.get("status")
        return qs.filter(status=st) if st else qs


class MyApplicationDetailView(generics.RetrieveDestroyAPIView):
    """GET to view, DELETE to withdraw."""
    permission_classes = [IsAuthenticated, IsCandidate]
    serializer_class = ApplicationSerializer

    def get_queryset(self):
        return Application.objects.filter(candidate=self.request.user.candidate_profile) \
            .select_related("job__employer", "candidate__user", "resume")

    def destroy(self, request, *args, **kwargs):
        app = self.get_object()
        if app.status in (Application.HIRED, Application.REJECTED, Application.WITHDRAWN):
            return Response({"error": f"Cannot withdraw an application that is {app.status}."},
                            status=status.HTTP_400_BAD_REQUEST)
        app.status = Application.WITHDRAWN
        app.save()
        notify(app.job.employer.user,
               f"{app.candidate.full_name} withdrew their application for {app.job.title}.")
        return Response(self.get_serializer(app).data)


class ApplicationStatusView(APIView):
    """Employer: move an application through the hiring pipeline."""
    permission_classes = [IsAuthenticated, IsEmployer]

    def patch(self, request, pk):
        app = get_object_or_404(Application.objects.select_related("job__employer", "candidate__user"),
                                pk=pk, job__employer=request.user.employer_profile)
        if app.status == Application.WITHDRAWN:
            return Response({"error": "The candidate withdrew this application."},
                            status=status.HTTP_400_BAD_REQUEST)
        s = StatusUpdateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        app.status = s.validated_data["status"]
        app.note = s.validated_data.get("note", app.note)
        app.save()
        notify(app.candidate.user,
               f"Your application for {app.job.title} at {app.job.employer.company_name} "
               f"is now {app.get_status_display().lower()}.")
        return Response(ApplicationSerializer(app, context={"request": request}).data)


# ---------------------------------------------------------- notifications
class NotificationListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        qs = Notification.objects.filter(user=self.request.user)
        if self.request.query_params.get("unread") == "true":
            qs = qs.filter(is_read=False)
        return qs


class NotificationReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk=None):
        qs = Notification.objects.filter(user=request.user)
        if pk is not None:
            get_object_or_404(qs, pk=pk)
            qs = qs.filter(pk=pk)
        updated = qs.update(is_read=True)
        return Response({"marked_read": updated})


# ---------------------------------------------------------------- reports
class EmployerStatsView(APIView):
    permission_classes = [IsAuthenticated, IsEmployer]

    def get(self, request):
        emp = request.user.employer_profile
        apps = Application.objects.filter(job__employer=emp)
        by_status = {s: 0 for s, _ in Application.STATUS_CHOICES}
        for row in apps.values("status").annotate(n=Count("id")):
            by_status[row["status"]] = row["n"]
        jobs = emp.jobs.annotate(n=Count("applications")).values("id", "title", "is_active", "n")
        return Response({
            "total_jobs": emp.jobs.count(),
            "active_jobs": emp.jobs.filter(is_active=True).count(),
            "total_applications": apps.count(),
            "applications_by_status": by_status,
            "applications_per_job": [
                {"job_id": j["id"], "title": j["title"], "is_active": j["is_active"],
                 "applications": j["n"]} for j in jobs],
        })


class AdminStatsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        by_status = {s: 0 for s, _ in Application.STATUS_CHOICES}
        for row in Application.objects.values("status").annotate(n=Count("id")):
            by_status[row["status"]] = row["n"]
        return Response({
            "users": User.objects.count(),
            "employers": User.objects.filter(employer_profile__isnull=False).count(),
            "candidates": User.objects.filter(candidate_profile__isnull=False).count(),
            "jobs": Job.objects.count(),
            "active_jobs": Job.objects.filter(is_active=True).count(),
            "applications": Application.objects.count(),
            "applications_by_status": by_status,
        })
