#!/usr/bin/env python3
"""
Test Driftor API endpoints end-to-end.
"""
import asyncio
import aiohttp
import json
import sys
import os
from typing import Dict, Any

# Configuration
API_BASE_URL = "http://localhost:8000"
TENANT_ID = "test-tenant"

# Load test tokens
def load_test_tokens() -> Dict[str, str]:
    """Load authentication tokens from file."""
    tokens = {}
    try:
        with open("test_tokens.txt", "r") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    key, value = line.strip().split("=", 1)
                    tokens[key] = value
        return tokens
    except FileNotFoundError:
        print("❌ test_tokens.txt not found. Run create_test_data.py first.")
        return {}


async def test_health_check(session: aiohttp.ClientSession) -> bool:
    """Test basic health check."""
    print("🔍 Testing health check...")
    
    try:
        async with session.get(f"{API_BASE_URL}/health") as response:
            if response.status == 200:
                data = await response.json()
                print(f"  ✅ Health check passed: {data.get('status')}")
                return True
            else:
                print(f"  ❌ Health check failed: {response.status}")
                return False
    except Exception as e:
        print(f"  ❌ Health check error: {e}")
        return False


async def test_ticket_analysis(session: aiohttp.ClientSession, token: str) -> bool:
    """Test ticket analysis endpoint."""
    print("🎫 Testing ticket analysis...")
    
    test_ticket = {
        "ticket_data": {
            "key": "API-TEST-001",
            "summary": "Database connection timeout during user registration",
            "description": "Users are experiencing timeouts when trying to register. The error occurs in UserRegistrationService.createUser() method when saving to database. Stack trace shows SQLException: connection timeout after 30 seconds.",
            "issue_type": "Bug",
            "priority": "High",
            "component": "backend",
            "assignee": {"displayName": "Test Developer"},
            "created": "2024-01-20T10:00:00Z",
            "labels": ["database", "timeout", "registration"]
        },
        "tenant_id": TENANT_ID
    }
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        async with session.post(
            f"{API_BASE_URL}/api/v1/tickets/analyze",
            json=test_ticket,
            headers=headers
        ) as response:
            if response.status == 200:
                data = await response.json()
                print(f"  ✅ Ticket analysis completed")
                print(f"     Classification: {data.get('classification', {}).get('component', 'N/A')}")
                print(f"     Confidence: {data.get('classification', {}).get('confidence', 'N/A')}")
                print(f"     Similar tickets: {len(data.get('similar_tickets', []))}")
                print(f"     Documentation: {len(data.get('documentation', []))}")
                return True
            else:
                error = await response.text()
                print(f"  ❌ Ticket analysis failed: {response.status} - {error}")
                return False
    except Exception as e:
        print(f"  ❌ Ticket analysis error: {e}")
        return False


async def test_vector_search(session: aiohttp.ClientSession, token: str) -> bool:
    """Test vector database search."""
    print("🔍 Testing vector search...")
    
    search_request = {
        "collection": f"tickets_{TENANT_ID}",
        "query": "null pointer exception authentication",
        "n_results": 3
    }
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        async with session.post(
            f"{API_BASE_URL}/api/v1/vector/search",
            json=search_request,
            headers=headers
        ) as response:
            if response.status == 200:
                data = await response.json()
                results = data.get("results", [])
                print(f"  ✅ Vector search completed: {len(results)} results")
                for i, result in enumerate(results[:2]):
                    score = result.get("score", 0)
                    metadata = result.get("metadata", {})
                    ticket_key = metadata.get("ticket_key", "N/A")
                    print(f"     {i+1}. {ticket_key} (score: {score:.3f})")
                return True
            else:
                error = await response.text()
                print(f"  ❌ Vector search failed: {response.status} - {error}")
                return False
    except Exception as e:
        print(f"  ❌ Vector search error: {e}")
        return False


async def test_llm_analysis(session: aiohttp.ClientSession, token: str) -> bool:
    """Test LLM analysis endpoint."""
    print("🤖 Testing LLM analysis...")
    
    llm_request = {
        "prompt_type": "code_analysis",
        "context": {
            "ticket_key": "API-TEST-001",
            "summary": "Database connection timeout",
            "description": "Connection timeout in user registration service",
            "component": "backend",
            "code_files": "UserRegistrationService.java: public void createUser(User user) { database.save(user); }",
            "similar_tickets": "PROJ-004: Database connection pool exhausted"
        },
        "tenant_id": TENANT_ID
    }
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        async with session.post(
            f"{API_BASE_URL}/api/v1/llm/analyze",
            json=llm_request,
            headers=headers
        ) as response:
            if response.status == 200:
                data = await response.json()
                print(f"  ✅ LLM analysis completed")
                print(f"     Provider: {data.get('provider', 'N/A')}")
                print(f"     Model: {data.get('model', 'N/A')}")
                print(f"     Confidence: {data.get('confidence', 'N/A')}")
                print(f"     Content length: {len(data.get('content', ''))}")
                return True
            else:
                error = await response.text()
                print(f"  ❌ LLM analysis failed: {response.status} - {error}")
                return False
    except Exception as e:
        print(f"  ❌ LLM analysis error: {e}")
        return False


async def test_chat_session(session: aiohttp.ClientSession, token: str) -> bool:
    """Test chat functionality."""
    print("💬 Testing chat session...")
    
    # Create chat session
    session_request = {
        "user_id": "test-developer",
        "tenant_id": TENANT_ID,
        "ticket_context": "API-TEST-001"
    }
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        # Create session
        async with session.post(
            f"{API_BASE_URL}/api/v1/chat/sessions",
            json=session_request,
            headers=headers
        ) as response:
            if response.status == 200:
                session_data = await response.json()
                session_id = session_data.get("session_id")
                print(f"  ✅ Chat session created: {session_id}")
                
                # Send chat message
                message_request = {
                    "message": "What could be causing the database timeout issue in the user registration service?",
                    "user_id": "test-developer"
                }
                
                async with session.post(
                    f"{API_BASE_URL}/api/v1/chat/sessions/{session_id}/messages",
                    json=message_request,
                    headers=headers
                ) as msg_response:
                    if msg_response.status == 200:
                        msg_data = await msg_response.json()
                        print(f"  ✅ Chat message processed")
                        print(f"     Response length: {len(msg_data.get('response', ''))}")
                        return True
                    else:
                        error = await msg_response.text()
                        print(f"  ❌ Chat message failed: {msg_response.status} - {error}")
                        return False
            else:
                error = await response.text()
                print(f"  ❌ Chat session creation failed: {response.status} - {error}")
                return False
    except Exception as e:
        print(f"  ❌ Chat session error: {e}")
        return False


async def test_webhook_simulation(session: aiohttp.ClientSession) -> bool:
    """Test Jira webhook simulation."""
    print("🔗 Testing webhook simulation...")
    
    # Simulate Jira webhook payload
    webhook_payload = {
        "webhookEvent": "jira:issue_created",
        "issue": {
            "key": "WEBHOOK-001",
            "fields": {
                "summary": "New bug reported via webhook",
                "description": "This is a test bug report created via webhook simulation",
                "issuetype": {"name": "Bug"},
                "priority": {"name": "Medium"},
                "assignee": {"displayName": "Auto Assigned"},
                "created": "2024-01-20T15:30:00Z",
                "components": [{"name": "backend"}]
            }
        }
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-Atlassian-Webhook-Signature": "test-signature"  # Simplified for testing
    }
    
    try:
        async with session.post(
            f"{API_BASE_URL}/webhooks/jira",
            json=webhook_payload,
            headers=headers
        ) as response:
            if response.status in [200, 202]:  # Accept both success codes
                print(f"  ✅ Webhook processed successfully")
                return True
            else:
                error = await response.text()
                print(f"  ❌ Webhook failed: {response.status} - {error}")
                return False
    except Exception as e:
        print(f"  ❌ Webhook error: {e}")
        return False


async def run_full_test_suite():
    """Run complete test suite."""
    print("🧪 Starting Driftor API Test Suite")
    print("=" * 50)
    
    # Load authentication tokens
    tokens = load_test_tokens()
    if not tokens:
        print("❌ Cannot run tests without authentication tokens")
        return False
    
    admin_token = tokens.get("ADMIN_TOKEN")
    if not admin_token:
        print("❌ Admin token not found")
        return False
    
    test_results = []
    
    async with aiohttp.ClientSession() as session:
        # Run tests
        tests = [
            ("Health Check", test_health_check(session)),
            ("Ticket Analysis", test_ticket_analysis(session, admin_token)),
            ("Vector Search", test_vector_search(session, admin_token)),
            ("LLM Analysis", test_llm_analysis(session, admin_token)),
            ("Chat Session", test_chat_session(session, admin_token)),
            ("Webhook Simulation", test_webhook_simulation(session))
        ]
        
        for test_name, test_coro in tests:
            print()
            try:
                result = await test_coro
                test_results.append((test_name, result))
            except Exception as e:
                print(f"  ❌ {test_name} failed with exception: {e}")
                test_results.append((test_name, False))
    
    # Print summary
    print()
    print("=" * 50)
    print("📊 Test Results Summary")
    print("=" * 50)
    
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print()
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Driftor is working correctly.")
        return True
    else:
        print("⚠️  Some tests failed. Check the logs above for details.")
        return False


async def main():
    """Main test function."""
    success = await run_full_test_suite()
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)