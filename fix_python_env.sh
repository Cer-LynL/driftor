#!/bin/bash
# Fix Python virtual environment setup

echo "🔧 Fixing Python Virtual Environment..."

# Deactivate current venv if active
if [[ "$VIRTUAL_ENV" != "" ]]; then
    echo "Deactivating current virtual environment..."
    deactivate
fi

# Remove old virtual environment
if [ -d "venv" ]; then
    echo "Removing old virtual environment..."
    rm -rf venv
fi

# Check for Python 3
echo "Checking for Python 3..."
if command -v python3.11 &> /dev/null; then
    PYTHON_CMD="python3.11"
    echo "✅ Found python3.11"
elif command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
    PYTHON_VERSION=$(python3 --version)
    echo "✅ Found python3: $PYTHON_VERSION"
else
    echo "❌ Python 3 not found!"
    echo "Please install Python 3.11+ first:"
    echo "  macOS: brew install python@3.11"
    echo "  Then rerun this script"
    exit 1
fi

# Create new virtual environment with Python 3
echo "Creating new virtual environment with $PYTHON_CMD..."
$PYTHON_CMD -m venv venv

# Activate the new environment
echo "Activating virtual environment..."
source venv/bin/activate

# Verify Python version
VENV_PYTHON_VERSION=$(python --version)
echo "Virtual environment Python version: $VENV_PYTHON_VERSION"

if [[ $VENV_PYTHON_VERSION == *"Python 2"* ]]; then
    echo "❌ Still using Python 2! Please install Python 3.11"
    exit 1
fi

# Upgrade pip
echo "Upgrading pip..."
python -m pip install --upgrade pip

# Install requirements
echo "Installing requirements..."
pip install -r requirements.txt

if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 Virtual environment setup complete!"
    echo ""
    echo "Now run:"
    echo "  source venv/bin/activate"
    echo "  alembic revision --autogenerate -m 'Initial migration'"
    echo "  alembic upgrade head"
else
    echo "❌ Failed to install requirements"
    exit 1
fi