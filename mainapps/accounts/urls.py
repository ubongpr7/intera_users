from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'users', views.UserViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path("verify/",views.VerificationAPI.as_view(),name="verify"),
    path("mfa/setup/", views.MfaSetupView.as_view(), name="mfa-setup"),
    path("mfa/verify/", views.MfaVerifyView.as_view(), name="mfa-verify"),
    path("mfa/toggle/", views.MfaToggleView.as_view(), name="mfa-toggle"),
]
