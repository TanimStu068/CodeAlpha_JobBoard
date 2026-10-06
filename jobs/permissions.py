from rest_framework.permissions import BasePermission


class IsEmployer(BasePermission):
    message = "Only employer accounts can do this."

    def has_permission(self, request, view):
        return bool(request.user.is_authenticated
                    and getattr(request.user, "employer_profile", None))


class IsCandidate(BasePermission):
    message = "Only candidate accounts can do this."

    def has_permission(self, request, view):
        return bool(request.user.is_authenticated
                    and getattr(request.user, "candidate_profile", None))
