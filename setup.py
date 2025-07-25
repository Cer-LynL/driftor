"""
Setup script for Developer Workflow Bot.
"""
import os
import sys
from pathlib import Path


def create_env_file():
    """Create .env file from template if it doesn't exist."""
    env_file = Path('.env')
    env_example = Path('.env.example')
    
    if not env_file.exists() and env_example.exists():
        print("Creating .env file from template...")
        env_file.write_text(env_example.read_text())
        print("✅ .env file created. Please edit it with your configuration.")
        return True
    elif env_file.exists():
        print("✅ .env file already exists.")
        return True
    else:
        print("❌ .env.example not found. Cannot create .env file.")
        return False


def check_python_version():
    """Check if Python version is compatible."""
    if sys.version_info < (3, 11):
        print("❌ Python 3.11+ is required.")
        return False
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detected.")
    return True


def install_dependencies():
    """Install Python dependencies."""
    print("Installing Python dependencies...")
    os.system("pip install -r requirements.txt")
    print("✅ Dependencies installed.")


def setup_database():
    """Set up database with Alembic."""
    print("Setting up database...")
    
    # Generate initial migration if needed
    if not Path('alembic/versions').exists():
        Path('alembic/versions').mkdir(parents=True, exist_ok=True)
    
    # Check if any migrations exist
    version_files = list(Path('alembic/versions').glob('*.py'))
    if not version_files:
        print("Generating initial database migration...")
        os.system("alembic revision --autogenerate -m 'Initial migration'")
    
    # Run migrations
    print("Running database migrations...")
    os.system("alembic upgrade head")
    print("✅ Database setup complete.")


def create_directories():
    """Create necessary directories."""
    directories = [
        'logs',
        'uploads',
        'temp'
    ]
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"✅ Created directory: {directory}")


def print_next_steps():
    """Print next steps for the user."""
    print("\n" + "="*50)
    print("🎉 SETUP COMPLETE!")
    print("="*50)
    print("\nNext Steps:")
    print("1. Edit .env file with your API keys and configuration")
    print("2. Start the services:")
    print("   • API Server: uvicorn app.main:app --reload")
    print("   • Worker: celery -A app.tasks worker --loglevel=info")
    print("   • Database: docker-compose up -d postgres redis qdrant")
    print("\n3. Test the API at: http://localhost:8000/docs")
    print("4. Configure Jira webhook: http://localhost:8000/api/v1/tickets/webhook/jira")
    print("5. Set up Teams bot endpoint: http://localhost:8000/api/v1/bot/messages")
    print("\nFor detailed instructions, see README.md")


def main():
    """Main setup function."""
    print("🤖 Developer Workflow Bot Setup")
    print("=" * 40)
    
    success = True
    
    # Check Python version
    if not check_python_version():
        success = False
    
    # Create .env file
    if success and not create_env_file():
        success = False
    
    if success:
        # Install dependencies
        install_dependencies()
        
        # Create directories
        create_directories()
        
        # Set up database (only if DATABASE_URL is configured)
        try:
            from app.core.config import settings
            if settings.DATABASE_URL:
                setup_database()
            else:
                print("⚠️  DATABASE_URL not configured, skipping database setup")
        except Exception as e:
            print(f"⚠️  Could not set up database: {e}")
        
        # Print next steps
        print_next_steps()
    else:
        print("\n❌ Setup failed. Please fix the issues above and try again.")


if __name__ == "__main__":
    main()