# utils.py
from django.utils.functional import SimpleLazyObject
from django.conf import settings

def get_current_tenant():
    from django.utils import timezone
    from threading import local

    _thread_locals = local()

    def get_current_tenant_from_request():
        if hasattr(_thread_locals, 'request'):
            return getattr(_thread_locals.request, 'tenant', None)
        return None

    return SimpleLazyObject(get_current_tenant_from_request)
