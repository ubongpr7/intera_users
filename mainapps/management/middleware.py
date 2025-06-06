# middleware.py
from django.utils.deprecation import MiddlewareMixin
from .models import CompanyProfile 

class TenantMiddleware(MiddlewareMixin):
    def process_request(self, request):
        hostname = request.get_host().split(':')[0]
        try:
            request.tenant = CompanyProfile.objects.get(domain_url=hostname)
        except CompanyProfile.DoesNotExist:
            request.tenant = None  
