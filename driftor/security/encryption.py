"""
Enterprise-grade encryption utilities for per-tenant data protection.
Implements AES-256-GCM encryption with secure key management.
"""
import base64
import os
from typing import Dict, Optional, Tuple
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import structlog

logger = structlog.get_logger(__name__)


class EncryptionError(Exception):
    """Base exception for encryption operations."""
    pass


class TenantEncryption:
    """Per-tenant encryption manager with key isolation."""
    
    def __init__(self, master_key: str):
        """Initialize with master encryption key."""
        self.master_key = base64.urlsafe_b64decode(master_key.encode())
        self._tenant_keys: Dict[str, bytes] = {}
        
    def _derive_tenant_key(self, tenant_id: str, salt: Optional[bytes] = None) -> Tuple[bytes, bytes]:
        """Derive tenant-specific encryption key from master key."""
        if salt is None:
            salt = os.urandom(16)
            
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        
        # Combine master key with tenant ID for derivation
        key_material = self.master_key + tenant_id.encode()
        derived_key = kdf.derive(key_material)
        
        return derived_key, salt
    
    def get_tenant_key(self, tenant_id: str) -> bytes:
        """Get or create tenant-specific encryption key."""
        if tenant_id not in self._tenant_keys:
            key, _ = self._derive_tenant_key(tenant_id)
            self._tenant_keys[tenant_id] = key
            
        return self._tenant_keys[tenant_id]
    
    def encrypt_data(self, tenant_id: str, data: str) -> str:
        """Encrypt data using tenant-specific key."""
        try:
            tenant_key = self.get_tenant_key(tenant_id)
            aesgcm = AESGCM(tenant_key)
            nonce = os.urandom(12)  # 96-bit nonce for GCM
            
            ciphertext = aesgcm.encrypt(
                nonce, 
                data.encode('utf-8'), 
                tenant_id.encode('utf-8')  # Additional authenticated data
            )
            
            # Combine nonce + ciphertext and encode
            encrypted_data = nonce + ciphertext
            return base64.urlsafe_b64encode(encrypted_data).decode('utf-8')
            
        except Exception as e:
            logger.error(
                "Encryption failed",
                tenant_id=tenant_id,
                error=str(e),
                exc_info=True
            )
            raise EncryptionError(f"Failed to encrypt data: {e}")
    
    def decrypt_data(self, tenant_id: str, encrypted_data: str) -> str:
        """Decrypt data using tenant-specific key."""
        try:
            tenant_key = self.get_tenant_key(tenant_id)
            aesgcm = AESGCM(tenant_key)
            
            # Decode and separate nonce from ciphertext
            raw_data = base64.urlsafe_b64decode(encrypted_data.encode('utf-8'))
            nonce = raw_data[:12]
            ciphertext = raw_data[12:]
            
            plaintext = aesgcm.decrypt(
                nonce,
                ciphertext,
                tenant_id.encode('utf-8')  # Additional authenticated data
            )
            
            return plaintext.decode('utf-8')
            
        except Exception as e:
            logger.error(
                "Decryption failed",
                tenant_id=tenant_id,
                error=str(e),
                exc_info=True
            )
            raise EncryptionError(f"Failed to decrypt data: {e}")
    
    def encrypt_sensitive_fields(self, tenant_id: str, data: Dict[str, any]) -> Dict[str, any]:
        """Encrypt sensitive fields in a dictionary."""
        sensitive_fields = {
            'password', 'token', 'secret', 'key', 'api_key', 
            'access_token', 'refresh_token', 'webhook_secret',
            'private_key', 'certificate'
        }
        
        encrypted_data = data.copy()
        
        for field, value in data.items():
            if any(sensitive in field.lower() for sensitive in sensitive_fields):
                if isinstance(value, str) and value:
                    encrypted_data[field] = self.encrypt_data(tenant_id, value)
                    logger.debug("Encrypted sensitive field", field=field, tenant_id=tenant_id)
        
        return encrypted_data
    
    def decrypt_sensitive_fields(self, tenant_id: str, data: Dict[str, any]) -> Dict[str, any]:
        """Decrypt sensitive fields in a dictionary."""
        sensitive_fields = {
            'password', 'token', 'secret', 'key', 'api_key',
            'access_token', 'refresh_token', 'webhook_secret',
            'private_key', 'certificate'
        }
        
        decrypted_data = data.copy()
        
        for field, value in data.items():
            if any(sensitive in field.lower() for sensitive in sensitive_fields):
                if isinstance(value, str) and value:
                    try:
                        decrypted_data[field] = self.decrypt_data(tenant_id, value)
                        logger.debug("Decrypted sensitive field", field=field, tenant_id=tenant_id)
                    except EncryptionError:
                        # Field might not be encrypted (backwards compatibility)
                        logger.warning("Failed to decrypt field, assuming plaintext", 
                                     field=field, tenant_id=tenant_id)
        
        return decrypted_data


class FieldLevelEncryption:
    """Field-level encryption for database columns."""
    
    def __init__(self, encryption_manager: TenantEncryption):
        self.encryption_manager = encryption_manager
    
    def encrypt_field(self, tenant_id: str, field_name: str, value: str) -> str:
        """Encrypt a single field value."""
        if not value:
            return value
            
        return self.encryption_manager.encrypt_data(tenant_id, value)
    
    def decrypt_field(self, tenant_id: str, field_name: str, encrypted_value: str) -> str:
        """Decrypt a single field value."""
        if not encrypted_value:
            return encrypted_value
            
        return self.encryption_manager.decrypt_data(tenant_id, encrypted_value)


class SecureTokenGenerator:
    """Generate cryptographically secure tokens for various purposes."""
    
    @staticmethod
    def generate_api_key(length: int = 32) -> str:
        """Generate a secure API key."""
        return base64.urlsafe_b64encode(os.urandom(length)).decode('utf-8')
    
    @staticmethod
    def generate_webhook_secret(length: int = 32) -> str:
        """Generate a secure webhook secret."""
        return base64.urlsafe_b64encode(os.urandom(length)).decode('utf-8')
    
    @staticmethod
    def generate_encryption_key() -> str:
        """Generate a new encryption key for Fernet."""
        return Fernet.generate_key().decode('utf-8')


# Global encryption instance
_encryption_manager: Optional[TenantEncryption] = None


def get_encryption_manager() -> TenantEncryption:
    """Get global encryption manager instance."""
    global _encryption_manager
    
    if _encryption_manager is None:
        from driftor.core.config import get_settings
        settings = get_settings()
        _encryption_manager = TenantEncryption(settings.security.encryption_key)
    
    return _encryption_manager


def encrypt_for_tenant(tenant_id: str, data: str) -> str:
    """Convenience function to encrypt data for a tenant."""
    return get_encryption_manager().encrypt_data(tenant_id, data)


def decrypt_for_tenant(tenant_id: str, encrypted_data: str) -> str:
    """Convenience function to decrypt data for a tenant."""
    return get_encryption_manager().decrypt_data(tenant_id, encrypted_data)