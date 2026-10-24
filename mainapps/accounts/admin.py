from django.contrib import admin
from .models import *

admin.site.register(User)
admin.site.register(VerificationCode)
admin.site.register(LegalConsent)
admin.site.register(ReferralPayout)
