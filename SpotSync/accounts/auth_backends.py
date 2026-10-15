from django.contrib.auth.backends import ModelBackend

from accounts.models import CustomUser


class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        try:
            user = CustomUser.objects.get(email=username)  # Treat `username` as email
            if user.check_password(password) and self.user_can_authenticate(user):
                return user
        except CustomUser.DoesNotExist:
            # Match Django's timing mitigation for unknown users.
            CustomUser().set_password(password)
            return None
        except CustomUser.MultipleObjectsReturned:
            # Historical imports may contain duplicates; fail closed without
            # changing existing records or adding a uniqueness migration.
            return None
