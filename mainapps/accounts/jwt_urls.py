from django.urls import path, re_path
from .views import (
    CompanyMembershipListView,
    CompanyContextSwitchView,
    CustomProviderAuthView,
    NativeOAuthTicketExchangeView,
    NativeProviderAuthTicketView,
    CustomTokenObtainPairView,
    CustomTokenRefreshView,
    CustomTokenVerifyView,
    LogoutView,
)

urlpatterns = [
    path('login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
    path('verify/', CustomTokenVerifyView.as_view(), name='token_verify'),
    path('logout/', LogoutView.as_view(), name='logout'), 
    path('companies/', CompanyMembershipListView.as_view(), name='company_membership_list'),
    path('switch-company/', CompanyContextSwitchView.as_view(), name='switch_company_context'),
    re_path(
        r'^o/(?P<provider>\S+)/native/$',
        NativeProviderAuthTicketView.as_view(),
        name='native-provider-auth-ticket',
    ),
    path('o/native/exchange/', NativeOAuthTicketExchangeView.as_view(), name='native-oauth-ticket-exchange'),
     re_path(
        r'^o/(?P<provider>\S+)/$',
        CustomProviderAuthView.as_view(),
        name='provider-auth'
    ),
]
