#!/usr/bin/env python3
"""
Test script to verify configuration and imports are working.
"""

def test_imports():
    """Test that all core imports work."""
    try:
        print("Testing imports...")
        
        # Test config
        from app.core.config import settings
        print("Config imported successfully")
        
        # Test database
        from app.core.database import Base
        print("Database imports working")
        
        # Test models
        from app.models.user import User
        from app.models.integration import Integration
        from app.models.ticket import Ticket
        from app.models.project_mapping import ProjectMapping
        print("Models imported successfully")
        
        # Test schemas
        from app.schemas.user import User as UserSchema
        from app.schemas.integration import Integration as IntegrationSchema
        print("Schemas imported successfully")
        
        print("\nAll imports successful!")
        return True
        
    except Exception as e:
        print(f"Import error: {e}")
        return False

def test_config():
    """Test configuration loading."""
    try:
        from app.core.config import settings
        print(f"Project Name: {settings.PROJECT_NAME}")
        print(f"Environment: {settings.ENVIRONMENT}")
        print(f"Debug: {settings.DEBUG}")
        print(f"Database URL configured: {bool(settings.DATABASE_URL)}")
        return True
    except Exception as e:
        print(f"Config error: {e}")
        return False

if __name__ == "__main__":
    print("Testing Developer Workflow Bot Configuration\n")
    
    if test_imports() and test_config():
        print("\nAll tests passed! Ready to run Alembic.")
    else:
        print("\nTests failed. Check the errors above.")