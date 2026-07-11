from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'users', views.UserViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path("verify/",views.VerificationAPI.as_view(),name="verify"),
    path("mfa/email/request/", views.MfaEmailRequestView.as_view(), name="mfa-email-request"),
    path("mfa/email/verify/", views.MfaEmailVerifyView.as_view(), name="mfa-email-verify"),
    path("mfa/setup/", views.MfaSetupView.as_view(), name="mfa-setup"),
    path("mfa/verify/", views.MfaVerifyView.as_view(), name="mfa-verify"),
    path("mfa/reset/request/", views.MfaResetRequestView.as_view(), name="mfa-reset-request"),
    path("mfa/reset/confirm/", views.MfaResetConfirmView.as_view(), name="mfa-reset-confirm"),
    path("mfa/toggle/", views.MfaToggleView.as_view(), name="mfa-toggle"),
]
