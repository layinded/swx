"""
SwX AI-Aware Layer - CLI Commands
================================

CLI commands for AI-aware layer exports:
- swx export-architecture
- swx export-contracts
- swx export-graph
- swx ai-context
- swx export-agent-rules
- swx export-ai-spec
- swx zone:check
- swx plan-change
"""

import click
import json
import yaml
from pathlib import Path

from swx_core.ai_exports.architecture import get_architecture
from swx_core.ai_exports.context_bundle import generate_agent_context
from swx_core.ai_exports.graph import generate_dependency_graph
from swx_core.ai_exports.contracts import get_contracts_export
from swx_core.ai_exports.agent_manifest import get_agent_manifest
from swx_core.ai_exports.ai_spec import get_ai_spec
from swx_core.ai_exports.safe_zones import validate_zone, check_modification_allowed


@click.group()
def ai():
    """AI-aware layer commands."""
    pass


@ai.command(name="export-architecture")
@click.option("--format", "output_format", type=click.Choice(["json", "yaml", "graph"]), default="json")
@click.option("--include", multiple=True, help="Components to include")
@click.option("--output", "-o", type=click.Path(), help="Output file")
@click.option("--pretty/--no-pretty", default=True)
def export_architecture(output_format, include, output, pretty):
    """Export complete architecture in machine-readable format."""
    try:
        architecture = get_architecture()
        
        # Filter if specific components requested
        if include:
            filtered = {}
            for component in include:
                if component in architecture:
                    filtered[component] = architecture[component]
            architecture = filtered
        
        # Format output
        if output_format == "json":
            content = json.dumps(architecture, indent=2 if pretty else None)
        elif output_format == "yaml":
            content = yaml.dump(architecture, default_flow_style=False)
        elif output_format == "graph":
            # Generate graphviz DOT format
            content = generate_graphviz(architecture)
        else:
            content = json.dumps(architecture, indent=2)
        
        if output:
            Path(output).write_text(content)
            click.echo(f"Architecture exported to {output}")
        else:
            click.echo(content)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@ai.command(name="export-contracts")
@click.option("--format", "output_format", type=click.Choice(["json", "yaml"]), default="json")
@click.option("--interface", help="Specific interface to export")
@click.option("--include-implementations", is_flag=True)
@click.option("--output", "-o", type=click.Path())
def export_contracts(output_format, interface, include_implementations, output):
    """Export contract registry."""
    try:
        contracts = get_contracts_export(
            interface=interface,
            include_implementations=include_implementations
        )
        
        if output_format == "json":
            content = json.dumps(contracts, indent=2)
        else:
            content = yaml.dump(contracts, default_flow_style=False)
        
        if output:
            Path(output).write_text(content)
            click.echo(f"Contracts exported to {output}")
        else:
            click.echo(content)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


@ai.command(name="export-graph")
@click.option("--type", "graph_type", type=click.Choice(["service", "event", "provider", "plugin", "all"]), default="all")
@click.option("--format", "output_format", type=click.Choice(["json", "dot", "mermaid"]), default="json")
@click.option("--output", "-o", type=click.Path())
def export_graph(graph_type, output_format, output):
    """Export dependency graphs."""
    try:
        graph = generate_dependency_graph(graph_type, output_format)
        
        if output:
            Path(output).write_text(graph)
            click.echo(f"Graph exported to {output}")
        else:
            click.echo(graph)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


@ai.command(name="ai-context")
@click.option("--format", "ctx_format", type=click.Choice(["compact", "standard", "detailed"]), default="standard")
@click.option("--include", multiple=True, help="Sections to include")
@click.option("--token-budget", type=int, default=4000, help="Target token count")
@click.option("--output", "-o", type=click.Path())
def ai_context(ctx_format, include, token_budget, output):
    """Generate AI agent context bundle."""
    try:
        context = generate_agent_context(
            format=ctx_format,
            include=list(include) if include else None,
            token_budget=token_budget
        )
        
        content = json.dumps(context, indent=2)
        
        if output:
            Path(output).write_text(content)
            click.echo(f"AI context exported to {output}")
        else:
            click.echo(content)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


@ai.command(name="export-agent-rules")
@click.option("--format", "output_format", type=click.Choice(["json", "markdown", "yaml"]), default="markdown")
@click.option("--output", "-o", type=click.Path())
def export_agent_rules(output_format, output):
    """Export agent instruction manifest."""
    try:
        manifest = get_agent_manifest(output_format)
        
        if output:
            Path(output).write_text(manifest)
            click.echo(f"Agent rules exported to {output}")
        else:
            click.echo(manifest)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


@ai.command(name="export-ai-spec")
@click.option("--format", "output_format", type=click.Choice(["json", "yaml"]), default="json")
@click.option("--output", "-o", type=click.Path())
def export_ai_spec(output_format, output):
    """Export versioned AI specification."""
    try:
        spec = get_ai_spec()
        
        if output_format == "json":
            content = json.dumps(spec, indent=2)
        else:
            content = yaml.dump(spec, default_flow_style=False)
        
        if output:
            Path(output).write_text(content)
            click.echo(f"AI spec exported to {output}")
        else:
            click.echo(content)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


@ai.group(name="zone")
def zone():
    """Zone management commands."""
    pass


@zone.command(name="check")
@click.argument("file_path")
@click.option("--operation", type=click.Choice(["edit", "delete", "create"]), default="edit")
def zone_check(file_path, operation):
    """Check zone classification for a file."""
    try:
        result = validate_zone(file_path, operation)
        
        if result["allowed"]:
            click.echo(f"✅ {operation.upper()} allowed in zone: {result['zone']}")
        else:
            click.echo(f"❌ {operation.upper()} NOT allowed in zone: {result['zone']}")
            if result.get("reason"):
                click.echo(f"   Reason: {result['reason']}")
                
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


@zone.command(name="info")
@click.argument("file_path")
def zone_info(file_path):
    """Show zone information for a file."""
    try:
        result = validate_zone(file_path, "read")
        
        click.echo(f"Zone: {result['zone']}")
        click.echo(f"Mutability: {result.get('mutability', 'unknown')}")
        click.echo(f"Allowed: {result['allowed']}")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


@ai.command(name="plan-change")
@click.argument("description")
@click.option("--format", "output_format", type=click.Choice(["json", "text"]), default="text")
def plan_change(description, output_format):
    """Plan a change with impact analysis."""
    try:
        # Import change planner
        from swx_core.ai_exports.change_planner import plan_modification
        
        plan = plan_modification(description)
        
        if output_format == "json":
            click.echo(json.dumps(plan, indent=2))
        else:
            click.echo(f"Change: {description}")
            click.echo(f"\nFiles to modify:")
            for f in plan.get("files_to_modify", []):
                click.echo(f"  - {f['path']} ({f['action']})")
            
            click.echo(f"\nRisk level: {plan.get('risk_level', 'unknown')}")
            click.echo(f"Breaking change: {plan.get('breaking_change', False)}")
                
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


def generate_graphviz(architecture: dict) -> str:
    """Generate Graphviz DOT format from architecture."""
    lines = ["digraph swx_architecture {"]
    lines.append('  rankdir=LR;')
    lines.append('  node [shape=box];')
    
    # Add providers
    for provider in architecture.get("providers", []):
        lines.append(f'  {provider["name"]} [label="{provider["name"]}"];')
    
    # Add bindings as edges
    for binding in architecture.get("bindings", [])[:20]:  # Limit to 20
        abstract = binding["abstract"]
        concrete = binding.get("concrete", "unknown")
        if "." in concrete:
            concrete = concrete.split(".")[-1]
        lines.append(f'  {abstract} -> {concrete};')
    
    lines.append("}")
    return "\n".join(lines)


def register_ai_commands(cli_group):
    """Register AI commands with main CLI."""
    cli_group.add_command(ai)
    ai.add_command(zone)


if __name__ == "__main__":
    ai()
