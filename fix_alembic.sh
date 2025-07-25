#!/bin/bash
# Fix Alembic migration setup

echo "🔧 Fixing Alembic setup..."

# Check if virtual environment is activated
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "❌ Virtual environment not activated!"
    echo "Please run: source venv/bin/activate"
    exit 1
fi

echo "✅ Virtual environment is active: $VIRTUAL_ENV"

# Check Python version
PYTHON_VERSION=$(python --version 2>&1)
echo "Python version: $PYTHON_VERSION"

# Test imports
echo "Testing imports..."
python -c "
try:
    from app.core.config import settings
    print('✅ Configuration imported successfully')
    print('Project:', settings.PROJECT_NAME)
    print('Environment:', settings.ENVIRONMENT)
except Exception as e:
    print('❌ Configuration import failed:', e)
    exit(1)

try:
    from app.core.database import Base
    print('✅ Database Base imported successfully')
except Exception as e:
    print('❌ Database import failed:', e)
    exit(1)

try:
    from app.models import user, integration, ticket, project_mapping
    print('✅ All models imported successfully')
except Exception as e:
    print('❌ Models import failed:', e)
    exit(1)
"

if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 All imports working! Generating migration..."
    alembic revision --autogenerate -m "Initial migration"
    
    if [ $? -eq 0 ]; then
        echo "✅ Migration generated successfully!"
        echo ""
        echo "Now run: alembic upgrade head"
    else
        echo "❌ Migration generation failed"
    fi
else
    echo "❌ Import tests failed. Please check the errors above."
fi