"""
SwX AI-Aware Layer - Agent Instruction Manifest
=============================================

Generates operating manual for AI agents.
"""

from typing import Any, Dict, List


def get_agent_manifest(format: str = "markdown") -> str:
    """Get agent instruction manifest."""
    
    manifest = _build_manifest()
    
    if format == "json":
        import json
        return json.dumps(manifest, indent=2)
    elif format == "yaml":
        import yaml
        return yaml.dump(manifest, default_flow_style=False)
    else:
        return _format_markdown(manifest)


def _build_manifest() -> Dict[str, Any]:
    """Build manifest structure."""
    
    return {
        "version": "1.0.0",
        "generated_at": "2026-03-08T12:00:00Z",
        "mutation_rules": [
            {
                "id": "MUTATION-001",
                "rule": "Never modify files in CORE zone directly",
                "rationale": "Core framework changes require framework updates",
                "exception": "Use provider override or plugin extension instead"
            },
            {
                "id": "MUTATION-002",
                "rule": "All APP modifications must implement contract interfaces",
                "rationale": "Ensures compatibility and substitutability"
            },
            {
                "id": "MUTATION-003",
                "rule": "Provider modifications must go through container binding",
                "rationale": "Maintains IoC integrity"
            }
        ],
        "file_ownership_rules": {
            "swx_core": {
                "mutability": "none",
                "rationale": "Framework code - do not modify",
                "exceptions": []
            },
            "swx_app": {
                "mutability": "full",
                "rationale": "Application code - safe to modify",
                "restrictions": ["Must implement contracts", "Must respect routes"]
            },
            "swx_plugins": {
                "mutability": "plugin_only",
                "rationale": "Plugin-specific code",
                "restrictions": ["Must follow plugin API"]
            }
        },
        "safe_override_patterns": [
            {
                "pattern": "Provider Override",
                "example": "container.bind('service', CustomImplementation)",
                "when_to_use": "Need different implementation of core service"
            },
            {
                "pattern": "Event Listener",
                "example": "class CustomListener(Listener): event = 'user.created'",
                "when_to_use": "Need to react to system events"
            },
            {
                "pattern": "Middleware",
                "example": "class CustomMiddleware(BaseMiddleware)",
                "when_to_use": "Need to process requests/responses"
            },
            {
                "pattern": "Plugin Hook",
                "example": "def custom_hook(context): pass",
                "when_to_use": "Need to extend plugin functionality"
            }
        ],
        "contract_enforcement_rules": [
            {
                "id": "CONTRACT-001",
                "rule": "Method signatures must match contract exactly",
                "rationale": "Ensures interface compatibility"
            },
            {
                "id": "CONTRACT-002",
                "rule": "Return types must be covariant with contract",
                "rationale": "Liskov substitution principle"
            },
            {
                "id": "CONTRACT-003",
                "rule": "Exceptions must be documented",
                "rationale": "API contract clarity"
            }
        ],
        "testing_requirements": [
            {
                "change_type": "new_service",
                "required_tests": ["unit_test", "integration_test"]
            },
            {
                "change_type": "new_route",
                "required_tests": ["unit_test", "api_test"]
            },
            {
                "change_type": "contract_implementation",
                "required_tests": ["contract_test"]
            }
        ]
    }


def _format_markdown(manifest: Dict[str, Any]) -> str:
    """Format manifest as markdown."""
    
    md = """# SwX Agent Instruction Manifest

## Version: {version}
Generated: {generated_at}

---

## Mutation Rules

""".format(
        version=manifest["version"],
        generated_at=manifest["generated_at"]
    )
    
    for rule in manifest["mutation_rules"]:
        md += """### Rule {id}: {rule}

- **Rationale**: {rationale}
- **Exception**: {exception}

""".format(**rule)
    
    md += """---

## File Ownership Rules

| Zone | Mutability | Rationale |
|------|------------|------------|
"""
    
    for zone, info in manifest["file_ownership_rules"].items():
        md += f"| {zone} | {info['mutability']} | {info['rationale']} |\n"
    
    md += """
---

## Safe Override Patterns

"""
    
    for pattern in manifest["safe_override_patterns"]:
        md += """### {pattern}

- **Example**: `{example}`
- **Use when**: {when_to_use}

""".format(**pattern)
    
    md += """---

## Contract Enforcement Rules

"""
    
    for rule in manifest["contract_enforcement_rules"]:
        md += """### {id}: {rule}

- **Rationale**: {rationale}

""".format(**rule)
    
    md += """---

## Testing Requirements

| Change Type | Required Tests |
|------------|----------------|
"""
    
    for req in manifest["testing_requirements"]:
        md += f"| {req['change_type']} | {', '.join(req['required_tests'])} |\n"
    
    md += """---

*This manifest provides operating instructions for AI agents working with SwX.*
"""
    
    return md
