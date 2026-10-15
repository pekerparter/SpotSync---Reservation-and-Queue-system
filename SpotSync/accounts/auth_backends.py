from django.contrib.auth.backends import ModelBackend

from accounts.models import CustomUser


class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            user = CustomUser.objects.get(email=username)  # Treat `username` as email
            if user.check_password(password):
                return user
        except CustomUser.DoesNotExist:
            return None
