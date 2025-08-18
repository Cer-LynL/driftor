# Driftor Enterprise

AI-powered bug analysis and resolution assistant designed for enterprise teams. Automatically analyzes Jira tickets, searches for similar issues, retrieves relevant documentation, and provides intelligent code-level fix suggestions.

## 🚀 Enterprise Features

### Security & Compliance
- **Multi-tenant architecture** with complete data isolation
- **End-to-end encryption** with per-tenant keys
- **GDPR compliance** with data retention policies and right to erasure
- **SOC2 Type II ready** with comprehensive audit logging
- **Row-level security** in PostgreSQL for tenant isolation
- **Rate limiting** and DDoS protection
- **Enterprise SSO** support (SAML, OIDC)

### Integrations
- **Jira Cloud/Server/Data Center** for ticket management
- **GitHub/GitLab/Bitbucket** for code repository access
- **Microsoft Teams & Slack** for notifications
- **Confluence** for documentation search
- **On-premise LLM** support (Ollama, vLLM)

### Architecture
- **Microservices-ready** containerized deployment
- **Horizontal scaling** with Kubernetes support
- **High availability** with Redis clustering
- **Monitoring & observability** with Prometheus & Grafana
- **Automated backups** with encryption

## 🏗️ Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.11+
- PostgreSQL 16+
- Redis 7+

### 1. Environment Setup

```bash
# Clone the repository
git clone https://github.com/your-org/driftor-enterprise.git
cd driftor-enterprise

# Copy environment configuration
cp .env.example .env

# Generate secure keys
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))"
python -c "import base64, os; print('ENCRYPTION_KEY=' + base64.urlsafe_b64encode(os.urandom(32)).decode())"
```

### 2. Configure Environment Variables

Edit `.env` file with your specific settings:

```bash
# Required: Update these values
SECRET_KEY=your-generated-secret-key
ENCRYPTION_KEY=your-generated-encryption-key
DB_PASSWORD=your-secure-db-password
REDIS_PASSWORD=your-secure-redis-password

# Integration credentials (obtain from your services)
JIRA_WEBHOOK_SECRET=your-jira-webhook-secret
GITHUB_WEBHOOK_SECRET=your-github-webhook-secret
SLACK_SIGNING_SECRET=your-slack-signing-secret
TEAMS_APP_SECRET=your-teams-app-secret
```

### 3. Deploy with Docker

```bash
# Start all services
docker-compose up -d

# Check service health
curl http://localhost:8000/health

# View logs
docker-compose logs -f driftor-api
```

### 4. Access the Application

- **API**: http://localhost:8000
- **Health Check**: http://localhost:8000/health
- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090

## 🔧 Enterprise Deployment

### Kubernetes Deployment

```bash
# Apply Kubernetes manifests
kubectl apply -f k8s/

# Configure ingress and TLS
kubectl apply -f k8s/ingress.yaml
```

### High Availability Setup

```bash
# Scale API instances
docker-compose up -d --scale driftor-api=3

# Setup Redis cluster
docker-compose -f docker-compose.prod.yml up -d
```

## 🔐 Security Configuration

### 1. Network Security

```yaml
# Configure IP whitelisting
ALLOWED_IPS=10.0.0.0/8,192.168.0.0/16

# CORS origins
CORS_ORIGINS=https://your-domain.com,https://admin.your-domain.com
```

### 2. Authentication Setup

```bash
# Enable SSO (SAML)
ENABLE_SAML_SSO=true
SAML_METADATA_URL=https://your-idp.com/metadata
SAML_ENTITY_ID=driftor-enterprise

# Enable SSO (OIDC)
ENABLE_OIDC_SSO=true
OIDC_DISCOVERY_URL=https://your-idp.com/.well-known/openid_configuration
OIDC_CLIENT_ID=your-client-id
OIDC_CLIENT_SECRET=your-client-secret
```

### 3. Data Residency

```bash
# Set data residency region
DATA_RESIDENCY_REGION=EU
GDPR_COMPLIANCE_MODE=true
AUDIT_RETENTION_DAYS=2555  # 7 years
```

## 🔌 Integration Setup

### Jira Configuration

1. **Create Webhook** in Jira:
   - URL: `https://your-domain.com/webhooks/jira`
   - Events: Issue Created, Issue Updated, Issue Assigned
   - Secret: Use `JIRA_WEBHOOK_SECRET`

2. **Create App Password** for API access:
   - Go to Account Settings → Security → Create App Password
   - Scope: Read/Write Issues, Read Projects

### GitHub/GitLab Setup

1. **Create GitHub App**:
   - Repository permissions: Contents (read), Issues (read), Pull requests (read)
   - Webhook URL: `https://your-domain.com/webhooks/github`
   - Secret: Use `GITHUB_WEBHOOK_SECRET`

2. **Install App** on target repositories

### Teams/Slack Bot Setup

#### Microsoft Teams
1. **Register App** in Azure AD:
   - API Permissions: Chat.ReadWrite, User.Read
   - Bot Framework registration
   - Messaging endpoint: `https://your-domain.com/webhooks/teams`

#### Slack
1. **Create Slack App**:
   - Bot scopes: chat:write, users:read, channels:read
   - Event subscriptions: `https://your-domain.com/webhooks/slack`
   - Signing secret: Use `SLACK_SIGNING_SECRET`

## 📊 Monitoring & Observability

### Metrics Collection

```bash
# View Prometheus metrics
curl http://localhost:8000/metrics

# Key metrics monitored:
# - API response times
# - Database connection pool usage  
# - Rate limit violations
# - Integration health status
# - Tenant usage statistics
```

### Grafana Dashboards

Pre-configured dashboards for:
- System overview
- API performance
- Security events
- Tenant usage
- Integration health

### Log Analysis

```bash
# View structured logs
docker-compose logs driftor-api | jq '.'

# Filter by tenant
docker-compose logs driftor-api | jq 'select(.tenant_id=="your-tenant-id")'

# Security events
docker-compose logs driftor-api | jq 'select(.event_type=="security.access_denied")'
```

## 🏢 Multi-Tenant Management

### Creating Tenants

```bash
# Via API (requires admin authentication)
curl -X POST http://localhost:8000/api/v1/tenants \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -d '{
    "name": "Acme Corporation",
    "slug": "acme-corp",
    "admin_email": "admin@acme.com",
    "tier": "enterprise"
  }'
```

### Tenant Configuration

Each tenant can configure:
- Integration credentials (encrypted)
- Notification preferences
- Data retention policies
- User roles and permissions
- Rate limits and usage quotas

## 🔍 Testing & Validation

### Health Checks

```bash
# Basic health check
curl http://localhost:8000/health

# Detailed health check (requires auth in production)
curl http://localhost:8000/health/detailed

# Integration-specific health
curl http://localhost:8000/api/v1/integrations/health
```

### Load Testing

```bash
# Using Apache Bench
ab -n 1000 -c 10 http://localhost:8000/health

# Using k6
k6 run tests/load/api-test.js
```

### Security Testing

```bash
# Run security tests
pytest tests/security/

# OWASP ZAP integration
docker run -t owasp/zap2docker-stable zap-baseline.py -t http://localhost:8000
```

## 📚 API Documentation

### Authentication

All API endpoints require JWT authentication:

```bash
# Login to get token
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@company.com",
    "password": "your-password",
    "tenant_id": "your-tenant-id"
  }'
```

### Core Endpoints

- `GET /api/v1/tickets` - List analyzed tickets
- `POST /api/v1/tickets/{id}/analyze` - Trigger ticket analysis
- `GET /api/v1/analysis/{id}` - Get analysis results
- `POST /api/v1/chat` - Chat with Driftor AI
- `GET /api/v1/integrations` - List tenant integrations

### Webhook Endpoints

- `POST /webhooks/jira` - Jira webhook receiver
- `POST /webhooks/github` - GitHub webhook receiver
- `POST /webhooks/slack` - Slack event receiver
- `POST /webhooks/teams` - Teams bot webhook

## 🔧 Troubleshooting

### Common Issues

**Database Connection Failed**
```bash
# Check PostgreSQL status
docker-compose ps postgres

# View database logs
docker-compose logs postgres

# Test connection
docker-compose exec postgres psql -U driftor -d driftor -c "SELECT 1;"
```

**Integration Authentication Failed**
```bash
# Check integration credentials
docker-compose exec driftor-api python -c "
from driftor.core.config import get_settings
from driftor.security.encryption import get_encryption_manager
# Debug credential decryption
"

# Test integration connectivity
curl -X GET http://localhost:8000/api/v1/integrations/test
```

**Rate Limiting Issues**
```bash
# Check Redis connection
docker-compose exec redis redis-cli ping

# View rate limit status
curl -H "Authorization: Bearer TOKEN" \
  http://localhost:8000/api/v1/rate-limits/status
```

### Log Analysis

```bash
# Application errors
docker-compose logs driftor-api | grep ERROR

# Security events
docker-compose logs driftor-api | grep "audit.*security"

# Performance issues
docker-compose logs driftor-api | grep "duration" | jq 'select(.duration > 1000)'
```

## 📞 Support

For enterprise support:
- Email: enterprise@driftor.dev
- Documentation: https://docs.driftor.dev
- Status Page: https://status.driftor.dev

## 📄 License

Driftor Enterprise - Proprietary License
Copyright (c) 2024 Driftor, Inc.

This software is proprietary and confidential. Unauthorized copying, distribution, or use is strictly prohibited.