# Installation Troubleshooting Guide

## 🔧 Dependency Conflicts Resolution

### Problem: aiohttp Version Conflicts
```
ERROR: Cannot install -r requirements.txt (line 19) and aiohttp==3.9.1 because these package versions have conflicting dependencies.
```

### Solution Options:

#### Option 1: Use Fixed Requirements (Recommended)
```bash
# Clean install with fixed versions
pip uninstall -y -r requirements.txt
pip install -r requirements.txt
```

#### Option 2: Use Flexible Requirements
```bash
# If you want more flexibility with versions
pip install -r requirements-flexible.txt
```

#### Option 3: Manual Resolution
```bash
# Install botbuilder first, then other packages
pip install botbuilder-core==4.15.0 botbuilder-schema==4.15.0 botbuilder-integration-aiohttp==4.15.0
pip install fastapi uvicorn sqlalchemy alembic
pip install anthropic sentence-transformers
# Continue with remaining packages...
```

## 🐍 Python Version Issues

### Problem: Python Version Too Old
```
ERROR: This package requires Python >=3.11
```

### Solution:
```bash
# Check current version
python --version

# Install Python 3.11+
# Windows: Download from python.org
# macOS: brew install python@3.11
# Ubuntu: sudo apt install python3.11 python3.11-venv

# Create new venv with correct Python
python3.11 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

## 🔐 Permission Issues

### Problem: Permission Denied on Windows
```
ERROR: Could not install packages due to an EnvironmentError: [WinError 5] Access is denied
```

### Solution:
```bash
# Option 1: Run as Administrator
# Right-click Command Prompt → "Run as administrator"

# Option 2: Install for user only
pip install --user -r requirements.txt

# Option 3: Use virtual environment (recommended)
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## 💾 Disk Space Issues

### Problem: No Space Left
```
ERROR: Could not install packages due to disk space
```

### Solution:
```bash
# Clean pip cache
pip cache purge

# Check space
df -h  # Linux/macOS
dir C:\  # Windows

# Install without cache
pip install --no-cache-dir -r requirements.txt
```

## 🌐 Network/Proxy Issues

### Problem: SSL Certificate Errors
```
WARNING: Retrying (Retry(total=4, backoff_factor=0.5)) after connection broken
```

### Solution:
```bash
# Upgrade certificates
pip install --upgrade certifi

# Use trusted hosts (temporary)
pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org -r requirements.txt

# Configure corporate proxy
pip install --proxy http://user:password@proxy.server:port -r requirements.txt
```

## 🔨 Compilation Issues

### Problem: Microsoft Visual C++ Build Tools Missing (Windows)
```
ERROR: Microsoft Visual C++ 14.0 is required
```

### Solution:
```bash
# Option 1: Install Visual Studio Build Tools
# Download from: https://visualstudio.microsoft.com/visual-cpp-build-tools/

# Option 2: Use pre-compiled wheels
pip install --only-binary=all -r requirements.txt

# Option 3: Install specific problematic packages first
pip install --only-binary=psycopg2-binary psycopg2-binary
```

## 🐧 Linux Specific Issues

### Problem: Missing System Dependencies
```
ERROR: Package 'libpq-dev' is not installed
```

### Solution:
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3-dev libpq-dev build-essential

# CentOS/RHEL
sudo yum install python3-devel postgresql-devel gcc

# Alpine Linux
apk add python3-dev postgresql-dev build-base
```

## 🍎 macOS Specific Issues

### Problem: Command Line Tools Missing
```
xcrun: error: invalid active developer path
```

### Solution:
```bash
# Install Xcode command line tools
xcode-select --install

# If using Homebrew
brew install python@3.11 postgresql
```

## 🔄 Clean Installation Process

If you're still having issues, try a completely clean installation:

```bash
# 1. Remove existing virtual environment
rm -rf venv  # Linux/macOS
rmdir /s venv  # Windows

# 2. Clear pip cache
pip cache purge

# 3. Create fresh virtual environment
python3.11 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 4. Upgrade pip and setuptools
python -m pip install --upgrade pip setuptools wheel

# 5. Install dependencies in order
pip install pydantic fastapi uvicorn
pip install sqlalchemy alembic psycopg2-binary
pip install botbuilder-core botbuilder-schema botbuilder-integration-aiohttp
pip install anthropic sentence-transformers
pip install redis celery
pip install python-dotenv jinja2
pip install pytest black flake8

# 6. Verify installation
python -c "import fastapi, sqlalchemy, anthropic; print('✅ Key packages installed')"
```

## 📦 Alternative Installation Methods

### Using Conda (Alternative to pip)
```bash
# Install conda/miniconda first
conda create -n developer-bot python=3.11
conda activate developer-bot

# Install conda packages where available
conda install fastapi uvicorn sqlalchemy redis numpy
pip install -r requirements.txt  # For remaining packages
```

### Using Poetry (Alternative Dependency Manager)
```bash
# Install poetry
pip install poetry

# Convert requirements.txt to pyproject.toml
poetry add $(cat requirements.txt | grep -v "^#" | tr '\n' ' ')

# Install
poetry install
poetry shell
```

## 🔍 Debugging Installation Issues

### Check What's Installed
```bash
pip list
pip show package-name  # Check specific package details
```

### Check Dependencies
```bash
pip check  # Find dependency conflicts
pipdeptree  # Visualize dependency tree (install with: pip install pipdeptree)
```

### Verbose Installation
```bash
pip install -v -r requirements.txt  # Verbose output
pip install --dry-run --report report.json -r requirements.txt  # See what would be installed
```

## 🆘 Still Having Issues?

### Create Minimal Environment
```bash
# Test with minimal requirements first
echo "fastapi==0.104.1" > minimal-requirements.txt
echo "uvicorn==0.24.0" >> minimal-requirements.txt
echo "anthropic==0.7.8" >> minimal-requirements.txt

pip install -r minimal-requirements.txt
python -c "from fastapi import FastAPI; print('FastAPI works!')"
```

### Report Environment
```bash
# Gather system information
python --version
pip --version
pip list
uname -a  # Linux/macOS
systeminfo  # Windows

# Check virtual environment
echo $VIRTUAL_ENV  # Should show path to your venv
```

### Common Working Configurations

**Ubuntu 22.04:**
```bash
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-dev
sudo apt install libpq-dev build-essential
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

**macOS with Homebrew:**
```bash
brew install python@3.11 postgresql
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

**Windows 11:**
```bash
# Install Python 3.11 from python.org
# Install Git for Windows
python -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

## 📞 Getting Help

If none of these solutions work:

1. **Check the GitHub Issues** for similar problems
2. **Create a new issue** with:
   - Your operating system and version
   - Python version (`python --version`)
   - Complete error message
   - Output of `pip list`
   - Steps you've already tried

3. **Include environment details**:
   ```bash
   python -m pip debug --verbose
   ```

The most common issue is the aiohttp version conflict, which should be resolved with the updated requirements.txt file above.