from django.contrib.auth.backends import ModelBackend
from django.conf import settings
from mainapps.accounts.models import User
StaffUser=User
class StaffUserBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, company_id=None, **kwargs):
        try:
            user = StaffUser.objects.get(username=username, profile__unique_id=company_id)
            if user.check_password(password):
                return user
        except StaffUser.DoesNotExist:
            print(StaffUser.DoesNotExist)
            return None

    def get_user(self, user_id):
        try:
            return StaffUser.objects.get(pk=user_id)
        except StaffUser.DoesNotExist:
            return None
    def has_perm(self,user,perm,obj=None):
        # if not user.is_main:
            return user.user_permissions.filter(codename=perm).exists()
        # return False
