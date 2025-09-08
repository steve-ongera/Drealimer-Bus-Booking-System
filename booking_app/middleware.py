# middleware.py - Custom error handling middleware

import logging
import time
from django.http import HttpResponseServerError
from django.shortcuts import render
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin
from django.core.cache import cache

logger = logging.getLogger(__name__)

class ErrorHandlingMiddleware(MiddlewareMixin):
    """
    Custom middleware for enhanced error handling and monitoring
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_request(self, request):
        """
        Process the request before it reaches the view
        """
        # Add request timestamp for performance monitoring
        request.start_time = time.time()
        
        # Log suspicious activity
        if self.is_suspicious_request(request):
            logger.warning(f"Suspicious request detected: {request.path} from {self.get_client_ip(request)}")
        
        return None
    
    def process_response(self, request, response):
        """
        Process the response after view processing
        """
        # Calculate request processing time
        if hasattr(request, 'start_time'):
            processing_time = time.time() - request.start_time
            
            # Log slow requests
            if processing_time > 5.0:  # 5 seconds threshold
                logger.warning(f"Slow request: {request.path} took {processing_time:.2f} seconds")
        
        # Add custom headers
        if not settings.DEBUG:
            response['X-Frame-Options'] = 'DENY'
            response['X-Content-Type-Options'] = 'nosniff'
            response['X-XSS-Protection'] = '1; mode=block'
        
        return response
    
    def process_exception(self, request, exception):
        """
        Handle uncaught exceptions
        """
        # Log the exception with context
        logger.error(
            f"Unhandled exception in {request.path}",
            extra={
                'request_path': request.path,
                'request_method': request.method,
                'user': str(request.user) if hasattr(request, 'user') else 'Unknown',
                'ip_address': self.get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            },
            exc_info=True
        )
        
        # Check if we're in a high-error state
        error_key = f"error_count_{self.get_client_ip(request)}"
        error_count = cache.get(error_key, 0)
        error_count += 1
        cache.set(error_key, error_count, 300)  # 5 minutes
        
        # If too many errors from same IP, consider blocking
        if error_count > 10:
            logger.critical(f"High error rate from IP: {self.get_client_ip(request)}")
        
        # Return custom error response
        if not settings.DEBUG:
            try:
                return render(request, '500.html', {
                    'request_path': request.path,
                    'user': request.user if hasattr(request, 'user') else None,
                }, status=500)
            except Exception as render_error:
                logger.critical(f"Error template rendering failed: {render_error}")
                return HttpResponseServerError(
                    '<h1>Internal Server Error</h1>'
                    '<p>Please try again later or contact support.</p>'
                )
        
        # In debug mode, let Django handle it
        return None
    
    def get_client_ip(self, request):
        """
        Get the real IP address of the client
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def is_suspicious_request(self, request):
        """
        Check if a request looks suspicious
        """
        suspicious_patterns = [
            '/admin/login/',
            '/wp-admin/',
            '/phpmyadmin/',
            '.php',
            '.env',
            'eval(',
            '<script>',
            'union select',
            'drop table',
        ]
        
        path_lower = request.path.lower()
        query_lower = request.META.get('QUERY_STRING', '').lower()
        
        for pattern in suspicious_patterns:
            if pattern in path_lower or pattern in query_lower:
                return True
        
        return False


class MaintenanceModeMiddleware(MiddlewareMixin):
    """
    Middleware to enable maintenance mode
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_request(self, request):
        """
        Check if maintenance mode is enabled
        """
        # Check if maintenance mode is enabled
        maintenance_enabled = cache.get('maintenance_mode', False)
        
        # Skip maintenance mode for admin and health check
        if (maintenance_enabled and 
            not request.path.startswith('/admin/') and 
            not request.path.startswith('/health/') and
            not (hasattr(request, 'user') and request.user.is_staff)):
            
            return render(request, '503.html', {
                'maintenance': True,
                'estimated_time': cache.get('maintenance_eta', '30 minutes'),
            }, status=503)
        
        return None


class RateLimitMiddleware(MiddlewareMixin):
    """
    Simple rate limiting middleware
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_request(self, request):
        """
        Check rate limits
        """
        if settings.DEBUG:
            return None
        
        client_ip = self.get_client_ip(request)
        cache_key = f"rate_limit_{client_ip}"
        
        # Get current request count
        request_count = cache.get(cache_key, 0)
        
        # Allow up to 100 requests per minute per IP
        if request_count > 100:
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return render(request, '429.html', {
                'error_type': 'rate_limit',
                'title': 'Too Many Requests',
                'message': 'You have exceeded the rate limit. Please try again later.',
            }, status=429)
        
        # Increment request count
        cache.set(cache_key, request_count + 1, 60)  # 1 minute window
        
        return None
    
    def get_client_ip(self, request):
        """
        Get the real IP address of the client
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Add security headers to responses
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_response(self, request, response):
        """
        Add security headers to response
        """
        if not settings.DEBUG:
            # Security headers
            response['X-Frame-Options'] = 'DENY'
            response['X-Content-Type-Options'] = 'nosniff'
            response['X-XSS-Protection'] = '1; mode=block'
            response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
            response['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
            
            # Content Security Policy
            csp = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' cdnjs.cloudflare.com; "
                "style-src 'self' 'unsafe-inline' cdnjs.cloudflare.com; "
                "font-src 'self' cdnjs.cloudflare.com; "
                "img-src 'self' data: https:; "
                "connect-src 'self';"
            )
            response['Content-Security-Policy'] = csp
        
        return response