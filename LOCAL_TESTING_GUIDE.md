# Driftor Local Testing Guide

This guide will help you set up and test the complete Driftor solution on your local machine.

## Prerequisites

### Required Software
- **Docker & Docker Compose** (v2.0+)
- **Python 3.11+**
- **Git**
- **curl** or **Postman** for API testing

### Optional for Advanced Testing
- **Jira Cloud/Server instance** (for integration testing)
- **GitHub account** with personal access token
- **Slack workspace** (for bot testing)
- **OpenAI API key** (for LLM fallback)

## Quick Start (15 minutes)

### 1. Clone and Setup Environment

```bash
cd /Users/Cer/Desktop/driftor_v2

# Copy environment file
cp .env.example .env

# Generate secure keys
python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))" >> .env.local
python3 -c "import secrets; print('ENCRYPTION_KEY=' + secrets.token_urlsafe(32))" >> .env.local  
python3 -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(32))" >> .env.local

# Edit .env with your generated keys
```

### 2. Start Infrastructure Services

```bash
# Start all services
docker-compose up -d

# Wait for services to be ready (2-3 minutes)
docker-compose logs -f
```

### 3. Install Python Dependencies

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .
```

### 4. Initialize Database

```bash
# Run database migrations
python -m alembic upgrade head

# Create test tenant
python scripts/create_test_data.py
```

### 5. Start Driftor Application

```bash
# Start the API server
python -m driftor.main
```

The application will be available at: http://localhost:8000

## Service Verification

### Check Service Health

```bash
# Check all services
curl http://localhost:8000/health

# Expected response:
# {
#   "status": "healthy",
#   "services": {
#     "database": "healthy",
#     "redis": "healthy", 
#     "vector_db": "healthy",
#     "llm": "healthy"
#   }
# }
```

### Verify Individual Services

```bash
# Database
curl http://localhost:5432  # Should connect

# Redis  
redis-cli ping  # Should return PONG

# ChromaDB
curl http://localhost:8000  # ChromaDB API

# Ollama (if available)
curl http://localhost:11434  # Ollama API

# Grafana Dashboard
open http://localhost:3000  # admin/admin
```

## End-to-End Testing Scenarios

### Scenario 1: Basic Ticket Analysis (No External Integrations)

This test uses simulated data and doesn't require external service accounts.

```bash
# Test ticket analysis
curl -X POST http://localhost:8000/api/v1/tickets/analyze \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <test-token>" \
  -d '{
    "ticket_data": {
      "key": "TEST-123",
      "summary": "Null pointer exception in user service",
      "description": "Getting NullPointerException when accessing user.getProfile() method. Stack trace shows the error occurs in UserService.java line 45.",
      "issue_type": "Bug",
      "priority": "High",
      "component": "backend",
      "assignee": {"displayName": "John Doe"},
      "created": "2024-01-15T10:00:00Z"
    },
    "tenant_id": "test-tenant"
  }'
```

Expected flow:
1. ✅ Ticket gets classified (bug detection, severity analysis)
2. ✅ Similar tickets searched in vector database
3. ✅ Documentation retrieved (simulated results)
4. ✅ Repository mapped (simulated code analysis)
5. ✅ AI analysis generated using LLM
6. ✅ Results stored with audit trail

### Scenario 2: Full Integration Test (Requires External Services)

For this test, you'll need actual service credentials.

#### Setup Integration Credentials

```bash
# Edit .env file with real credentials
JIRA_BASE_URL=https://your-company.atlassian.net
JIRA_USERNAME=your-email@company.com
JIRA_API_TOKEN=your-jira-api-token

GITHUB_TOKEN=ghp_your_github_personal_access_token

SLACK_BOT_TOKEN=xoxb-your-slack-bot-token
SLACK_SIGNING_SECRET=your-slack-signing-secret
```

#### Test Real Jira Integration

```bash
# Test Jira webhook simulation
curl -X POST http://localhost:8000/webhooks/jira \
  -H "Content-Type: application/json" \
  -H "X-Atlassian-Webhook-Signature: sha256=<calculated-signature>" \
  -d '{
    "webhookEvent": "jira:issue_updated",
    "issue": {
      "key": "PROJ-456",
      "fields": {
        "summary": "API timeout in payment service",
        "description": "Payment API timing out after 30 seconds",
        "issuetype": {"name": "Bug"},
        "priority": {"name": "High"},
        "assignee": {"displayName": "Jane Smith"},
        "created": "2024-01-15T14:30:00Z"
      }
    }
  }'
```

#### Test GitHub Integration

```bash
# Test repository analysis
curl -X POST http://localhost:8000/api/v1/repositories/analyze \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <test-token>" \
  -d '{
    "repository": {
      "owner": "your-github-username",
      "repo": "your-test-repo",
      "provider": "github"
    },
    "ticket_key": "PROJ-456",
    "tenant_id": "test-tenant"
  }'
```

### Scenario 3: Interactive Chat Testing

```bash
# Start chat session
curl -X POST http://localhost:8000/api/v1/chat/sessions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <test-token>" \
  -d '{
    "user_id": "test-user",
    "tenant_id": "test-tenant",
    "ticket_context": "TEST-123"
  }'

# Send chat message
curl -X POST http://localhost:8000/api/v1/chat/sessions/{session_id}/messages \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <test-token>" \
  -d '{
    "message": "Can you explain what might be causing this null pointer exception?",
    "user_id": "test-user"
  }'
```

## Testing Different Components

### 1. Vector Database Testing

```bash
# Index a test document
curl -X POST http://localhost:8000/api/v1/vector/index \
  -H "Content-Type: application/json" \
  -d '{
    "collection": "tickets_test-tenant",
    "documents": [{
      "id": "test-doc-1",
      "content": "This is a test bug report about null pointer exception",
      "metadata": {"ticket_key": "TEST-001", "component": "backend"}
    }]
  }'

# Search for similar documents
curl -X POST http://localhost:8000/api/v1/vector/search \
  -H "Content-Type: application/json" \
  -d '{
    "collection": "tickets_test-tenant", 
    "query": "null pointer exception bug",
    "n_results": 5
  }'
```

### 2. LLM Integration Testing

```bash
# Test Ollama connection
curl -X GET http://localhost:8000/api/v1/llm/health

# Test code analysis
curl -X POST http://localhost:8000/api/v1/llm/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "prompt_type": "code_analysis",
    "context": {
      "ticket_key": "TEST-123",
      "summary": "Null pointer exception",
      "code_files": "UserService.java: public Profile getProfile() { return user.profile; }",
      "component": "backend"
    },
    "tenant_id": "test-tenant"
  }'
```

### 3. Messaging Integration Testing

If you have Slack/Teams configured:

```bash
# Test Slack notification
curl -X POST http://localhost:8000/api/v1/messaging/notify \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "slack",
    "user_id": "U1234567",
    "ticket_data": {"key": "TEST-123", "summary": "Test issue"},
    "analysis_results": {"confidence": 0.85, "severity": "high"},
    "tenant_id": "test-tenant"
  }'
```

## Performance Testing

### Load Testing with Simple Script

```python
# test_load.py
import asyncio
import aiohttp
import time

async def test_ticket_analysis():
    async with aiohttp.ClientSession() as session:
        tasks = []
        for i in range(10):  # 10 concurrent requests
            task = session.post(
                'http://localhost:8000/api/v1/tickets/analyze',
                json={
                    "ticket_data": {
                        "key": f"LOAD-{i}",
                        "summary": f"Load test ticket {i}",
                        "description": "Test description",
                        "issue_type": "Bug",
                        "priority": "Medium"
                    },
                    "tenant_id": "test-tenant"
                }
            )
            tasks.append(task)
        
        start = time.time()
        responses = await asyncio.gather(*tasks)
        end = time.time()
        
        print(f"Processed 10 tickets in {end-start:.2f} seconds")

# Run with: python test_load.py
asyncio.run(test_ticket_analysis())
```

## Troubleshooting Common Issues

### Services Not Starting

```bash
# Check Docker logs
docker-compose logs postgres
docker-compose logs redis
docker-compose logs chromadb

# Restart specific service
docker-compose restart postgres
```

### Database Connection Issues

```bash
# Test database connection
python -c "
from driftor.core.database import get_database_url
import asyncpg
import asyncio
async def test():
    conn = await asyncpg.connect(get_database_url())
    print('Database connected!')
    await conn.close()
asyncio.run(test())
"
```

### LLM Not Available

```bash
# Pull Ollama model
docker exec -it driftor_v2-ollama-1 ollama pull llama3.1:8b

# Test Ollama directly
curl http://localhost:11434/api/generate -d '{
  "model": "llama3.1:8b",
  "prompt": "Say hello",
  "stream": false
}'
```

### Vector Database Issues

```bash
# Check ChromaDB
curl http://localhost:8000/api/v1/heartbeat

# Reset ChromaDB (if needed)
docker-compose restart chromadb
```

## Monitoring and Logs

### View Application Logs

```bash
# API server logs
tail -f logs/driftor.log

# Docker service logs
docker-compose logs -f driftor-api
```

### Grafana Dashboards

1. Open http://localhost:3000
2. Login: admin/admin
3. View pre-configured dashboards:
   - Application Metrics
   - Database Performance
   - LLM Usage Statistics
   - Integration Health

### Prometheus Metrics

- API Metrics: http://localhost:8000/metrics
- System Metrics: http://localhost:9090

## Next Steps

Once basic testing works:

1. **Configure Real Integrations**: Add actual Jira, GitHub, Slack credentials
2. **Load Test Data**: Import real tickets and documentation
3. **Custom Workflows**: Test with your specific use cases
4. **Security Testing**: Test authentication, authorization, rate limiting
5. **Performance Tuning**: Optimize based on your data volume

## Getting Help

If you encounter issues:

1. Check the logs in `logs/` directory
2. Verify all services are healthy via `/health` endpoint
3. Review the Docker Compose logs
4. Check the troubleshooting section above

The system is designed to work with minimal external dependencies for basic testing, with full integration capabilities when credentials are provided.