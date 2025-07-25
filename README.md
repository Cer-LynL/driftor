# Developer Workflow Bot

An automated bot that analyzes Jira tickets, finds similar issues, locates relevant documentation, and suggests code fixes through Microsoft Teams integration.

## Features

- **MS Teams Integration**: Receive notifications and interact through Teams
- **Jira Webhook Processing**: Automatic ticket assignment detection
- **Smart Analysis**: Similar ticket detection and documentation lookup
- **Code Analysis**: Integrated with Claude Code API for fix suggestions
- **Project Mapping**: Automated Jira project to Git repository mapping

## Architecture

```
MS Teams ←→ Bot Framework ←→ FastAPI Backend
                                    ↓
                            Webhook Processors
                                    ↓
                        [Jira] [Confluence] [Git APIs]
                                    ↓
                            Analysis Pipeline
                                    ↓
                        [Vector Search] [Claude API]
                                    ↓
                            Response Generator
```

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL
- Redis
- Microsoft Azure App Registration (for Teams bot)
- API tokens for Jira, Confluence, GitHub
- Anthropic API key

### Local Development

1. **Clone and setup environment**:
```bash
git clone <repository-url>
cd developer-workflow-bot
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. **Configure environment**:
```bash
cp .env.example .env
# Edit .env with your API keys and database URL
```

3. **Start services with Docker**:
```bash
docker-compose up -d postgres redis qdrant
```

4. **Initialize database**:
```bash
alembic upgrade head
```

5. **Start the application**:
```bash
# API server
uvicorn app.main:app --reload --port 8000

# Background worker (separate terminal)
celery -A app.tasks worker --loglevel=info

# For webhook testing
ngrok http 8000
```

### Docker Deployment

```bash
docker-compose up -d
```

## Configuration

### Microsoft Bot Framework Setup

1. Create Azure App Registration
2. Generate App ID and Secret
3. Configure bot endpoint: `https://your-domain.com/api/v1/bot/messages`
4. Add to Teams App Studio

### Jira Integration

1. Create API token in Jira
2. Set up webhook: `https://your-domain.com/api/v1/tickets/webhook/jira`
3. Configure for "Issue Assigned" events

### API Endpoints

- `GET /api/v1/health` - Health check
- `POST /api/v1/bot/messages` - Teams bot messages
- `POST /api/v1/tickets/webhook/jira` - Jira webhook
- `GET /api/v1/auth/oauth/{service}` - OAuth flows
- `GET /api/v1/admin/project-mappings` - Project mappings

## Development

### Project Structure

```
app/
├── api/v1/endpoints/     # API endpoints
├── core/                 # Configuration and database
├── models/               # SQLAlchemy models
├── schemas/              # Pydantic schemas
├── services/             # Business logic
│   ├── auth/            # Authentication services
│   ├── bot/             # Teams bot services
│   ├── integrations/    # External API clients
│   └── analysis/        # Ticket analysis pipeline
└── tasks/               # Background tasks
```

### Adding New Features

1. Create database model in `app/models/`
2. Add Pydantic schema in `app/schemas/`
3. Implement service logic in `app/services/`
4. Create API endpoint in `app/api/v1/endpoints/`
5. Add tests in `tests/`

## Testing

```bash
# Run tests
pytest

# With coverage
pytest --cov=app

# Specific test file
pytest tests/test_bot.py
```

## Deployment

### Production Environment

1. **Environment Variables**:
   - Set `ENVIRONMENT=production`
   - Use strong `SECRET_KEY`
   - Configure production database URL
   - Set proper `ALLOWED_HOSTS`

2. **Database Migration**:
```bash
alembic upgrade head
```

3. **Deploy Options**:
   - Railway: Connect GitHub repo, auto-deploy
   - Render: Web service + background worker
   - Docker: Use provided Dockerfile

### Monitoring

- Health checks: `/api/v1/health`
- Bot status: `/api/v1/bot/status`
- Admin dashboard: `/api/v1/admin/system/health`

## Contributing

1. Fork the repository
2. Create feature branch
3. Make changes with tests
4. Submit pull request

## License

MIT License - see LICENSE file for details