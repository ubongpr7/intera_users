from django.urls import path,include
from .views import *

urlpatterns=[
    path('',permit_home, name='permisions')
]