# Developer Workflow Bot - Complete Setup Guide

## 🎯 Overview

This guide walks you through setting up the Developer Workflow Bot from scratch. The bot analyzes Jira bug tickets and provides intelligent suggestions via Microsoft Teams.

**Time Required:** 2-3 hours for complete setup  
**Difficulty:** Intermediate (requires API tokens and webhook configuration)

---

## 📋 Prerequisites Checklist

Before starting, ensure you have:

- [ ] **Python 3.11+** installed
- [ ] **Git** installed
- [ ] **Docker** installed (recommended) or PostgreSQL + Redis
- [ ] **Microsoft Azure account** (for Teams bot)
- [ ] **Jira admin access** (to create webhooks)
- [ ] **GitHub/GitLab account** with repository access
- [ ] **Anthropic API key** (Claude AI)
- [ ] **Text editor** (VS Code recommended)

---

# Phase 1: Local Environment Setup

## Step 1: Clone and Setup Project

```bash
# Clone the repository
git clone <your-repository-url>
cd developer-workflow-bot

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run setup script
python setup.py
```

## Step 2: Database Setup

**Option A: Docker (Recommended)**
```bash
# Option 1: Start just the databases (recommended for development)
docker-compose -f docker-compose.dev.yml up -d

# Option 2: Use main docker-compose file  
docker-compose up -d postgres redis qdrant

# Verify services are running
docker-compose ps
```

**Option B: Local Installation**
```bash
# Install PostgreSQL
# Windows: Download from postgresql.org
# macOS: brew install postgresql
# Ubuntu: sudo apt install postgresql

# Install Redis
# Windows: Download from redis.io
# macOS: brew install redis  
# Ubuntu: sudo apt install redis-server

# Start services
sudo systemctl start postgresql redis-server
```

## Step 3: Environment Configuration

Copy and edit the environment file:
```bash
cp .env.example .env
```

Edit `.env` with your settings:
```bash
# Basic Configuration
SECRET_KEY=your-super-secret-key-here-make-it-long-and-random
ENVIRONMENT=development
DEBUG=true
DATABASE_URL=postgresql://username:password@localhost:5432/developer_workflow_bot
REDIS_URL=redis://localhost:6379/0

# AI Service (REQUIRED)
ANTHROPIC_API_KEY=your-anthropic-api-key-from-console.anthropic.com

# Microsoft Bot Framework (We'll get these in Phase 2)
MICROSOFT_APP_ID=
MICROSOFT_APP_PASSWORD=
MICROSOFT_BOT_ID=

# Optional - can be configured via web UI later
JIRA_BASE_URL=
JIRA_USERNAME=
JIRA_API_TOKEN=
GITHUB_TOKEN=
```

## Step 4: Initialize Database

```bash
# Generate database migration
alembic revision --autogenerate -m "Initial migration"

# Apply migrations
alembic upgrade head

# Verify database setup
python -c "from app.core.database import SessionLocal; db = SessionLocal(); print('Database connected!')"
```

---

# Phase 2: Microsoft Teams Bot Setup

## Step 1: Create Azure App Registration

1. **Go to Azure Portal**: https://portal.azure.com
2. **Navigate to**: Azure Active Directory → App registrations → New registration
3. **Fill in details**:
   - Name: `Developer Workflow Bot`
   - Supported account types: `Accounts in any organizational directory`
   - Redirect URI: Leave blank for now
4. **Click**: Register

## Step 2: Configure Bot Application

1. **Note down the Application (client) ID** - this is your `MICROSOFT_APP_ID`
2. **Go to**: Certificates & secrets → New client secret
3. **Create secret**:
   - Description: `Bot Secret`
   - Expires: `24 months`
4. **Copy the secret value** - this is your `MICROSOFT_APP_PASSWORD` (you can't see it again!)

## Step 3: Create Bot Service

1. **Go to**: Azure Portal → Create a resource → Search "Bot"
2. **Select**: Azure Bot → Create
3. **Fill in details**:
   - Bot handle: `developer-workflow-bot` (must be unique)
   - Subscription: Your subscription
   - Resource group: Create new or use existing
   - Pricing tier: `F0 (Free)`
   - Microsoft App ID: Use the App ID from Step 1
4. **Click**: Create

## Step 4: Configure Bot Endpoint

1. **In your bot resource**: Go to Configuration
2. **Set Messaging endpoint**: `https://your-domain.com/api/v1/bot/messages`
   - For local testing: Use ngrok (see Phase 4)
3. **Save** the configuration

## Step 5: Add Teams Channel

1. **In your bot resource**: Go to Channels
2. **Click**: Microsoft Teams icon
3. **Configure**: Accept defaults and click Save
4. **Test**: Click "Test in Web Chat" to verify basic functionality

## Step 6: Update Environment Variables

Add to your `.env` file:
```bash
MICROSOFT_APP_ID=your-application-id-from-step-2
MICROSOFT_APP_PASSWORD=your-secret-value-from-step-2  
MICROSOFT_BOT_ID=your-bot-handle-from-step-3
```

---

# Phase 3: External Integrations Setup

## Step 1: Anthropic API Key

1. **Go to**: https://console.anthropic.com
2. **Sign up/Login** with your account
3. **Navigate to**: API Keys
4. **Create new key**: Give it a descriptive name
5. **Copy the key** and add to `.env`:
```bash
ANTHROPIC_API_KEY=your-anthropic-api-key-here
```

## Step 2: Jira Integration (Option A: Manual)

1. **Go to**: Your Jira instance → Profile → Personal Access Tokens
2. **Create token**:
   - Label: `Developer Workflow Bot`
   - Expiry: Choose appropriate duration
3. **Copy token** and add to `.env`:
```bash
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_USERNAME=your-email@company.com
JIRA_API_TOKEN=your-personal-access-token
```

## Step 3: GitHub Integration

1. **Go to**: GitHub → Settings → Developer settings → Personal access tokens
2. **Generate new token** (classic):
   - Note: `Developer Workflow Bot`
   - Expiration: Choose appropriate duration
   - Scopes: Check `repo` (Full control of private repositories)
3. **Copy token** and add to `.env`:
```bash
GITHUB_TOKEN=your-personal-access-token
```

## Step 4: Confluence Integration (Optional)

1. **Use same Jira token** for Confluence:
```bash
CONFLUENCE_BASE_URL=https://your-domain.atlassian.net/wiki
CONFLUENCE_USERNAME=your-email@company.com
CONFLUENCE_API_TOKEN=your-personal-access-token-from-jira
```

---

# Phase 4: Local Testing Setup

## Step 1: Install ngrok (for webhook testing)

```bash
# Download from https://ngrok.com/download
# Or install via package manager:
# Windows: choco install ngrok
# macOS: brew install ngrok
# Ubuntu: snap install ngrok

# Sign up at ngrok.com and get auth token
ngrok authtoken your-ngrok-auth-token
```

## Step 2: Start Application Services

**Terminal 1: Main Application**
```bash
source venv/bin/activate  # Windows: venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
```

**Terminal 2: Background Worker**
```bash
source venv/bin/activate  # Windows: venv\Scripts\activate
celery -A app.tasks worker --loglevel=info
```

**Terminal 3: Public Tunnel (for webhooks)**
```bash
ngrok http 8000
```

Note the ngrok URL (e.g., `https://abc123.ngrok.io`) - you'll need this for webhook configuration.

## Step 3: Update Bot Endpoint

1. **Go back to Azure Portal** → Your Bot → Configuration
2. **Update Messaging endpoint**: `https://your-ngrok-url.ngrok.io/api/v1/bot/messages`
3. **Save** configuration

## Step 4: Test Basic Functionality

1. **Visit**: http://localhost:8000/docs (API documentation)
2. **Check health**: http://localhost:8000/api/v1/health
3. **Visit onboarding**: http://localhost:8000/onboarding/
4. **Test bot**: Go to your bot in Teams and send "hello"

---

# Phase 5: Integration Configuration via Web UI

## Step 1: Open Onboarding Interface

1. **Visit**: http://localhost:8000/onboarding/
2. **Click**: "Get Started"
3. **Configure integrations** using the web forms

## Step 2: Setup Project Mapping

The system can auto-discover project mappings, but for testing:

1. **Create a manual mapping**:
   - Jira Project: Your test project key (e.g., "WEBAPP")
   - Git Repository: Your test repository
   - Confidence: High

## Step 3: Test Integration Connections

1. **Go to**: http://localhost:8000/api/v1/integrations/
2. **Verify**: All your integrations show as "active"
3. **Test**: Use the "Test Connection" buttons

---

# Phase 6: Jira Webhook Configuration

## Step 1: Create Jira Webhook

1. **Go to**: Jira Settings → System → Webhooks
2. **Create webhook**:
   - Name: `Developer Workflow Bot`
   - Status: Enabled
   - URL: `https://your-ngrok-url.ngrok.io/api/v1/tickets/webhook/jira`
   - Events: Check these boxes:
     - ✅ Issue created
     - ✅ Issue updated
   - JQL Filter (optional): `issueType = Bug`

## Step 2: Test Webhook

1. **Create a test bug ticket** in Jira:
   - Issue Type: Bug
   - Title: "Test login validation error"
   - Description: "Users cannot login when password contains special characters"
   - Assign to: A developer

2. **Check application logs** for webhook processing:
```bash
# In your application terminal, you should see:
# INFO: Received Jira webhook: jira:issue_updated
# INFO: Created new ticket: TEST-123
```

3. **Verify database**:
```bash
# Connect to your database and check:
SELECT * FROM tickets ORDER BY created_at DESC LIMIT 1;
```

---

# Phase 7: End-to-End Testing

## Step 1: Create Test Data

**Test Jira Project:**
- Project key: `TEST`
- Issue types: Bug, Story, Task
- Sample bug tickets with realistic descriptions

**Test Git Repository:**
- Create a simple repository with common file types
- Include some intentional bugs for testing
- Add README and documentation

**Test Confluence Space:**
- Create a few documentation pages
- Include troubleshooting guides
- Add some technical documentation

## Step 2: Full Workflow Test

1. **Create bug ticket** in Jira with detailed description
2. **Assign to developer** (someone with Teams access)
3. **Monitor logs** for:
   - Webhook receipt
   - Ticket processing
   - Similarity search
   - Code analysis
   - Teams notification

## Step 3: Verify Teams Integration

1. **Check Teams** for bot notification
2. **Test bot commands**:
   - `help` - Should show available commands
   - `status` - Should show integration status
   - `elaborate TEST-123` - Should provide detailed analysis

---

# Phase 8: Production Deployment (Optional)

## Step 1: Choose Deployment Platform

**Option A: Railway (Recommended for MVP)**
1. Connect GitHub repository
2. Add environment variables
3. Deploy automatically

**Option B: Cloud Provider**
- AWS: ECS or Lambda
- Google Cloud: Cloud Run
- Azure: Container Instances

## Step 2: Production Environment Variables

```bash
# Production settings
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=your-super-secure-production-key

# Use managed database URLs
DATABASE_URL=postgresql://user:pass@production-db:5432/db
REDIS_URL=redis://production-redis:6379/0

# Production webhook endpoints
# Update Jira webhook URL to production domain
# Update Teams bot endpoint to production domain
```

## Step 3: Security Checklist

- [ ] Use HTTPS endpoints only
- [ ] Rotate all API keys
- [ ] Enable webhook signature validation
- [ ] Set up monitoring and logging
- [ ] Configure backup strategy
- [ ] Test disaster recovery

---

# 🚨 Troubleshooting

## Common Issues

### "Database connection failed"
```bash
# Check if PostgreSQL is running
docker-compose ps
# Or for local: pg_isready -h localhost

# Check connection string format
# Should be: postgresql://username:password@host:port/database
```

### "Bot not responding in Teams"
1. **Check ngrok tunnel**: Visit ngrok status at http://localhost:4040
2. **Verify endpoint**: Test POST to `https://your-ngrok-url/api/v1/bot/messages`
3. **Check App ID/Password**: Ensure they match Azure configuration
4. **Review logs**: Look for authentication errors

### "Jira webhook not triggered"
1. **Test webhook URL manually**:
```bash
curl -X POST https://your-ngrok-url/api/v1/tickets/webhook/jira \
  -H "Content-Type: application/json" \
  -d '{"test": "data"}'
```
2. **Check Jira webhook delivery logs**: Jira Settings → Webhooks → View deliveries
3. **Verify JQL filter**: Remove filter temporarily to test
4. **Check ticket labels**: Ensure tickets are labeled as "Bug"

### "Analysis not working"
1. **Check Anthropic API key**: Test at https://console.anthropic.com
2. **Verify project mapping**: Ensure Jira project links to Git repository
3. **Check Celery worker**: Should show "ready" status
4. **Review task logs**: Look for processing errors

### "No similar tickets found"
- **Expected for new systems** - similarity improves with more data
- **Check ticket content** - ensure descriptions are meaningful
- **Verify embeddings** - check if sentence transformers model loaded

## Getting Help

1. **Check logs** in all terminals for error details
2. **Test individual components**:
   - API: http://localhost:8000/docs
   - Health: http://localhost:8000/api/v1/health
   - Bot: http://localhost:8000/api/v1/bot/status
3. **Review configuration** via onboarding UI
4. **File issues** on GitHub repository with logs and configuration details

---

# 🎉 Success Criteria

Your setup is complete when:

- [ ] ✅ Web interface loads at http://localhost:8000/onboarding/
- [ ] ✅ All integrations show "Connected" status
- [ ] ✅ Bot responds to "hello" in Teams
- [ ] ✅ Test Jira ticket triggers webhook processing
- [ ] ✅ Analysis results appear in application logs
- [ ] ✅ Teams notification is sent to assigned developer
- [ ] ✅ Developer can ask for elaboration via Teams bot

**You're now ready to validate your MVP with real developers!** 🚀

**Estimated Cost**: $50-150/month for production deployment
**Next Steps**: Gather feedback, iterate on analysis quality, scale infrastructure as needed.