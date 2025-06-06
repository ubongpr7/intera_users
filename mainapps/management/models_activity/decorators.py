# core/decorators.py
from functools import wraps
from django.http import HttpRequest
from .activity_logger import log_user_activity

def track_activity(action: str, model_name: str = None):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request: HttpRequest, *args, **kwargs):
            response = view_func(request, *args, **kwargs)
            
            try:
                if response.status_code < 400:  # Log only successful actions
                    model = model_name or request.resolver_match.url_name
                    log_user_activity(
                        user=request.user,
                        action=action,
                        model_name=model,
                        object_id=kwargs.get('pk'),
                        details={
                            'method': request.method,
                            'path': request.path,
                            'params': dict(request.GET),
                            'data': request.POST.dict() if request.method == 'POST' else {}
                        }
                    )
            except Exception as e:
                pass  # Don't break main functionality
            
            return response
        return _wrapped_view
    return decorator