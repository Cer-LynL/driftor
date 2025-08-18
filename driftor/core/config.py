"""
Enterprise-grade configuration management with security-first approach.
"""
import os
from typing import List, Optional
from pydantic import Field, validator
from pydantic_settings import BaseSettings


class SecuritySettings(BaseSettings):
    """Security configuration with enterprise defaults."""
    
    secret_key: str = Field(..., min_length=32)
    encryption_key: str = Field(..., min_length=32)
    jwt_secret_key: str = Field(..., min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    
    # Password policy
    min_password_length: int = 12
    require_special_chars: bool = True
    require_uppercase: bool = True
    require_numbers: bool = True
    
    # Session management
    session_timeout_minutes: int = 480  # 8 hours
    max_concurrent_sessions: int = 5
    
    # Rate limiting
    enable_rate_limiting: bool = True
    rate_limit_jira: int = 100
    rate_limit_github: int = 5000
    rate_limit_slack: int = 100
    rate_limit_teams: int = 100
    
    # Network security
    allowed_ips: str = "0.0.0.0/0"
    cors_origins: List[str] = ["http://localhost:3000"]
    webhook_timeout_seconds: int = 30
    
    @validator('cors_origins', pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(',')]
        return v


class DatabaseSettings(BaseSettings):
    """Database configuration with encryption support."""
    
    database_url: str = Field(..., description="PostgreSQL connection string")
    db_encryption_enabled: bool = True
    db_connection_pool_size: int = 20
    db_max_overflow: int = 30
    db_pool_timeout: int = 30
    db_pool_recycle: int = 3600
    
    # Backup and recovery
    enable_backup_encryption: bool = True
    backup_retention_days: int = 30


class ComplianceSettings(BaseSettings):
    """GDPR, SOC2, and audit compliance settings."""
    
    gdpr_compliance_mode: bool = True
    soc2_compliance_mode: bool = True
    audit_all_actions: bool = True
    data_residency_region: str = "EU"
    
    # Data retention policies (in days)
    retention_analysis_results: int = 90
    retention_code_snippets: int = 30
    retention_chat_history: int = 365
    retention_audit_logs: int = 2555  # 7 years
    
    # Privacy settings
    anonymize_expired_data: bool = True
    enable_data_export: bool = True
    enable_right_to_deletion: bool = True


class IntegrationSettings(BaseSettings):
    """Third-party integration settings with security controls."""
    
    # Webhook secrets
    jira_webhook_secret: Optional[str] = None
    github_webhook_secret: Optional[str] = None
    slack_signing_secret: Optional[str] = None
    teams_app_secret: Optional[str] = None
    
    # API timeouts
    jira_api_timeout: int = 30
    github_api_timeout: int = 30
    confluence_api_timeout: int = 30
    
    # Integration health checks
    health_check_interval: int = 300  # 5 minutes
    max_failed_health_checks: int = 3


class LLMSettings(BaseSettings):
    """LLM configuration for on-premise deployment."""
    
    llm_provider: str = "ollama"
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    
    # OpenAI fallback
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4"
    
    # Model parameters
    max_tokens: int = 4000
    temperature: float = 0.1
    confidence_threshold: float = 0.7
    
    # Embedding configuration
    embedding_model: str = "all-MiniLM-L6-v2"


class VectorDBSettings(BaseSettings):
    """Vector database configuration for similarity search."""
    
    type: str = "chromadb"
    host: str = "localhost"
    port: int = 8000
    ssl: bool = False
    
    # Authentication
    auth_token: Optional[str] = None
    headers: dict = {}
    
    # Embedding configuration
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384
    
    # Performance settings
    batch_size: int = 100
    max_connections: int = 10
    timeout_seconds: int = 30


class MonitoringSettings(BaseSettings):
    """Monitoring and observability configuration."""
    
    enable_prometheus_metrics: bool = True
    enable_structured_logging: bool = True
    log_level: str = "INFO"
    
    # Grafana
    grafana_password: str = "admin"
    
    # Health checks
    health_check_enabled: bool = True
    health_check_timeout: int = 10


class EnterpriseSettings(BaseSettings):
    """Enterprise-specific features."""
    
    # Multi-tenancy
    enable_multi_tenancy: bool = True
    max_tenants: int = 1000
    
    # SSO Integration
    enable_saml_sso: bool = False
    saml_metadata_url: Optional[str] = None
    saml_entity_id: str = "driftor"
    
    enable_oidc_sso: bool = False
    oidc_discovery_url: Optional[str] = None
    oidc_client_id: Optional[str] = None
    oidc_client_secret: Optional[str] = None
    
    # Enterprise features
    enable_advanced_analytics: bool = True
    enable_custom_workflows: bool = True
    enable_api_access: bool = True


class Settings(BaseSettings):
    """Main application settings combining all configuration areas."""
    
    environment: str = "development"
    debug: bool = False
    
    # Sub-configurations
    security: SecuritySettings = SecuritySettings()
    database: DatabaseSettings = DatabaseSettings()
    compliance: ComplianceSettings = ComplianceSettings()
    integrations: IntegrationSettings = IntegrationSettings()
    llm: LLMSettings = LLMSettings()
    vector_db: VectorDBSettings = VectorDBSettings()
    monitoring: MonitoringSettings = MonitoringSettings()
    enterprise: EnterpriseSettings = EnterpriseSettings()
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_password: Optional[str] = None
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        env_nested_delimiter = "__"
    
    @validator('debug')
    def debug_security_check(cls, v, values):
        """Ensure debug is never enabled in production."""
        if values.get('environment') == 'production' and v:
            raise ValueError("Debug mode cannot be enabled in production")
        return v
    
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"
    
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment.lower() == "development"


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings singleton."""
    return settings