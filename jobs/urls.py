from django.urls import path

from . import views

urlpatterns = [
    path("auth/signup/", views.SignupView.as_view()),
    path("auth/login/", views.LoginView.as_view()),

    path("jobs/", views.JobListCreateView.as_view()),
    path("jobs/<int:pk>/", views.JobDetailView.as_view()),
    path("jobs/<int:pk>/apply/", views.ApplyView.as_view()),
    path("jobs/<int:pk>/applications/", views.JobApplicationsView.as_view()),
    path("my/jobs/", views.MyJobsView.as_view()),

    path("resumes/", views.ResumeListCreateView.as_view()),
    path("resumes/<int:pk>/", views.ResumeDetailView.as_view()),

    path("applications/", views.MyApplicationsView.as_view()),
    path("applications/<int:pk>/", views.MyApplicationDetailView.as_view()),
    path("applications/<int:pk>/status/", views.ApplicationStatusView.as_view()),

    path("notifications/", views.NotificationListView.as_view()),
    path("notifications/read/", views.NotificationReadView.as_view()),
    path("notifications/<int:pk>/read/", views.NotificationReadView.as_view()),

    path("stats/employer/", views.EmployerStatsView.as_view()),
    path("stats/admin/", views.AdminStatsView.as_view()),
]
