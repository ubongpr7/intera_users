from django.contrib.auth.backends import BaseBackend
from django.conf import settings


class UserBackend(BaseBackend):
    def autenticate(self,request,username=None,password=None,**kwargs):
        User=settings.AUTH_USER_MODEL
        try:
            user=User.objects.get(username=username)
            if user.check_password(password):
                return user
        except User.DoesNotExist:
            return None

    def get_user(self, user_id)        :
        User=settings.AUTH_USER_MODEL
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
        


