from pybloom_live import BloomFilter
from curabot.logger.log import logger
import json
import os
from pathlib import Path
import re

"""Bloom filter configuration for Auth system security enhancements"""

class BloomFilterService:
    """Service for managing Bloom filters for security and performance"""
    
    def __init__(self):
        try:
            self.bloom_dir = Path(__file__).parent.parent / "data" / "bloom"
            self.bloom_dir.mkdir(parents=True, exist_ok=True)
            
            # Initialize bloom filters
            self.blacklisted_tokens = self._load_or_create_filter("blacklisted_tokens", 100000, 0.001)
            self.compromised_passwords = self._load_or_create_filter("compromised_passwords", 1000000, 0.001)
            self.suspicious_ips = self._load_or_create_filter("suspicious_ips", 50000, 0.001)
            self.registered_emails = self._load_or_create_filter("registered_emails", 500000, 0.001)
            
            logger("CuraDocs_Doctor_CuraBot", "Bloom Filter", "INFO", "null", "BloomFilterService initialized successfully")
        except Exception as e:
            logger("CuraDocs_Doctor_CuraBot", "Bloom Filter", "ERROR", "ERROR", f"BloomFilterService initialization failed: {str(e)}")
            raise
    
    def _sanitize_filename(self, name: str) -> str:
        """Sanitize filename to prevent path traversal"""
        # Only allow alphanumeric characters and underscores
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '', name)
        if not sanitized or sanitized != name:
            raise ValueError(f"Invalid filter name: {name}")
        return sanitized
    
    def _load_or_create_filter(self, name: str, capacity: int, error_rate: float) -> BloomFilter:
        """Load existing bloom filter or create new one"""
        try:
            sanitized_name = self._sanitize_filename(name)
            # Use secure path construction to prevent traversal
            filter_path = self.bloom_dir / sanitized_name
            filter_path = filter_path.with_suffix('.json')
            
            # Ensure path is within allowed directory
            if not str(filter_path.resolve()).startswith(str(self.bloom_dir.resolve())):
                raise ValueError(f"Path traversal attempt detected: {sanitized_name}")
            
            if filter_path.exists():
                # Additional security check before file access
                abs_filter_path = filter_path.resolve()
                abs_bloom_dir = self.bloom_dir.resolve()
                if not str(abs_filter_path).startswith(str(abs_bloom_dir)):
                    raise ValueError("Path traversal blocked")
                
                with abs_filter_path.open('r') as f:
                    data = json.load(f)
                bloom_filter = BloomFilter(capacity=data['capacity'], error_rate=data['error_rate'])
                # Reconstruct bloom filter from bit array
                for item in data.get('items', []):
                    bloom_filter.add(item)
                logger("CuraDocs_Doctor_CuraBot", "Bloom Filter", "INFO", "null", f"Loaded existing bloom filter: {sanitized_name}")
                return bloom_filter
            else:
                bloom_filter = BloomFilter(capacity=capacity, error_rate=error_rate)
                self._save_filter(sanitized_name, bloom_filter)
                logger("CuraDocs_Doctor_CuraBot", "Bloom Filter", "INFO", "null", f"Created new bloom filter: {sanitized_name}")
                return bloom_filter
        except Exception as e:
            logger("CuraDocs_Doctor_CuraBot", "Bloom Filter", "ERROR", "ERROR", f"Failed to load/create bloom filter {name}: {str(e)}")
            raise
    
    def _save_filter(self, name: str, bloom_filter: BloomFilter):
        """Save bloom filter to disk using secure JSON format"""
        try:
            sanitized_name = self._sanitize_filename(name)
            # Use secure path construction to prevent traversal
            filter_path = self.bloom_dir / sanitized_name
            filter_path = filter_path.with_suffix('.json')
            
            # Ensure path is within allowed directory
            if not str(filter_path.resolve()).startswith(str(self.bloom_dir.resolve())):
                raise ValueError(f"Path traversal attempt detected: {sanitized_name}")
            
            # Save metadata only (items are tracked separately for security)
            data = {
                'capacity': bloom_filter.capacity,
                'error_rate': bloom_filter.error_rate,
                'count': bloom_filter.count,
                'items': []  # Don't store actual items for security
            }
            
            # Additional security check before file access
            abs_filter_path = filter_path.resolve()
            abs_bloom_dir = self.bloom_dir.resolve()
            if not str(abs_filter_path).startswith(str(abs_bloom_dir)):
                raise ValueError("Path traversal blocked")
            
            with abs_filter_path.open('w') as f:
                json.dump(data, f, indent=2)
            logger("CuraDocs_Doctor_CuraBot", "Bloom Filter", "INFO", "null", f"Saved bloom filter: {sanitized_name}")
        except Exception as e:
            logger("CuraDocs_Doctor_CuraBot", "Bloom Filter", "ERROR", "ERROR", f"Failed to save bloom filter {name}: {str(e)}")
            raise


    """JWT Token Blacklisting Methods"""
    def is_token_blacklisted(self, jti: str) -> bool:
        """Fast check if JWT token might be blacklisted"""
        try:
            result = jti in self.blacklisted_tokens
            if result:
                logger("CuraDocs_Doctor_CuraBot", "Bloom Filter", "WARN", "MEDIUM", f"Token possibly blacklisted: {jti[:10]}...")
            return result
        except Exception as e:
            logger("CuraDocs_Doctor_CuraBot", "Bloom Filter", "ERROR", "ERROR", f"Token blacklist check failed: {str(e)}")
            return False
    
    def add_blacklisted_token(self, jti: str):
        """Add JWT token to blacklist"""
        try:
            self.blacklisted_tokens.add(jti)
            self._save_filter("blacklisted_tokens", self.blacklisted_tokens)
            logger("CuraDocs_Profile", "Bloom Filter", "INFO", "null", f"Token added to blacklist: {jti[:10]}...")
        except Exception as e:
            logger("CuraDocs_Profile", "Bloom Filter", "ERROR", "ERROR", f"Failed to blacklist token: {str(e)}")
            raise


    """Password Security Methods"""
    def is_password_compromised(self, password: str) -> bool:
        """Check if password is in breach database"""
        try:
            result = password in self.compromised_passwords
            if result:
                logger("CuraDocs_Doctor_CuraBot", "Bloom Filter", "WARN", "HIGH", "Compromised password detected")
            return result
        except Exception as e:
            logger("CuraDocs_Doctor_CuraBot", "Bloom Filter", "ERROR", "ERROR", f"Password compromise check failed: {str(e)}")
            return False
    
    def add_compromised_password(self, password: str):
        """Add password to compromised list"""
        try:
            self.compromised_passwords.add(password)
            self._save_filter("compromised_passwords", self.compromised_passwords)
            logger("CuraDocs_Doctor_CuraBot", "Bloom Filter", "INFO", "null", "Compromised password added to filter")
        except Exception as e:
            logger("CuraDocs_Doctor_CuraBot", "Bloom Filter", "ERROR", "ERROR", f"Failed to add compromised password: {str(e)}")
            raise


    """IP Security Methods"""
    def is_ip_suspicious(self, ip: str) -> bool:
        """Check if IP is marked as suspicious"""
        try:
            result = ip in self.suspicious_ips
            if result:
                logger("CuraDocs_Doctor_CuraBot", "Bloom Filter", "WARN", "HIGH", f"Suspicious IP detected: {ip}")
            return result
        except Exception as e:
            logger("CuraDocs_Doctor_CuraBot", "Bloom Filter", "ERROR", "ERROR", f"IP suspicion check failed: {str(e)}")
            return False
    
    def add_suspicious_ip(self, ip: str):
        """Mark IP as suspicious"""
        try:
            self.suspicious_ips.add(ip)
            self._save_filter("suspicious_ips", self.suspicious_ips)
            logger("CuraDocs_Doctor_CuraBot", "Bloom Filter", "INFO", "null", f"IP marked as suspicious: {ip}")
        except Exception as e:
            logger("CuraDocs_Doctor_CuraBot", "Bloom Filter", "ERROR", "ERROR", f"Failed to mark IP as suspicious: {str(e)}")
            raise


    """Email Existence Methods"""
    def is_email_registered(self, email: str) -> bool:
        """Fast check if email might be already registered"""
        try:
            result = email.lower() in self.registered_emails
            if result:
                logger("CuraDocs_Doctor_CuraBot", "Bloom Filter", "WARN", "MEDIUM", f"Email possibly registered: {email}")
            return result
        except Exception as e:
            logger("CuraDocs_Doctor_CuraBot", "Bloom Filter", "ERROR", "ERROR", f"Email registration check failed: {str(e)}")
            return False
    
    def add_registered_email(self, email: str):
        """Add email to registered emails filter"""
        try:
            self.registered_emails.add(email.lower())
            self._save_filter("registered_emails", self.registered_emails)
            logger("CuraDocs_Doctor_CuraBot", "Bloom Filter", "INFO", "null", f"Email added to registered filter: {email}")
        except Exception as e:
            logger("CuraDocs_Doctor_CuraBot", "Bloom Filter", "ERROR", "ERROR", f"Failed to add registered email: {str(e)}")
            raise


    """Utility Methods"""
    def get_filter_stats(self) -> dict:
        """Get statistics about bloom filters"""
        try:
            stats = {
                "blacklisted_tokens": {
                    "capacity": self.blacklisted_tokens.capacity,
                    "count": self.blacklisted_tokens.count,
                    "error_rate": self.blacklisted_tokens.error_rate
                },
                "compromised_passwords": {
                    "capacity": self.compromised_passwords.capacity,
                    "count": self.compromised_passwords.count,
                    "error_rate": self.compromised_passwords.error_rate
                },
                "suspicious_ips": {
                    "capacity": self.suspicious_ips.capacity,
                    "count": self.suspicious_ips.count,
                    "error_rate": self.suspicious_ips.error_rate
                },
                "registered_emails": {
                    "capacity": self.registered_emails.capacity,
                    "count": self.registered_emails.count,
                    "error_rate": self.registered_emails.error_rate
                }
            }
            logger("CuraDocs_Doctor_CuraBot", "Bloom Filter", "INFO", "null", "Bloom filter stats retrieved")
            return stats
        except Exception as e:
            logger("CuraDocs_Doctor_CuraBot", "Bloom Filter", "ERROR", "ERROR", f"Failed to get filter stats: {str(e)}")
            return {}


# Global bloom filter service instance
bloom_service = BloomFilterService()