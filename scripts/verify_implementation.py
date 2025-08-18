#!/usr/bin/env python3
"""
Verify that all Driftor components are properly implemented.
"""
import os
import sys
import importlib
from pathlib import Path

def check_file_exists(file_path: str) -> bool:
    """Check if a file exists."""
    return Path(file_path).exists()

def check_import(module_name: str) -> bool:
    """Check if a module can be imported."""
    try:
        importlib.import_module(module_name)
        return True
    except ImportError as e:
        print(f"    ❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"    ❌ Other error: {e}")
        return False

def verify_core_components():
    """Verify core components are implemented."""
    print("🔧 Verifying Core Components")
    print("-" * 30)
    
    components = [
        ("Configuration", "driftor.core.config"),
        ("Database", "driftor.core.database"),
        ("Authentication", "driftor.core.auth"),
        ("Rate Limiter", "driftor.core.rate_limiter"),
        ("Security/Encryption", "driftor.security.encryption"),
        ("Security/Audit", "driftor.security.audit"),
        ("Security/Retention", "driftor.security.retention"),
    ]
    
    passed = 0
    for name, module in components:
        print(f"  {name}...", end=" ")
        if check_import(module):
            print("✅")
            passed += 1
        else:
            print("❌")
    
    print(f"\nCore Components: {passed}/{len(components)} ✅")
    return passed == len(components)

def verify_models():
    """Verify database models are implemented."""
    print("\n📊 Verifying Database Models")
    print("-" * 30)
    
    models = [
        ("Base Models", "driftor.models.base"),
        ("Tenant Models", "driftor.models.tenant"),
    ]
    
    passed = 0
    for name, module in models:
        print(f"  {name}...", end=" ")
        if check_import(module):
            print("✅")
            passed += 1
        else:
            print("❌")
    
    print(f"\nDatabase Models: {passed}/{len(models)} ✅")
    return passed == len(models)

def verify_integrations():
    """Verify integrations are implemented."""
    print("\n🔗 Verifying Integrations")
    print("-" * 30)
    
    integrations = [
        ("Git Base", "driftor.integrations.git.base"),
        ("GitHub", "driftor.integrations.git.github"),
        ("GitLab", "driftor.integrations.git.gitlab"),
        ("Gitea", "driftor.integrations.git.gitea"),
        ("Git Factory", "driftor.integrations.git.factory"),
        ("Jira Client", "driftor.integrations.jira.client"),
        ("Jira Webhooks", "driftor.integrations.jira.webhooks"),
        ("Messaging Base", "driftor.integrations.messaging.base"),
        ("Teams Bot", "driftor.integrations.messaging.teams"),
        ("Slack Bot", "driftor.integrations.messaging.slack"),
        ("Messaging Factory", "driftor.integrations.messaging.factory"),
    ]
    
    passed = 0
    for name, module in integrations:
        print(f"  {name}...", end=" ")
        if check_import(module):
            print("✅")
            passed += 1
        else:
            print("❌")
    
    print(f"\nIntegrations: {passed}/{len(integrations)} ✅")
    return passed == len(integrations)

def verify_ai_components():
    """Verify AI components are implemented."""
    print("\n🤖 Verifying AI Components")
    print("-" * 30)
    
    ai_components = [
        ("LangGraph Workflow", "driftor.agents.graph"),
        ("Ticket Analyzer", "driftor.agents.nodes.ticket_analyzer"),
        ("Similarity Searcher", "driftor.agents.nodes.similarity_searcher"),
        ("Documentation Retriever", "driftor.agents.nodes.doc_retrieval"),
        ("Repository Mapper", "driftor.agents.nodes.repo_mapper"),
        ("Vector DB Base", "driftor.integrations.vector_db.base"),
        ("ChromaDB Client", "driftor.integrations.vector_db.chromadb_client"),
        ("Vector DB Factory", "driftor.integrations.vector_db.factory"),
        ("LLM Base", "driftor.integrations.llm.base"),
        ("Ollama Client", "driftor.integrations.llm.ollama_client"),
        ("OpenAI Client", "driftor.integrations.llm.openai_client"),
        ("LLM Factory", "driftor.integrations.llm.factory"),
    ]
    
    passed = 0
    for name, module in ai_components:
        print(f"  {name}...", end=" ")
        if check_import(module):
            print("✅")
            passed += 1
        else:
            print("❌")
    
    print(f"\nAI Components: {passed}/{len(ai_components)} ✅")
    return passed == len(ai_components)

def verify_configuration_files():
    """Verify configuration files exist."""
    print("\n⚙️  Verifying Configuration Files")
    print("-" * 30)
    
    config_files = [
        ("Docker Compose", "docker-compose.yml"),
        ("Dockerfile", "Dockerfile"),
        ("Environment Template", ".env.example"),
        ("Project Config", "pyproject.toml"),
        ("Database Init", "database/init.sql"),
        ("Alembic Config", "alembic.ini"),
        ("Main Application", "driftor/main.py"),
    ]
    
    passed = 0
    for name, file_path in config_files:
        print(f"  {name}...", end=" ")
        if check_file_exists(file_path):
            print("✅")
            passed += 1
        else:
            print("❌")
    
    print(f"\nConfiguration Files: {passed}/{len(config_files)} ✅")
    return passed == len(config_files)

def verify_test_scripts():
    """Verify test scripts exist."""
    print("\n🧪 Verifying Test Scripts")
    print("-" * 30)
    
    test_scripts = [
        ("Test Data Creation", "scripts/create_test_data.py"),
        ("API Testing", "scripts/test_api.py"),
        ("Startup Script", "start_driftor.sh"),
        ("Testing Guide", "LOCAL_TESTING_GUIDE.md"),
    ]
    
    passed = 0
    for name, file_path in test_scripts:
        print(f"  {name}...", end=" ")
        if check_file_exists(file_path):
            print("✅")
            passed += 1
        else:
            print("❌")
    
    print(f"\nTest Scripts: {passed}/{len(test_scripts)} ✅")
    return passed == len(test_scripts)

def main():
    """Main verification function."""
    print("🔍 Driftor Implementation Verification")
    print("=" * 50)
    
    # Change to project directory
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    # Add project to Python path
    sys.path.insert(0, str(project_root))
    
    results = []
    
    # Run all verifications
    results.append(("Core Components", verify_core_components()))
    results.append(("Database Models", verify_models()))
    results.append(("Integrations", verify_integrations()))
    results.append(("AI Components", verify_ai_components()))
    results.append(("Configuration Files", verify_configuration_files()))
    results.append(("Test Scripts", verify_test_scripts()))
    
    # Print final summary
    print("\n" + "=" * 50)
    print("📋 Verification Summary")
    print("=" * 50)
    
    total_passed = 0
    total_categories = len(results)
    
    for category, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} {category}")
        if passed:
            total_passed += 1
    
    print()
    if total_passed == total_categories:
        print("🎉 All components verified successfully!")
        print("✅ Driftor implementation is complete and ready for testing.")
        print()
        print("Next steps:")
        print("1. Copy .env.example to .env and configure")
        print("2. Run: ./start_driftor.sh")
        print("3. Run: python scripts/test_api.py")
        return True
    else:
        print(f"⚠️  {total_passed}/{total_categories} categories passed.")
        print("❌ Some components are missing or have import errors.")
        print("Please check the errors above and fix missing components.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)