from django.urls import path
from .views import   *
app_name='management'


urlpatterns = [
    path('company-profile/', CompanyProfileCreateView.as_view(), name='company_profile'),
    path('login/', login_staff, name='login'),
    path('<str:company_id>/add-staff/', StaffUserCreateView.as_view(), name='add_staff_user'),
]