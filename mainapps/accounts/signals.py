from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import VerificationCode,User
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
import random
import string


@receiver(post_save,sender=User)
def post_save_create_user_code(sender, instance, created,**kwargs):
    if created:
        VerificationCode.objects.create(user=instance)
        
