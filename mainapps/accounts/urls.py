from django.urls import path,include
from .views import *
app_name='accounts'
urlpatterns=[
    
    path('',register_owner,name = 'signup'),
    path('signout/',signout, name='logout'),
    path('signin/',login_owner, name='signin'),
    path('register/',RegisterPage.as_view(), name='register'),
    # path('signin/',signin, name='signin'),
    path('welcome/',LandingPage.as_view(), name='land'),
    path('verification/',twofa, name='verification'),
    path('send_code',send_code,name='send_code'),
]

