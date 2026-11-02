from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'users', views.UserViewSet)
router.register(r'affiliate-partners', views.AffiliatePartnerViewSet, basename='affiliate-partner')
router.register(r'referral-payouts', views.ReferralPayoutViewSet, basename='referral-payout')

urlpatterns = [
    path('', include(router.urls)),
    path("verify/",views.VerificationAPI.as_view(),name="verify"),
    path("mfa/email/request/", views.MfaEmailRequestView.as_view(), name="mfa-email-request"),
    path("mfa/email/verify/", views.MfaEmailVerifyView.as_view(), name="mfa-email-verify"),
    path("mfa/setup/", views.MfaSetupView.as_view(), name="mfa-setup"),
    path("mfa/verify/", views.MfaVerifyView.as_view(), name="mfa-verify"),
    path("mfa/reset/request/", views.MfaResetRequestView.as_view(), name="mfa-reset-request"),
    path("mfa/reset/confirm/", views.MfaResetConfirmView.as_view(), name="mfa-reset-confirm"),
    path("websocket-ticket/", views.WebSocketTicketView.as_view(), name="websocket-ticket"),
    path("signing-keys/", views.PublicSigningKeysView.as_view(), name="public-signing-keys"),
    path("mfa/toggle/", views.MfaToggleView.as_view(), name="mfa-toggle"),
    path("platform-staff-invitations/", views.PlatformStaffInvitationView.as_view(), name="platform-staff-invitations"),
    path("platform-staff-invitations/<uuid:invitation_id>/revoke/", views.PlatformStaffInvitationRevokeView.as_view(), name="platform-staff-invitation-revoke"),
    path("platform-staff-invitations/lookup/", views.PlatformStaffInvitationLookupView.as_view(), name="platform-staff-invitation-lookup"),
    path("platform-staff-invitations/accept/", views.PlatformStaffInvitationAcceptView.as_view(), name="platform-staff-invitation-accept"),
    path("affiliate-partner-invitations/lookup/", views.AffiliatePartnerInvitationLookupView.as_view(), name="affiliate-partner-invitation-lookup"),
    path("affiliate-partner-invitations/accept/", views.AffiliatePartnerInvitationAcceptView.as_view(), name="affiliate-partner-invitation-accept"),
]
