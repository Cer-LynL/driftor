# Developer Workflow Bot - Quick Start Guide

## 🚀 Getting Started in 5 Minutes

### Prerequisites
- Python 3.11+ 
- Git
- PostgreSQL (or Docker)
- Microsoft Azure account (for Teams bot)
- Jira instance with admin access
- GitHub/GitLab account with repository access
- Anthropic API key

### 1. Setup Environment

```bash
# Clone repository
git clone <your-repo-url>
cd developer-workflow-bot

# Run setup script
python setup.py

# Or manual setup:
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

### 2. Configure Environment Variables

Edit `.env` file with your settings:

```bash
# Required
SECRET_KEY=your-secret-key-here
DATABASE_URL=postgresql://user:password@localhost:5432/developer_workflow_bot
ANTHROPIC_API_KEY=your-anthropic-api-key

# Microsoft Bot Framework (create at portal.azure.com)
MICROSOFT_APP_ID=your-app-id
MICROSOFT_APP_PASSWORD=your-app-password
MICROSOFT_BOT_ID=your-bot-id

# Optional - can be configured via web UI
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_USERNAME=your-email@example.com
JIRA_API_TOKEN=your-jira-api-token

GITHUB_TOKEN=your-github-token
```

### 3. Start Services

**Option A: Docker (Recommended)**
```bash
docker-compose up -d
```

**Option B: Local Services**
```bash
# Terminal 1: Database & Redis
docker-compose up -d postgres redis qdrant

# Terminal 2: API Server
uvicorn app.main:app --reload --port 8000

# Terminal 3: Background Worker  
celery -A app.tasks worker --loglevel=info

# Terminal 4: For webhook testing
ngrok http 8000
```

### 4. Initial Setup

1. **Visit onboarding page**: http://localhost:8000/onboarding/
2. **Connect integrations**: Follow the setup wizard
3. **Configure webhooks**:
   - Jira: Add webhook URL: `http://your-domain.com/api/v1/tickets/webhook/jira`
   - Events: Issue assigned, Issue updated
4. **Setup Teams bot**: Add message endpoint: `http://your-domain.com/api/v1/bot/messages`

### 5. Test the System

1. **Create a test bug ticket** in Jira
2. **Assign it to a developer**
3. **Check the logs** for processing
4. **Verify Teams notification** (if configured)

### 6. API Documentation

- **Interactive docs**: http://localhost:8000/docs
- **Health check**: http://localhost:8000/api/v1/health
- **Bot status**: http://localhost:8000/api/v1/bot/status

## 🔧 Configuration Details

### Microsoft Teams Bot Setup

1. Go to [Azure Portal](https://portal.azure.com)
2. Create new "Bot Channels Registration"
3. Note down App ID and generate App Secret
4. Set messaging endpoint: `https://your-domain.com/api/v1/bot/messages`
5. Enable Teams channel

### Jira Webhook Configuration

1. Go to Jira Settings → System → Webhooks
2. Create new webhook:
   - **URL**: `https://your-domain.com/api/v1/tickets/webhook/jira`
   - **Events**: Issue created, Issue updated
   - **JQL Filter**: `issueType = Bug` (optional)

### GitHub Integration

1. Create Personal Access Token with `repo` permissions
2. Add to environment variables or configure via web UI

## 🐛 Troubleshooting

### Common Issues

**Database connection failed**
```bash
# Check if PostgreSQL is running
docker-compose ps
# Or check local PostgreSQL
pg_isready -h localhost
```

**Bot not responding**
- Verify Microsoft App ID/Password are correct
- Check ngrok is forwarding to correct port
- Ensure webhook endpoint is accessible publicly

**Jira webhook not triggering**
- Test webhook URL manually: `curl -X POST http://localhost:8000/api/v1/tickets/webhook/jira`
- Check Jira webhook delivery logs
- Verify JQL filter (if any) matches your test tickets

**Analysis not working**
- Check Anthropic API key is valid
- Verify project mapping exists for your Jira project
- Check Celery worker is running and processing tasks

### Logs and Debugging

```bash
# Check application logs
docker-compose logs app

# Check worker logs  
docker-compose logs worker

# Check specific service
docker-compose logs postgres
```

## 📋 Production Deployment

### Environment Setup
- Use strong SECRET_KEY
- Set ENVIRONMENT=production
- Configure proper DATABASE_URL (managed PostgreSQL)
- Use Redis cluster for high availability
- Set up proper logging and monitoring

### Deployment Options

**Railway** (Recommended for MVP)
1. Connect GitHub repository
2. Add environment variables
3. Deploy automatically

**Docker + Cloud Provider**
```bash
# Build image
docker build -t developer-workflow-bot .

# Deploy to your cloud provider
# (AWS ECS, Google Cloud Run, Azure Container Instances)
```

### Security Considerations
- Use HTTPS endpoints only
- Validate webhook signatures
- Encrypt API tokens in database
- Use OAuth for user authentication
- Implement rate limiting

## 🚀 Next Steps

1. **Test with real tickets**: Create bug tickets and verify analysis quality
2. **Train the system**: More usage improves similarity matching
3. **Add more integrations**: GitLab, Azure DevOps, etc.
4. **Customize analysis**: Adjust confidence thresholds
5. **Scale infrastructure**: Add more workers for high volume

## 📞 Support

- Check logs for error details
- Review API documentation at `/docs`
- File issues on GitHub repository
- Check configuration in onboarding UI

---

**Ready to automate your development workflow!** 🤖✨