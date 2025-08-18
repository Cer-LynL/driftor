# 🧪 Driftor Local Testing Guide

Complete guide to test the Driftor AI bug analysis system end-to-end on your local machine.

## 🚀 Quick Start (5 Commands)

```bash
# 1. Verify implementation
python scripts/verify_implementation.py

# 2. Setup environment  
cp .env.example .env
# Edit .env with secure keys (see below)

# 3. Start all services
./start_driftor.sh

# 4. Wait for startup, then test
python scripts/test_api.py

# 5. View results in browser
open http://localhost:8000/docs
```

## 📋 Prerequisites

- **Docker Desktop** (running)
- **Python 3.11+**
- **8GB+ RAM** (for AI models)
- **10GB+ disk space** (for models and data)

## 🔧 Detailed Setup

### 1. Environment Configuration

```bash
# Copy environment template
cp .env.example .env

# Generate secure keys (required)
python3 -c "
import secrets
print('SECRET_KEY=' + secrets.token_urlsafe(32))
print('ENCRYPTION_KEY=' + secrets.token_urlsafe(32))  
print('JWT_SECRET_KEY=' + secrets.token_urlsafe(32))
" >> .env
```

### 2. Optional: Add Real Integration Credentials

For full testing with real services, add to your `.env`:

```bash
# Jira (optional)
JIRA_BASE_URL=https://your-company.atlassian.net
JIRA_USERNAME=your-email@company.com
JIRA_API_TOKEN=your-jira-api-token

# GitHub (optional)
GITHUB_TOKEN=ghp_your_github_personal_access_token

# Slack (optional)
SLACK_BOT_TOKEN=xoxb-your-slack-bot-token
SLACK_SIGNING_SECRET=your-slack-signing-secret

# OpenAI Fallback (optional)
LLM__OPENAI_API_KEY=sk-your-openai-api-key
```

### 3. Start Services

```bash
# Automated startup
./start_driftor.sh

# OR manual startup
docker-compose up -d
source venv/bin/activate
pip install -e .
python -m alembic upgrade head
python scripts/create_test_data.py
python -m driftor.main
```

## 🧪 Testing Scenarios

### Level 1: Basic Functionality (No External APIs)

Tests core AI functionality with simulated data:

```bash
# Verify all components work
python scripts/verify_implementation.py

# Run automated API tests
python scripts/test_api.py
```

**What this tests:**
- ✅ Ticket classification and analysis
- ✅ Vector similarity search
- ✅ LLM-powered code analysis  
- ✅ Documentation retrieval
- ✅ Repository mapping (simulated)
- ✅ Chat interactions
- ✅ Webhook processing

### Level 2: Real Integration Testing

Tests with actual external services:

#### Test Real Jira Integration

```bash
# Simulate Jira webhook
curl -X POST http://localhost:8000/webhooks/jira \
  -H "Content-Type: application/json" \
  -d '{
    "webhookEvent": "jira:issue_created",
    "issue": {
      "key": "REAL-123",
      "fields": {
        "summary": "Production API timeout in payment service",
        "description": "Users experiencing 30s timeouts during checkout",
        "issuetype": {"name": "Bug"},
        "priority": {"name": "Critical"},
        "assignee": {"displayName": "Your Name"}
      }
    }
  }'
```

#### Test GitHub Repository Analysis

```bash
# Analyze real repository
curl -X POST http://localhost:8000/api/v1/repositories/analyze \
  -H "Authorization: Bearer $(cat test_tokens.txt | grep ADMIN_TOKEN | cut -d= -f2)" \
  -H "Content-Type: application/json" \
  -d '{
    "repository": {
      "owner": "your-github-username",
      "repo": "your-test-repo", 
      "provider": "github"
    },
    "ticket_key": "REAL-123",
    "tenant_id": "test-tenant"
  }'
```

### Level 3: Interactive Testing

#### Test Slack/Teams Notifications

If configured, test real notifications:

```bash
# Send notification to Slack
curl -X POST http://localhost:8000/api/v1/messaging/notify \
  -H "Authorization: Bearer $(cat test_tokens.txt | grep ADMIN_TOKEN | cut -d= -f2)" \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "slack",
    "user_id": "your-slack-user-id",
    "ticket_data": {
      "key": "TEST-SLACK",
      "summary": "Test notification from Driftor"
    },
    "analysis_results": {
      "confidence": 0.92,
      "severity": "high", 
      "component": "payment-service"
    },
    "tenant_id": "test-tenant"
  }'
```

#### Interactive Chat Testing

```bash
# Start chat session
SESSION_ID=$(curl -s -X POST http://localhost:8000/api/v1/chat/sessions \
  -H "Authorization: Bearer $(cat test_tokens.txt | grep ADMIN_TOKEN | cut -d= -f2)" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test-developer",
    "tenant_id": "test-tenant"
  }' | jq -r '.session_id')

# Chat with Driftor
curl -X POST http://localhost:8000/api/v1/chat/sessions/$SESSION_ID/messages \
  -H "Authorization: Bearer $(cat test_tokens.txt | grep ADMIN_TOKEN | cut -d= -f2)" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Explain how to debug a null pointer exception in Java",
    "user_id": "test-developer"
  }'
```

## 📊 Expected Results

### Successful Test Output

```
🧪 Starting Driftor API Test Suite
==================================================

🔍 Testing health check...
  ✅ Health check passed: healthy

🎫 Testing ticket analysis...
  ✅ Ticket analysis completed
     Classification: backend
     Confidence: 0.85
     Similar tickets: 3
     Documentation: 2

🔍 Testing vector search...
  ✅ Vector search completed: 3 results
     1. PROJ-001 (score: 0.892)
     2. PROJ-004 (score: 0.743)

🤖 Testing LLM analysis...
  ✅ LLM analysis completed
     Provider: ollama
     Model: llama3.1:8b
     Confidence: 0.78

💬 Testing chat session...
  ✅ Chat session created: sess_abc123
  ✅ Chat message processed

🔗 Testing webhook simulation...
  ✅ Webhook processed successfully

==================================================
📊 Test Results Summary
==================================================
✅ PASS Health Check
✅ PASS Ticket Analysis  
✅ PASS Vector Search
✅ PASS LLM Analysis
✅ PASS Chat Session
✅ PASS Webhook Simulation

Results: 6/6 tests passed
🎉 All tests passed! Driftor is working correctly.
```

## 🔍 Monitoring & Debugging

### Service Health Checks

```bash
# Overall health
curl http://localhost:8000/health

# Individual services
curl http://localhost:8000/api/v1/health/detailed
```

### View Logs

```bash
# Application logs
tail -f logs/driftor.log

# Docker service logs  
docker-compose logs -f postgres
docker-compose logs -f redis
docker-compose logs -f chromadb
docker-compose logs -f ollama
```

### Monitoring Dashboards

- **API Documentation**: http://localhost:8000/docs
- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **ChromaDB**: http://localhost:8000 (vector database)

### Database Inspection

```bash
# Connect to database
docker exec -it driftor_v2-postgres-1 psql -U driftor -d driftor_db

# View tenants
SELECT id, name, slug FROM tenants;

# View users  
SELECT email, role, is_active FROM users;

# View audit logs
SELECT event_type, resource_type, created_at FROM audit_logs LIMIT 10;
```

## 🐛 Common Issues & Solutions

### "Ollama model not found"

```bash
# Pull the model manually
docker exec driftor_v2-ollama-1 ollama pull llama3.1:8b

# Or use a different model
docker exec driftor_v2-ollama-1 ollama pull llama3.2:3b
# Update .env: LLM__OLLAMA_MODEL=llama3.2:3b
```

### "Database connection failed"

```bash
# Check if PostgreSQL is running
docker ps | grep postgres

# Reset database
docker-compose restart postgres
python -m alembic upgrade head
```

### "Vector database not responding"

```bash
# Check ChromaDB
curl http://localhost:8000/api/v1/heartbeat

# Restart ChromaDB
docker-compose restart chromadb
```

### "Tests failing with authentication errors"

```bash
# Recreate test tokens
python scripts/create_test_data.py

# Check token file
cat test_tokens.txt
```

## 🚀 Performance Testing

### Load Testing

```python
# save as load_test.py
import asyncio
import aiohttp
import time

async def load_test():
    async with aiohttp.ClientSession() as session:
        # Test 50 concurrent ticket analyses
        start = time.time()
        tasks = []
        
        for i in range(50):
            task = session.post(
                'http://localhost:8000/api/v1/tickets/analyze',
                json={
                    "ticket_data": {
                        "key": f"LOAD-{i}",
                        "summary": f"Load test issue {i}",
                        "description": "Performance testing"
                    },
                    "tenant_id": "test-tenant"
                }
            )
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks)
        end = time.time()
        
        success = sum(1 for r in responses if r.status == 200)
        print(f"Processed {success}/50 tickets in {end-start:.2f}s")

# Run: python load_test.py
asyncio.run(load_test())
```

## 📈 Success Metrics

A successful test run should show:

- ✅ **All API endpoints responding** (6/6 tests pass)
- ✅ **LLM generating analysis** (confidence > 0.5)
- ✅ **Vector search finding similarities** (>= 1 result)
- ✅ **Database operations working** (audit logs created)
- ✅ **Real-time processing** (< 30s response times)
- ✅ **Memory usage stable** (< 4GB total)

## 🎯 Next Steps

Once basic testing works:

1. **Configure Production Integrations**
   - Add real Jira, GitHub, Teams/Slack credentials
   - Test with actual repositories and tickets

2. **Load Your Data**  
   - Import existing tickets for similarity search
   - Index your documentation in vector database
   - Configure your specific repositories

3. **Customize Workflows**
   - Modify prompt templates for your use cases
   - Adjust classification rules
   - Configure team-specific notifications

4. **Deploy to Production**
   - Use production database
   - Configure SSL/TLS
   - Set up monitoring and alerting

## 🆘 Getting Help

If you encounter issues:

1. **Check logs** in `logs/driftor.log`
2. **Verify services** with health checks
3. **Review configuration** in `.env`
4. **Test step by step** using individual curl commands
5. **Check Docker containers** with `docker-compose ps`

The system is designed to work offline with simulated data, so you can test core functionality without any external service accounts.