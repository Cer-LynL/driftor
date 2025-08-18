#!/usr/bin/env python3
"""
Create test data for local Driftor testing.
"""
import asyncio
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from driftor.core.database import get_db
from driftor.models.tenant import Tenant, User, UserRole
from driftor.security.encryption import get_encryption_manager
from driftor.integrations.vector_db.factory import get_vector_db_service
from sqlalchemy.orm import Session


async def create_test_tenant() -> str:
    """Create a test tenant with sample data."""
    print("Creating test tenant...")
    
    # Get database session
    db = next(get_db())
    
    try:
        # Create test tenant
        tenant = Tenant(
            name="Test Company",
            slug="test-tenant",
            subscription_tier="enterprise",
            is_active=True,
            settings={
                "max_users": 100,
                "max_repositories": 10,
                "features": [
                    "ai_analysis",
                    "vector_search", 
                    "multi_git_support",
                    "advanced_analytics"
                ]
            }
        )
        
        db.add(tenant)
        db.commit()
        db.refresh(tenant)
        
        print(f"✅ Created tenant: {tenant.name} (ID: {tenant.id})")
        
        # Create test users
        await create_test_users(db, tenant.id)
        
        # Create sample tickets in vector database
        await create_sample_tickets(tenant.id)
        
        # Create sample documentation
        await create_sample_documentation(tenant.id)
        
        return tenant.id
        
    except Exception as e:
        print(f"❌ Error creating tenant: {e}")
        db.rollback()
        raise
    finally:
        db.close()


async def create_test_users(db: Session, tenant_id: str):
    """Create test users for the tenant."""
    print("Creating test users...")
    
    test_users = [
        {
            "email": "admin@testcompany.com",
            "username": "admin",
            "full_name": "Test Admin",
            "role": UserRole.ADMIN,
            "is_active": True
        },
        {
            "email": "developer@testcompany.com", 
            "username": "developer",
            "full_name": "Test Developer",
            "role": UserRole.USER,
            "is_active": True
        },
        {
            "email": "manager@testcompany.com",
            "username": "manager", 
            "full_name": "Test Manager",
            "role": UserRole.MANAGER,
            "is_active": True
        }
    ]
    
    for user_data in test_users:
        # Hash password (for testing, use simple password)
        password_hash = get_encryption_manager().hash_password("testpassword123")
        
        user = User(
            tenant_id=tenant_id,
            email=user_data["email"],
            username=user_data["username"],
            full_name=user_data["full_name"],
            password_hash=password_hash,
            role=user_data["role"],
            is_active=user_data["is_active"],
            preferences={
                "notifications": True,
                "theme": "light",
                "language": "en"
            }
        )
        
        db.add(user)
        print(f"  ✅ Created user: {user.email}")
    
    db.commit()


async def create_sample_tickets(tenant_id: str):
    """Create sample tickets in vector database."""
    print("Creating sample tickets in vector database...")
    
    vector_service = get_vector_db_service()
    
    sample_tickets = [
        {
            "key": "PROJ-001",
            "summary": "Null pointer exception in user authentication",
            "description": "Getting NullPointerException when user tries to login. The error occurs in AuthService.validateUser() method when accessing user.getProfile(). Stack trace shows the issue is on line 67 of AuthService.java.",
            "issue_type": "Bug",
            "priority": "High",
            "component": "backend",
            "assignee": {"displayName": "John Developer"},
            "created": "2024-01-10T09:00:00Z",
            "labels": ["authentication", "critical"]
        },
        {
            "key": "PROJ-002", 
            "summary": "API timeout in payment processing",
            "description": "Payment API calls are timing out after 30 seconds. Users report failed transactions even though payments are processed successfully. The issue seems to be in PaymentGateway.processPayment() method.",
            "issue_type": "Bug",
            "priority": "Critical",
            "component": "backend",
            "assignee": {"displayName": "Jane Smith"},
            "created": "2024-01-12T14:30:00Z",
            "labels": ["payment", "timeout", "api"]
        },
        {
            "key": "PROJ-003",
            "summary": "Frontend validation not working for email field",
            "description": "Email validation on the registration form is not working properly. Users can submit forms with invalid email addresses. The validation should happen both client-side and server-side.",
            "issue_type": "Bug", 
            "priority": "Medium",
            "component": "frontend",
            "assignee": {"displayName": "Alice Frontend"},
            "created": "2024-01-14T11:15:00Z",
            "labels": ["validation", "frontend", "email"]
        },
        {
            "key": "PROJ-004",
            "summary": "Database connection pool exhausted",
            "description": "Application is running out of database connections during peak hours. Connection pool size is set to 20 but we're seeing 'connection pool exhausted' errors. Need to investigate connection leaks.",
            "issue_type": "Bug",
            "priority": "High", 
            "component": "database",
            "assignee": {"displayName": "Bob Backend"},
            "created": "2024-01-15T16:45:00Z",
            "labels": ["database", "connection-pool", "performance"]
        },
        {
            "key": "PROJ-005",
            "summary": "Memory leak in image processing service",
            "description": "Image processing service shows increasing memory usage over time. After processing multiple images, the service eventually crashes with OutOfMemoryError. Suspect there's a memory leak in ImageProcessor.resizeImage() method.",
            "issue_type": "Bug",
            "priority": "High",
            "component": "backend",
            "assignee": {"displayName": "Carol Developer"},
            "created": "2024-01-16T08:20:00Z",
            "labels": ["memory-leak", "image-processing", "performance"]
        }
    ]
    
    # Index tickets in vector database
    for ticket in sample_tickets:
        # Create mock classification
        classification = {
            "is_bug": True,
            "severity": ticket["priority"].lower(),
            "component": ticket["component"],
            "keywords": ticket["labels"] + ["exception", "error", "bug"],
            "confidence": 0.9
        }
        
        success = await vector_service.index_ticket(ticket, classification, tenant_id)
        if success:
            print(f"  ✅ Indexed ticket: {ticket['key']}")
        else:
            print(f"  ❌ Failed to index ticket: {ticket['key']}")


async def create_sample_documentation(tenant_id: str):
    """Create sample documentation in vector database."""
    print("Creating sample documentation in vector database...")
    
    vector_service = get_vector_db_service()
    
    sample_docs = [
        {
            "title": "Authentication Service Troubleshooting Guide",
            "content": "This guide covers common authentication issues including null pointer exceptions, token validation failures, and user session problems. For null pointer exceptions in AuthService, check that user profiles are properly loaded before accessing user.getProfile().",
            "url": "https://docs.company.com/auth-troubleshooting",
            "source": "confluence",
            "doc_type": "troubleshooting",
            "author": "Tech Team",
            "last_modified": "2024-01-10T10:00:00Z"
        },
        {
            "title": "Payment API Integration Guide", 
            "content": "Complete guide for integrating with payment APIs. Covers timeout handling, retry logic, and error handling. Set timeouts to 60 seconds for payment operations and implement exponential backoff for retries.",
            "url": "https://docs.company.com/payment-api",
            "source": "confluence",
            "doc_type": "api_documentation",
            "author": "Payment Team",
            "last_modified": "2024-01-11T15:30:00Z"
        },
        {
            "title": "Frontend Validation Best Practices",
            "content": "Best practices for client-side and server-side validation. Always validate on both client and server side. Use HTML5 validation attributes and JavaScript for client-side validation, and server-side validation for security.",
            "url": "https://docs.company.com/validation-practices",
            "source": "knowledge_base",
            "doc_type": "best_practices",
            "author": "Frontend Team", 
            "last_modified": "2024-01-12T09:20:00Z"
        },
        {
            "title": "Database Connection Pool Configuration",
            "content": "Guide for configuring database connection pools. Recommended pool size is 20-50 connections depending on load. Monitor pool utilization and set appropriate timeouts. Always close connections in finally blocks.",
            "url": "https://docs.company.com/db-connection-pool",
            "source": "confluence",
            "doc_type": "setup_guide",
            "author": "DBA Team",
            "last_modified": "2024-01-13T14:10:00Z"
        },
        {
            "title": "Memory Management in Java Applications",
            "content": "Best practices for memory management in Java applications. Use try-with-resources for automatic resource management. Monitor heap usage with JVM flags. For image processing, ensure InputStreams and BufferedImages are properly disposed.",
            "url": "https://docs.company.com/memory-management",
            "source": "knowledge_base",
            "doc_type": "best_practices",
            "author": "Java Team",
            "last_modified": "2024-01-14T11:45:00Z"
        }
    ]
    
    success = await vector_service.index_documentation(sample_docs, tenant_id)
    if success:
        print(f"  ✅ Indexed {len(sample_docs)} documentation articles")
    else:
        print("  ❌ Failed to index documentation")


async def create_auth_tokens(tenant_id: str):
    """Create test authentication tokens."""
    print("Creating test authentication tokens...")
    
    from driftor.core.auth import create_access_token
    
    # Create tokens for test users
    test_tokens = {
        "admin": create_access_token(
            data={"sub": "admin@testcompany.com", "tenant_id": tenant_id, "role": "admin"}
        ),
        "developer": create_access_token(
            data={"sub": "developer@testcompany.com", "tenant_id": tenant_id, "role": "user"}
        ),
        "manager": create_access_token(
            data={"sub": "manager@testcompany.com", "tenant_id": tenant_id, "role": "manager"}
        )
    }
    
    # Save tokens to file for testing
    with open("test_tokens.txt", "w") as f:
        f.write("# Test Authentication Tokens\n")
        f.write("# Use these tokens in Authorization: Bearer <token> headers\n\n")
        for role, token in test_tokens.items():
            f.write(f"{role.upper()}_TOKEN={token}\n")
    
    print("  ✅ Created test tokens (saved to test_tokens.txt)")


async def main():
    """Main setup function."""
    print("🚀 Setting up Driftor test environment...")
    print()
    
    try:
        # Create test tenant and users
        tenant_id = await create_test_tenant()
        
        # Create authentication tokens
        await create_auth_tokens(tenant_id)
        
        print()
        print("✅ Test environment setup complete!")
        print()
        print("📋 Summary:")
        print(f"   Tenant ID: {tenant_id}")
        print("   Users created: admin, developer, manager")
        print("   Sample tickets: 5 indexed in vector database")
        print("   Sample docs: 5 indexed in vector database")
        print("   Auth tokens: saved to test_tokens.txt")
        print()
        print("🧪 Ready for testing! Use the tokens from test_tokens.txt for API calls.")
        print("   Example:")
        print("   curl -H 'Authorization: Bearer <ADMIN_TOKEN>' http://localhost:8000/api/v1/health")
        
    except Exception as e:
        print(f"❌ Setup failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)