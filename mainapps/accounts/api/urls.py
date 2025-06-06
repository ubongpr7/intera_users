from django.urls import path,include
from rest_framework import routers
from .views import *
router=routers.DefaultRouter()


urlpatterns=[
    path("logout/",LogoutAPI.as_view(),name="logout"),
    path("verify/",VerificationAPI.as_view(),name="verify"),
    path("token/",TokenGenerator.as_view(),name="token"),
    path("api_route/",ge_route,name="api_route"),

    path('staff/list/', StaffUsersView.as_view(), name='staff-list'),
    path('user/', UserDetailView.as_view(), name='user-detail'),
    path('create-staff/', StaffUserRegistrationAPIView.as_view(), name='create_staff'),

    path('register/', RootUserRegistrationAPIView.as_view(), name='user-register'),
    ]

