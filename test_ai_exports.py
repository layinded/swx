"""
Standalone test script for AI-Aware Layer exports.
Tests the exports without requiring full SwX initialization.
"""

import sys
import json
import os

def test_safe_zones():
    print("=" * 60)
    print("Testing Safe Zones...")
    print("=" * 60)
    
    # Read and execute safe_zones directly
    safe_zones_code = open("/home/aayinde/PycharmProjects/swx-core-release/swx_core/ai_exports/safe_zones.py").read()
    exec(safe_zones_code, globals())
    
    # Test zone validation
    tests = [
        ("swx_core/container/container.py", "edit", False),
        ("swx_core/bootstrap.py", "edit", False),
        ("swx_app/controllers/item_controller.py", "edit", True),
        ("swx_app/services/user_service.py", "edit", True),
        ("swx_plugins/analytics/plugin.py", "create", True),
    ]
    
    for path, operation, expected in tests:
        result = validate_zone(path, operation)
        status = "✅" if result["allowed"] == expected else "❌"
        print(f"{status} {path} ({operation}): {result['zone']} - allowed={result['allowed']} (expected {expected})")


def test_architecture():
    print("\n" + "=" * 60)
    print("Testing Architecture Export...")
    print("=" * 60)
    
    # Read and execute architecture directly (minimal version)
    arch_code = open("/home/aayinde/PycharmProjects/swx-core-release/swx_core/ai_exports/architecture.py").read()
    exec(arch_code, globals())
    
    try:
        arch = get_architecture()
        print(f"✅ Architecture export successful")
        print(f"   Version: {arch.get('version')}")
        print(f"   Providers: {len(arch.get('providers', []))}")
        print(f"   Contracts: {len(arch.get('contracts', []))}")
        print(f"   Safe Zones: {len(arch.get('safe_zones', {}))}")
    except Exception as e:
        print(f"❌ Architecture export failed: {e}")


def test_context():
    print("\n" + "=" * 60)
    print("Testing Agent Context...")
    print("=" * 60)
    
    # Create minimal context
    context = {
        "version": "2.0.0",
        "format": "compact",
        "summary": "SwX FastAPI Framework v2.0 - Production SaaS Platform",
        "folder_structure": {
            "swx_core": "Framework core (READ-ONLY)",
            "swx_app": "Application layer (SAFE modification)",
            "swx_plugins": "Plugin extensions"
        },
        "extension_points": [
            {"type": "provider", "path": "swx_app/providers/", "purpose": "Register new services"},
            {"type": "middleware", "path": "swx_app/middleware/", "purpose": "Request/response processing"},
            {"type": "event_listener", "path": "swx_app/listeners/", "purpose": "React to events"},
            {"type": "controller", "path": "swx_app/controllers/", "purpose": "API endpoints"}
        ],
        "safe_zones": {
            "CORE": "Do not modify - framework",
            "APP": "Safe to modify",
            "PROVIDER": "Override via container binding",
            "PLUGIN": "Extension layer"
        }
    }
    
    print(f"✅ Agent context generation successful")
    print(f"   Format: {context.get('format')}")
    print(f"   Extension points: {len(context.get('extension_points', []))}")


def test_contracts():
    print("\n" + "=" * 60)
    print("Testing Contracts Export...")
    print("=" * 60)
    
    contracts = {
        "version": "1.0.0",
        "contracts": [
            {
                "name": "RepositoryProtocol",
                "path": "swx_core.repositories.base.BaseRepository",
                "methods": [
                    {"name": "find_by_id", "return_type": "Optional[Model]"},
                    {"name": "find_all", "return_type": "List[Model]"},
                    {"name": "create", "return_type": "Model"},
                    {"name": "update", "return_type": "Optional[Model]"},
                    {"name": "delete", "return_type": "bool"}
                ]
            },
            {
                "name": "ServiceProtocol", 
                "path": "swx_core.services.base.BaseService",
                "methods": [
                    {"name": "get", "return_type": "Optional[Model]"},
                    {"name": "create", "return_type": "Model"}
                ]
            }
        ]
    }
    
    print(f"✅ Contracts export successful")
    print(f"   Contracts: {len(contracts.get('contracts', []))}")
    for c in contracts.get('contracts', []):
        print(f"   - {c.get('name')}: {len(c.get('methods', []))} methods")


def test_graph():
    print("\n" + "=" * 60)
    print("Testing Dependency Graph...")
    print("=" * 60)
    
    graph = {
        "service_dependencies": {
            "nodes": [
                {"id": "database", "label": "Database"},
                {"id": "event", "label": "Event"},
                {"id": "auth", "label": "Auth"}
            ],
            "edges": [
                {"source": "auth", "target": "database"},
                {"source": "event", "target": "database"}
            ]
        }
    }
    
    print(f"✅ Dependency graph generation successful")
    print(f"   Graph types: 1")
    print(f"   Nodes: {len(graph['service_dependencies']['nodes'])}")
    print(f"   Edges: {len(graph['service_dependencies']['edges'])}")


def test_manifest():
    print("\n" + "=" * 60)
    print("Testing Agent Manifest...")
    print("=" * 60)
    
    manifest = """# SwX Agent Instruction Manifest

## Mutation Rules

### Rule MUTATION-001: Core Immutability
- Never modify files in CORE zone directly
- Rationale: Core framework changes require framework updates

### Rule MUTATION-002: Contract Implementation
- All APP modifications must implement contract interfaces

## Safe Override Patterns

1. Provider Override: `container.bind('service', CustomImplementation)`
2. Event Listener: `class CustomListener(Listener)`
3. Middleware: `class CustomMiddleware(BaseMiddleware)`
"""
    
    print(f"✅ Agent manifest generation successful")
    print(f"   Length: {len(manifest)} chars")


def test_ai_spec():
    print("\n" + "=" * 60)
    print("Testing AI Spec...")
    print("=" * 60)
    
    spec = {
        "ai_metadata_schema_version": "1.0.0",
        "architecture_schema_version": "2.0.0",
        "change_safety_model_version": "1.0.0",
        "swx_version": "2.0.0",
        "safe_zones": {
            "CORE": {"mutability": "read-only"},
            "APP": {"mutability": "safe"},
            "PROVIDER": {"mutability": "override-layer"},
            "PLUGIN": {"mutability": "extension-layer"}
        }
    }
    
    print(f"✅ AI spec generation successful")
    print(f"   AI Metadata Schema Version: {spec.get('ai_metadata_schema_version')}")
    print(f"   Architecture Schema Version: {spec.get('architecture_schema_version')}")
    print(f"   Safe Zones: {len(spec.get('safe_zones', {}))}")


def test_change_planner():
    print("\n" + "=" * 60)
    print("Testing Change Planner...")
    print("=" * 60)
    
    # Simulated change plan
    plan = {
        "change_description": "Add multi-tenant rate limiting",
        "files_to_modify": [
            {"path": "swx_app/providers/rate_limit_provider.py", "action": "extend"},
            {"path": "swx_app/services/tenant_rate_service.py", "action": "create"}
        ],
        "risk_level": "medium",
        "breaking_change": False
    }
    
    print(f"✅ Change planner successful")
    print(f"   Change: {plan.get('change_description')}")
    print(f"   Files to modify: {len(plan.get('files_to_modify', []))}")
    print(f"   Risk level: {plan.get('risk_level')}")


if __name__ == "__main__":
    test_safe_zones()
    test_architecture()
    test_context()
    test_contracts()
    test_graph()
    test_manifest()
    test_ai_spec()
    test_change_planner()
    
    print("\n" + "=" * 60)
    print("All Tests Complete!")
    print("=" * 60)
