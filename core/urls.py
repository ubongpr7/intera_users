from django.contrib import admin
from django.urls import path,include
from django.urls import re_path
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from django.views.decorators.csrf import csrf_exempt
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from schema_graph.views import Schema

schema_view = get_schema_view(
   openapi.Info(
      title="Intera API Users",
      default_version='v1',
      description="Test description",
      terms_of_service="https://www.google.com/policies/terms/",
      contact=openapi.Contact(email="contact@snippets.local"),
      license=openapi.License(name="BSD License"),
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('djoser/', include('djoser.urls'), name='djoser_users'),
    path('auth/', include("mainapps.accounts.jwt_urls")),
    path('accounts/', include("mainapps.accounts.urls")),
    #  api endpoints docs
    path('swagger<format>/', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    path("schema/", Schema.as_view()),

    # db sync
    # path('api/v1/accounts/', include("mainapps.accounts.api.urls")),
    path('permission_api/', include("mainapps.permit.api.urls",)),
    path('management/', include("mainapps.profile.urls")),
    
]

