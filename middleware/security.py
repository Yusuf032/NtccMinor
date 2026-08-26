from fastapi import Request, HTTPException, status
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import time
import re
from collections import defaultdict
from curabot.logger.log import logger
import html

"""
Security Middleware Module

This module implements a comprehensive security middleware for the FastAPI application.
It handles input validation, rate limiting, and the application of security headers to
protect against common web vulnerabilities (XSS, SQL Injection, etc.).
"""

class SecurityMiddleware(BaseHTTPMiddleware):
    """
    Middleware for enhancing application security.
    
    Features:
    - **Rate Limiting**: Limits requests per IP address within a time window.
    - **Input Validation**: Scans headers and query parameters for malicious patterns.
    - **Security Headers**: Adds strict HTTP security headers (CSP, HSTS, X-Frame-Options).
    - **Endpoint Protection**: Applies different security policies for documentation vs. API endpoints.
    
    Attributes:
        rate_limit_requests (int): Max requests allowed per window.
        rate_limit_window (int): Time window in seconds.
        request_counts (defaultdict): Stores request timestamps per IP.
    """
    
    def __init__(self, app, rate_limit_requests: int = 100, rate_limit_window: int = 3600):
        """
        Initialize the security middleware.

        Args:
            app: The ASGI application.
            rate_limit_requests (int): Maximum requests allowed per IP in the window. Defaults to 100.
            rate_limit_window (int): Rate limit window size in seconds. Defaults to 3600 (1 hour).
        """
        super().__init__(app)
        self.rate_limit_requests = rate_limit_requests
        self.rate_limit_window = rate_limit_window
        self.request_counts = defaultdict(list)
        
    async def dispatch(self, request: Request, call_next):
        """
        Process incoming requests and apply security checks.

        Args:
            request (Request): The incoming HTTP request.
            call_next (callable): The next middleware or route handler.

        Returns:
            Response: The HTTP response.
        """
        # Get client IP
        client_ip = self._get_client_ip(request)
        
        # Check if it's a documentation endpoint
        is_docs = self._is_docs_endpoint(request.url.path)
        
        if is_docs:
            response = await call_next(request)
            self._add_security_headers(response, is_docs=True)
            return response
        
        # Skip security checks for health/ready endpoints (publicly accessible)
        if self._is_public_endpoint(request.url.path):
            return await call_next(request)
        
        # Rate limiting
        if self._is_rate_limited(client_ip):
            logger("CuraDocs_Doctor_CuraBot", "Security", "WARN", "HIGH", f"Rate limit exceeded for IP: {client_ip}")
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"}
            )
        
        # Input validation for suspicious patterns
        if await self._has_malicious_input(request):
            logger("CuraDocs_Doctor_CuraBot", "Security", "WARN", "HIGH", f"Malicious input detected from IP: {client_ip}")
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid input detected"}
            )
        
        # Process request
        response = await call_next(request)
        
        # Add security headers
        self._add_security_headers(response, is_docs=False)
        
        return response
    
    def _is_docs_endpoint(self, path: str) -> bool:
        """
        Check if the request path matches documentation endpoints.
        
        Args:
            path (str): The request path.
            
        Returns:
            bool: True if it's a documentation endpoint.
        """
        return path.startswith((
            "/docs", "/redoc", "/openapi.json", "/scalar", "/favicon.ico"
        ))
    
    def _is_public_endpoint(self, path: str) -> bool:
        """
        Check if the request path matches public service checkpoints.
        
        Args:
            path (str): The request path.
            
        Returns:
            bool: True if it's a health or ready endpoint.
        """
        public_endpoints = [
            "/health", "/ready",
            "/curabot/health", "/curabot/ready",
            "/doctor/health", "/doctor/ready",
            "/patient/health", "/patient/ready",
        ]
        return path in public_endpoints
    
    def _get_client_ip(self, request: Request) -> str:
        """
        Determine the client IP address, handling proxy headers.
        
        Args:
            request (Request): The incoming request.
            
        Returns:
            str: The client IP address.
        """
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.client.host if request.client else "unknown"
    
    def _is_rate_limited(self, client_ip: str) -> bool:
        """
        Check if the client IP has exceeded the rate limit.
        
        Args:
            client_ip (str): The client IP address.
            
        Returns:
            bool: True if rate limited, False otherwise.
        """
        now = time.time()
        
        # Clean old requests from history
        self.request_counts[client_ip] = [
            req_time for req_time in self.request_counts[client_ip]
            if now - req_time < self.rate_limit_window
        ]
        
        # Check against limit
        if len(self.request_counts[client_ip]) >= self.rate_limit_requests:
            return True
        
        # Record current request
        self.request_counts[client_ip].append(now)
        return False
    
    async def _has_malicious_input(self, request: Request) -> bool:
        """
        Scan request headers and query parameters for malicious content.
        
        Args:
            request (Request): The incoming request.
            
        Returns:
            bool: True if malicious patterns are found.
        """
        try:
            # Check headers
            for header_name, header_value in request.headers.items():
                # Skip standard headers that might legitimately contain special chars
                if header_name.lower() in ("user-agent", "accept", "accept-encoding", "host", "connection", "authorization"):
                    continue
                if self._contains_malicious_patterns(header_value):
                    return True
            
            # Check query parameters
            for param_value in request.query_params.values():
                if self._contains_malicious_patterns(param_value):
                    return True
            
            return False
        except Exception:
            return False
    
    def _contains_malicious_patterns(self, input_str: str) -> bool:
        """
        Verify input string against known attack patterns (XSS, SQLi, etc.).
        
        Args:
            input_str (str): String to check.
            
        Returns:
            bool: True if a pattern matches.
        """
        malicious_patterns = [
            r'<script[^>]*>.*?</script>',  # XSS
            r'javascript:',  # XSS
            r'on\w+\s*=',  # Event handlers
            r'union\s+select',  # SQL injection
            r'drop\s+table',  # SQL injection
            r'\.\./.*\.\.',  # Path traversal
            r'exec\s*\(',  # Code injection
            r'eval\s*\(',  # Code injection
            r'system\s*\(',  # Command injection
        ]
        
        input_lower = input_str.lower()
        for pattern in malicious_patterns:
            if re.search(pattern, input_lower, re.IGNORECASE):
                return True
        return False
    
    def _add_security_headers(self, response: Response, is_docs: bool = False):
        """
        Add security headers to the HTTP response.
        
        Args:
            response (Response): The response object.
            is_docs (bool): Whether the response is for documentation (allows relaxed CSP).
        """
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

        if is_docs:
            # Relaxed CSP for documentation (allows CDNs and inline scripts needed for Swagger UI)
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "img-src 'self' data: blob: https://fastapi.tiangolo.com; "
                "connect-src 'self'; "
                "frame-ancestors 'none'"
            )
            return

        # Strict CSP for API endpoints
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"


def sanitize_input(input_str: str) -> str:
    """
    Sanitize user input string to prevent XSS and injection attacks.
    
    Escapes HTML characters and removes dangerous special characters.
    
    Args:
        input_str (str): The raw input string.
        
    Returns:
        str: The sanitized string.
    """
    if not isinstance(input_str, str):
        return input_str
    
    # HTML escape
    sanitized = html.escape(input_str)
    
    # Remove potentially dangerous characters
    sanitized = re.sub(r'[<>"\';\\&]', '', sanitized)
    
    return sanitized.strip()


def validate_email(email: str) -> bool:
    """
    Validate email address format.
    
    Args:
        email (str): Email address to validate.
        
    Returns:
        bool: True if valid, False otherwise.
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email)) and len(email) <= 254


def validate_password_strength(password: str) -> bool:
    """
    Check if a password meets minimum strength requirements.
    
    Requires:
    - Minimum length of 8 characters.
    - At least one uppercase letter.
    - At least one lowercase letter.
    - At least one digit.
    - At least one special character.
    
    Args:
        password (str): Password to check.
    
    Returns:
        bool: True if strong, False otherwise.
    """
    if len(password) < 8:
        return False
    
    # Check for at least one uppercase, lowercase, digit, and special character
    patterns = [
        r'[A-Z]',  # Uppercase
        r'[a-z]',  # Lowercase
        r'\d',     # Digit
        r'[!@#$%^&*(),.?":{}|<>]'  # Special character
    ]
    
    return all(re.search(pattern, password) for pattern in patterns)
