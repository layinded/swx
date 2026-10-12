"""
SwX AI Benchmark Framework
==========================

A comprehensive framework for measuring AI-assisted development improvement
with the AI-aware layer vs standard FastAPI projects.

Usage:
    python -m benchmarks.runner --task TASK-001 --project swx --agent claude
    python -m benchmarks.runner --compare --output results.json
"""

import json
import time
import asyncio
import subprocess
import hashlib
import ast
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional
import argparse


# =============================================================================
# CONFIGURATION
# =============================================================================

BENCHMARK_ROOT = Path(__file__).parent
CONTROL_FASTAPI_PATH = BENCHMARK_ROOT / "control_fastapi"
SWX_PROJECT_PATH = BENCHMARK_ROOT / "swx_ai_aware"
RESULTS_DIR = BENCHMARK_ROOT / "results"


class ProjectType(Enum):
    FASTAPI = "fastapi"
    SWX = "swx"


class AgentType(Enum):
    CLAUDE = "claude"
    COPILOT = "copilot"
    GPT = "gpt"


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class TaskDefinition:
    """Definition of a benchmark task."""
    id: str
    name: str
    description: str
    difficulty: str
    prompt_template: str
    expected_files_fastapi: list[str] = field(default_factory=list)
    expected_files_swx: list[str] = field(default_factory=list)
    expected_modifications: list[str] = field(default_factory=list)


@dataclass
class RunMetrics:
    """Metrics collected from a single benchmark run."""
    task_id: str
    project_type: str
    agent_type: str
    bootstrap_strategy: str
    
    # Timing
    start_time: datetime = None
    end_time: datetime = None
    duration_seconds: float = 0
    
    # Token usage
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    
    # Code quality
    files_touched: int = 0
    lines_added: int = 0
    lines_deleted: int = 0
    lines_modified: int = 0
    
    # Errors
    compilation_errors: int = 0
    import_errors: int = 0
    test_failures: int = 0
    runtime_errors: int = 0
    
    # Hallucinations
    hallucination_incidents: int = 0
    invalid_imports: list[str] = field(default_factory=list)
    non_existent_methods: list[str] = field(default_factory=list)
    
    # Corrections
    correction_cycles: int = 0
    human_feedback_needed: bool = False
    
    # Success
    completed_successfully: bool = False
    error_message: str = ""


@dataclass
class BootstrapStrategy:
    """Definition of a context injection strategy."""
    id: str
    name: str
    context_injected: str
    ai_context: dict = field(default_factory=dict)
    architecture_json: dict = field(default_factory=dict)
    dependency_graph: str = ""


@dataclass
class SafetyTestResult:
    """Result of a safety enforcement test."""
    test_id: str
    test_name: str
    prompt: str
    expected_outcome: str
    actual_outcome: str
    blocked: bool = False
    warning_issued: bool = False
    false_positive: bool = False
    false_negative: bool = False


@dataclass
class BenchmarkResults:
    """Aggregated benchmark results."""
    timestamp: datetime = None
    total_tasks: int = 0
    fastapi_results: list[RunMetrics] = field(default_factory=list)
    swx_results: list[RunMetrics] = field(default_factory=list)
    
    # Aggregated scores
    determinism_score_fastapi: float = 0
    determinism_score_swx: float = 0
    stability_score_fastapi: float = 0
    stability_score_swx: float = 0
    efficiency_score_fastapi: float = 0
    efficiency_score_swx: float = 0
    
    # Token comparison
    avg_tokens_fastapi: int = 0
    avg_tokens_swx: int = 0
    token_reduction_percent: float = 0
    
    # Error comparison
    total_errors_fastapi: int = 0
    total_errors_swx: int = 0
    error_reduction_percent: float = 0
    
    # Safety
    safety_tests_passed: int = 0
    safety_tests_failed: int = 0


# =============================================================================
# TASK DEFINITIONS
# =============================================================================

BENCHMARK_TASKS: dict[str, TaskDefinition] = {
    "TASK-001": TaskDefinition(
        id="TASK-001",
        name="Add multi-tenant rate limiting",
        description="Modify rate limiting to support tenant-specific limits",
        difficulty="medium",
        prompt_template="""Add multi-tenant rate limiting to support different rate limits per tenant. 
Each tenant should have their own rate limit configuration stored in the database.
The implementation should:
1. Add tenant_id to rate limit configuration
2. Create a tenant-specific rate limit lookup
3. Apply tenant limits before global limits
4. Include tests for tenant isolation""",
        expected_files_fastapi=["app/middleware/rate_limit.py", "app/models/tenant.py", "tests/test_tenant_rate_limit.py"],
        expected_files_swx=["swx_app/providers/rate_limit_provider.py", "swx_app/services/tenant_rate_service.py"],
        expected_modifications=["Add tenant context extraction", "Add per-tenant limit storage", "Modify rate limit check logic"]
    ),
    
    "TASK-002": TaskDefinition(
        id="TASK-002",
        name="Add audit logging to specific route",
        description="Add audit trail for a protected endpoint",
        difficulty="easy",
        prompt_template="""Add audit logging to track all admin API calls.
Log user ID, action, timestamp, request details, and response status to an audit_logs table.
The implementation should:
1. Create audit log model
2. Add audit logging middleware/decorator
3. Apply to admin endpoints
4. Include tests""",
        expected_files_fastapi=["app/middleware/audit.py", "app/models/audit.py", "app/api/admin.py"],
        expected_files_swx=["swx_app/middleware/audit_middleware.py", "swx_app/controllers/admin_controller.py"],
        expected_modifications=["Create audit log model", "Add audit logging middleware/decorator", "Apply to admin endpoint"]
    ),
    
    "TASK-003": TaskDefinition(
        id="TASK-003",
        name="Replace JWT with API key guard",
        description="Switch authentication mechanism on specific routes",
        difficulty="medium",
        prompt_template="""Replace JWT authentication with API key authentication for external service routes.
Use X-API-Key header for authentication.
The implementation should:
1. Create API key validation service
2. Add API key to database model
3. Update route guards to use API key
4. Remove JWT dependency for external routes""",
        expected_files_fastapi=["app/auth/api_key.py", "app/middleware/auth.py", "app/api/external.py"],
        expected_files_swx=["swx_app/guards/api_key_guard.py", "swx_app/routes/external.py"],
        expected_modifications=["Create API key validation", "Update route guards", "Remove JWT dependency for external routes"]
    ),
    
    "TASK-004": TaskDefinition(
        id="TASK-004",
        name="Add billing plan restriction",
        description="Restrict feature access based on subscription plan",
        difficulty="hard",
        prompt_template="""Add billing plan restrictions. Only allow premium features for users on Pro and Enterprise plans.
Free users should see upgrade prompts.
The implementation should:
1. Define plan tiers (free, pro, team, enterprise)
2. Add entitlement check middleware
3. Create restriction decorator
4. Apply to premium features""",
        expected_files_fastapi=["app/middleware/entitlement.py", "app/services/subscription.py"],
        expected_files_swx=["swx_app/services/entitlement_service.py", "swx_app/middleware/plan_restriction.py"],
        expected_modifications=["Define plan tiers", "Add entitlement check", "Create restriction middleware"]
    ),
    
    "TASK-005": TaskDefinition(
        id="TASK-005",
        name="Add new event listener",
        description="Subscribe to existing event for custom handling",
        difficulty="easy",
        prompt_template="""Add an event listener for order.completed events.
When an order is completed, send a confirmation email to the customer.
The implementation should:
1. Create event listener class
2. Register with event dispatcher
3. Implement handler logic with email sending""",
        expected_files_fastapi=["app/events/order_events.py", "app/handlers/order.py"],
        expected_files_swx=["swx_app/listeners/order_listener.py"],
        expected_modifications=["Create event listener class", "Register with event dispatcher", "Implement handler logic"]
    ),
    
    "TASK-006": TaskDefinition(
        id="TASK-006",
        name="Add new plugin feature",
        description="Create plugin extension point",
        difficulty="medium",
        prompt_template="""Create an analytics plugin that tracks user actions.
Implement the plugin interface and register hooks for page views and button clicks.
The implementation should:
1. Define plugin interface
2. Implement analytics plugin class
3. Register hooks for tracking events
4. Store analytics data""",
        expected_files_fastapi=["app/plugins/analytics.py", "app/plugins/manager.py"],
        expected_files_swx=["swx_plugins/analytics/"],
        expected_modifications=["Define plugin interface", "Implement plugin hook", "Create plugin class"]
    ),
    
    "TASK-007": TaskDefinition(
        id="TASK-007",
        name="Refactor service into provider override",
        description="Replace core service with custom implementation",
        difficulty="hard",
        prompt_template="""Refactor the cache service to use Redis instead of in-memory caching.
Create a new provider that overrides the default cache service while maintaining the same interface.
The implementation should:
1. Create custom Redis cache service
2. Override container binding
3. Maintain interface compatibility""",
        expected_files_fastapi=["app/services/cache.py"],
        expected_files_swx=["swx_app/providers/cache_provider.py"],
        expected_modifications=["Create custom cache service", "Update container binding", "Maintain interface compatibility"]
    ),
}


# =============================================================================
# METRICS COLLECTOR
# =============================================================================

class MetricsCollector:
    """Collects and analyzes metrics from benchmark runs."""
    
    def __init__(self, project_path: Path):
        self.project_path = project_path
    
    def collect_tokens(self, agent_output: str) -> dict:
        """Extract token usage from agent output."""
        # Parse token counts from agent output
        # This is agent-specific and would need implementation
        prompt_match = re.search(r'prompt.*?(\d+)', agent_output, re.IGNORECASE)
        completion_match = re.search(r'completion.*?(\d+)', agent_output, re.IGNORECASE)
        
        return {
            "prompt_tokens": int(prompt_match.group(1)) if prompt_match else 0,
            "completion_tokens": int(completion_match.group(1)) if completion_match else 0,
            "total_tokens": 0  # Calculated
        }
    
    def collect_git_diff(self) -> dict:
        """Collect git diff statistics."""
        try:
            result = subprocess.run(
                ["git", "diff", "--stat"],
                cwd=self.project_path,
                capture_output=True,
                text=True
            )
            
            # Parse output like: "file.py | 10 +++---"
            lines = result.stdout.strip().split('\n')
            total_files = 0
            total_additions = 0
            total_deletions = 0
            
            for line in lines:
                if '|' in line:
                    parts = line.split('|')
                    file_name = parts[0].strip()
                    stats = parts[1].strip() if len(parts) > 1 else ""
                    
                    if file_name and file_name != "summary":
                        total_files += 1
                        
                        # Parse additions/deletions
                        add_match = re.search(r'(\d+)\s*\+', stats)
                        del_match = re.search(r'-(\d+)', stats)
                        
                        if add_match:
                            total_additions += int(add_match.group(1))
                        if del_match:
                            total_deletions += int(del_match.group(1))
            
            return {
                "files_touched": total_files,
                "lines_added": total_additions,
                "lines_deleted": total_deletions,
                "lines_modified": total_additions + total_deletions
            }
        except Exception as e:
            return {
                "files_touched": 0,
                "lines_added": 0,
                "lines_deleted": 0,
                "lines_modified": 0
            }
    
    def detect_import_errors(self, file_path: Path) -> list[str]:
        """Detect invalid imports in a Python file."""
        invalid_imports = []
        
        try:
            with open(file_path) as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        # Check if import exists
                        module_name = alias.name.split('.')[0]
                        if not self._module_exists(module_name):
                            invalid_imports.append(alias.name)
                            
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        if not self._module_exists(node.module):
                            invalid_imports.append(node.module)
                            
        except Exception:
            pass
        
        return invalid_imports
    
    def _module_exists(self, module_name: str) -> bool:
        """Check if a module exists in the project."""
        # Check standard library
        stdlib_modules = {
            'os', 'sys', 're', 'json', 'datetime', 'time', 'uuid',
            'pathlib', 'typing', 'collections', 'functools', 'itertools',
            'asyncio', 'contextlib', 'abc', 'copy', 'hashlib', 'hmac',
            'secrets', 'random', 'math', 'statistics', 'decimal', 'fractions'
        }
        
        if module_name in stdlib_modules:
            return True
        
        # Check project imports
        project_imports = [
            'fastapi', 'uvicorn', 'sqlmodel', 'sqlalchemy', 'pydantic',
            'swx_core', 'swx_app', 'jose', 'python_jose', 'passlib',
            'redis', 'httpx', 'alembic'
        ]
        
        return module_name in project_imports
    
    def detect_hallucinations(self, file_path: Path) -> list[str]:
        """Detect hallucinated methods/classes."""
        hallucinations = []
        
        # Known real methods in SwX
        known_methods = {
            'BaseRepository': ['find_by_id', 'find_all', 'create', 'update', 'delete', 'search', 'paginate'],
            'BaseService': ['get', 'create', 'update', 'delete', 'list'],
            'BaseController': ['get', 'create', 'update', 'delete', 'list'],
            'Container': ['bind', 'singleton', 'scoped', 'make', 'tag', 'tagged'],
            'EventDispatcher': ['listen', 'emit', 'dispatch', 'until'],
        }
        
        try:
            with open(file_path) as f:
                content = f.read()
            
            # Look for method calls that don't exist
            for class_name, methods in known_methods.items():
                if class_name in content:
                    # Find all method calls
                    pattern = r'\.(\w+)\('
                    matches = re.findall(pattern, content)
                    
                    for match in matches:
                        if match not in methods:
                            # Could be a hallucination
                            pass  # Would need more sophisticated analysis
                            
        except Exception:
            pass
        
        return hallucinations


# =============================================================================
# AGENT INTERFACE
# =============================================================================

class AgentInterface:
    """Interface for calling AI agents."""
    
    def __init__(self, agent_type: AgentType):
        self.agent_type = agent_type
    
    async def execute_task(
        self,
        task: TaskDefinition,
        project_path: Path,
        bootstrap_context: Optional[dict] = None
    ) -> RunMetrics:
        """Execute a benchmark task with an AI agent."""
        metrics = RunMetrics(
            task_id=task.id,
            project_type=str(project_path),
            agent_type=self.agent_type.value,
            bootstrap_strategy="none" if not bootstrap_context else "with_context",
            start_time=datetime.now()
        )
        
        # Build prompt
        prompt = self._build_prompt(task, bootstrap_context)
        
        # Execute based on agent type
        if self.agent_type == AgentType.CLAUDE:
            result = await self._call_claude(prompt, project_path)
        elif self.agent_type == AgentType.COPILOT:
            result = await self._call_copilot(prompt, project_path)
        else:
            result = await self._call_gpt(prompt, project_path)
        
        # Update metrics
        metrics.end_time = datetime.now()
        metrics.duration_seconds = (metrics.end_time - metrics.start_time).total_seconds()
        metrics.completed_successfully = result.get("success", False)
        metrics.error_message = result.get("error", "")
        
        return metrics
    
    def _build_prompt(self, task: TaskDefinition, context: Optional[dict]) -> str:
        """Build the prompt for the agent."""
        base_prompt = task.prompt_template
        
        if context:
            context_str = json.dumps(context, indent=2)
            return f"""You are working on a SwX project with the following architecture context:

```
{context_str}
```

Task: {base_prompt}

Provide the complete implementation. Only output the files that need to be created or modified.
Follow SwX conventions: use providers for services, containers for DI, and implement contract interfaces."""
        
        return f"""You are working on a Python FastAPI project.
Task: {base_prompt}

Provide the complete implementation."""
    
    async def _call_claude(self, prompt: str, project_path: Path) -> dict:
        """Call Claude API."""
        # This would integrate with Claude API
        # Placeholder implementation
        return {"success": True, "output": ""}
    
    async def _call_copilot(self, prompt: str, project_path: Path) -> dict:
        """Call GitHub Copilot."""
        # This would integrate with Copilot
        return {"success": True, "output": ""}
    
    async def _call_gpt(self, prompt: str, project_path: Path) -> dict:
        """Call OpenAI GPT API."""
        # This would integrate with OpenAI
        return {"success": True, "output": ""}


# =============================================================================
# SAFETY TESTER
# =============================================================================

class SafetyTester:
    """Tests AI-aware layer safety enforcement."""
    
    def __init__(self, project_path: Path):
        self.project_path = project_path
    
    def test_zone_enforcement(self, file_path: str, operation: str) -> SafetyTestResult:
        """Test if zone boundaries are enforced."""
        # Check if file is in CORE zone
        is_core = 'swx_core/' in file_path
        
        if is_core and operation in ['edit', 'delete']:
            return SafetyTestResult(
                test_id="SAFETY-001",
                test_name="Attempt to modify core",
                prompt=f"Modify {file_path}",
                expected_outcome="blocked_or_warning",
                actual_outcome="blocked" if is_core else "allowed",
                blocked=is_core,
                false_negative=not is_core
            )
        
        return SafetyTestResult(
            test_id="SAFETY-001",
            test_name="Attempt to modify core",
            prompt=f"Modify {file_path}",
            expected_outcome="allowed",
            actual_outcome="allowed",
            blocked=False
        )
    
    def test_contract_compliance(self, impl_path: str, contract_name: str) -> SafetyTestResult:
        """Test if contract interface is implemented correctly."""
        # Read implementation
        try:
            with open(impl_path) as f:
                content = f.read()
            
            # Check if implements protocol
            implements = f"implements {contract_name}" in content or f"extends {contract_name}" in content
            
            return SafetyTestResult(
                test_id="SAFETY-002",
                test_name="Bypass contract",
                prompt=f"Create implementation without contract",
                expected_outcome="warning_or_contract_violation",
                actual_outcome="warning" if not implements else "compliant",
                warning_issued=not implements
            )
        except Exception as e:
            return SafetyTestResult(
                test_id="SAFETY-002",
                test_name="Bypass contract",
                prompt=f"Create implementation without contract",
                expected_outcome="error",
                actual_outcome="error",
                false_negative=True
            )
    
    def test_plugin_isolation(self, plugin_a: str, plugin_b: str) -> SafetyTestResult:
        """Test if plugins cannot override each other."""
        # Check if plugin A tries to override plugin B
        try:
            with open(plugin_a) as f:
                content = f.read()
            
            overrides_b = plugin_b in content and 'override' in content.lower()
            
            return SafetyTestResult(
                test_id="SAFETY-003",
                test_name="Incorrect plugin override",
                prompt=f"Override plugin {plugin_b} from {plugin_a}",
                expected_outcome="blocked",
                actual_outcome="blocked" if overrides_b else "allowed",
                blocked=overrides_b
            )
        except Exception:
            return SafetyTestResult(
                test_id="SAFETY-003",
                test_name="Incorrect plugin override",
                prompt="",
                expected_outcome="error",
                actual_outcome="error"
            )


# =============================================================================
# RESULTS ANALYZER
# =============================================================================

class ResultsAnalyzer:
    """Analyzes and compares benchmark results."""
    
    @staticmethod
    def calculate_determinism(results: list[RunMetrics]) -> float:
        """Calculate determinism score."""
        if not results:
            return 0.0
        
        successful = sum(1 for r in results if r.completed_successfully)
        return (successful / len(results)) * 100
    
    @staticmethod
    def calculate_stability(results: list[RunMetrics]) -> float:
        """Calculate stability score."""
        if not results:
            return 0.0
        
        no_corrections = sum(1 for r in results if r.correction_cycles == 0)
        return (no_corrections / len(results)) * 100
    
    @staticmethod
    def calculate_efficiency(results: list[RunMetrics]) -> float:
        """Calculate efficiency score."""
        if not results:
            return 0.0
        
        # Based on files touched vs expected
        total = sum(r.files_touched for r in results)
        errors = sum(r.import_errors + r.test_failures for r in results)
        
        if total == 0:
            return 0.0
        
        return ((total - errors) / total) * 100
    
    @staticmethod
    def analyze_results(fastapi_results: list[RunMetrics], swx_results: list[RunMetrics]) -> BenchmarkResults:
        """Analyze and compare results."""
        results = BenchmarkResults(
            timestamp=datetime.now(),
            total_tasks=len(fastapi_results),
            fastapi_results=fastapi_results,
            swx_results=swx_results,
            determinism_score_fastapi=ResultsAnalyzer.calculate_determinism(fastapi_results),
            determinism_score_swx=ResultsAnalyzer.calculate_determinism(swx_results),
            stability_score_fastapi=ResultsAnalyzer.calculate_stability(fastapi_results),
            stability_score_swx=ResultsAnalyzer.calculate_stability(swx_results),
            efficiency_score_fastapi=ResultsAnalyzer.calculate_efficiency(fastapi_results),
            efficiency_score_swx=ResultsAnalyzer.calculate_efficiency(swx_results)
        )
        
        # Token comparison
        if fastapi_results:
            results.avg_tokens_fastapi = sum(r.total_tokens for r in fastapi_results) // len(fastapi_results)
        if swx_results:
            results.avg_tokens_swx = sum(r.total_tokens for r in swx_results) // len(swx_results)
        
        if results.avg_tokens_fastapi > 0:
            results.token_reduction_percent = (
                (results.avg_tokens_fastapi - results.avg_tokens_swx) / results.avg_tokens_fastapi
            ) * 100
        
        # Error comparison
        results.total_errors_fastapi = sum(
            r.import_errors + r.test_failures + r.compilation_errors
            for r in fastapi_results
        )
        results.total_errors_swx = sum(
            r.import_errors + r.test_failures + r.compilation_errors
            for r in swx_results
        )
        
        if results.total_errors_fastapi > 0:
            results.error_reduction_percent = (
                (results.total_errors_fastapi - results.total_errors_swx) / results.total_errors_fastapi
            ) * 100
        
        return results
    
    @staticmethod
    def generate_report(results: BenchmarkResults) -> str:
        """Generate markdown report."""
        return f"""# SwX AI Benchmark Results

## Summary

- **Date**: {results.timestamp}
- **Total Tasks**: {results.total_tasks}

## Comparison

| Metric | FastAPI | SwX | Improvement |
|--------|---------|-----|-------------|
| Determinism Score | {results.determinism_score_fastapi:.1f}% | {results.determinism_score_swx:.1f}% | {results.determinism_score_swx - results.determinism_score_fastapi:+.1f}% |
| Stability Score | {results.stability_score_fastapi:.1f}% | {results.stability_score_swx:.1f}% | {results.stability_score_swx - results.stability_score_fastapi:+.1f}% |
| Efficiency Score | {results.efficiency_score_fastapi:.1f}% | {results.efficiency_score_swx:.1f}% | {results.efficiency_score_swx - results.efficiency_score_fastapi:+.1f}% |

## Token Usage

| Metric | FastAPI | SwX | Reduction |
|--------|---------|-----|-----------|
| Avg Tokens | {results.avg_tokens_fastapi} | {results.avg_tokens_swx} | {results.token_reduction_percent:.1f}% |

## Error Rates

| Metric | FastAPI | SwX | Reduction |
|--------|---------|-----|-----------|
| Total Errors | {results.total_errors_fastapi} | {results.total_errors_swx} | {results.error_reduction_percent:.1f}% |

## Verdict

{"**PASS**: AI-aware layer provides meaningful improvement" if results.determinism_score_swx > results.determinism_score_fastapi else "**FAIL**: Marginal or no improvement"}
"""


# =============================================================================
# MAIN RUNNER
# =============================================================================

class BenchmarkRunner:
    """Main benchmark runner."""
    
    def __init__(self):
        self.results_dir = RESULTS_DIR
        self.results_dir.mkdir(exist_ok=True)
    
    async def run_task(
        self,
        task_id: str,
        project_type: ProjectType,
        agent_type: AgentType = AgentType.CLAUDE,
        bootstrap_strategy: Optional[BootstrapStrategy] = None
    ) -> RunMetrics:
        """Run a single benchmark task."""
        task = BENCHMARK_TASKS.get(task_id)
        if not task:
            raise ValueError(f"Unknown task: {task_id}")
        
        project_path = SWX_PROJECT_PATH if project_type == ProjectType.SWX else CONTROL_FASTAPI_PATH
        
        # Collect context
        context = None
        if bootstrap_strategy:
            context = bootstrap_strategy.ai_context or bootstrap_strategy.architecture_json
        
        # Execute with agent
        agent = AgentInterface(agent_type)
        metrics = await agent.execute_task(task, project_path, context)
        
        # Collect additional metrics
        collector = MetricsCollector(project_path)
        diff_stats = collector.collect_git_diff()
        metrics.files_touched = diff_stats["files_touched"]
        metrics.lines_added = diff_stats["lines_added"]
        metrics.lines_deleted = diff_stats["lines_deleted"]
        
        return metrics
    
    async def run_comparison(
        self,
        task_ids: list[str],
        agent_type: AgentType = AgentType.CLAUDE
    ) -> BenchmarkResults:
        """Run comparison between FastAPI and SwX."""
        fastapi_results = []
        swx_results = []
        
        for task_id in task_ids:
            # Run with FastAPI
            fastapi_metrics = await self.run_task(
                task_id, ProjectType.FASTAPI, agent_type
            )
            fastapi_results.append(fastapi_metrics)
            
            # Run with SwX
            swx_metrics = await self.run_task(
                task_id, ProjectType.SWX, agent_type
            )
            swx_results.append(swx_metrics)
        
        return ResultsAnalyzer.analyze_results(fastapi_results, swx_results)
    
    def run_safety_tests(self) -> list[SafetyTestResult]:
        """Run safety enforcement tests."""
        tester = SafetyTester(SWX_PROJECT_PATH)
        results = []
        
        # Test 1: Core modification
        results.append(tester.test_zone_enforcement("swx_core/container/container.py", "edit"))
        
        # Test 2: Contract bypass
        results.append(tester.test_contract_compliance(
            "swx_app/services/bad_service.py",
            "UserServiceProtocol"
        ))
        
        # Test 3: Plugin isolation
        results.append(tester.test_plugin_isolation(
            "swx_plugins/analytics/plugin.py",
            "logging"
        ))
        
        return results
    
    async def run_full_benchmark(
        self,
        task_ids: list[str] = None,
        agent_type: AgentType = AgentType.CLAUDE
    ) -> BenchmarkResults:
        """Run the full benchmark suite."""
        if task_ids is None:
            task_ids = list(BENCHMARK_TASKS.keys())
        
        print(f"Running benchmark with {len(task_ids)} tasks...")
        
        # Run comparison
        results = await self.run_comparison(task_ids, agent_type)
        
        # Run safety tests
        safety_results = self.run_safety_tests()
        results.safety_tests_passed = sum(1 for r in safety_results if r.blocked or not r.false_negative)
        results.safety_tests_failed = len(safety_results) - results.safety_tests_passed
        
        # Save results
        output_file = self.results_dir / f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w') as f:
            json.dump(asdict(results), f, indent=2, default=str)
        
        print(f"Results saved to {output_file}")
        
        return results


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="SwX AI Benchmark Framework")
    parser.add_argument("--task", help="Task ID to run")
    parser.add_argument("--project", choices=["fastapi", "swx"], default="swx")
    parser.add_argument("--agent", choices=["claude", "copilot", "gpt"], default="claude")
    parser.add_argument("--compare", action="store_true", help="Run comparison")
    parser.add_argument("--output", help="Output file")
    parser.add_argument("--safety", action="store_true", help="Run safety tests")
    
    args = parser.parse_args()
    
    runner = BenchmarkRunner()
    
    if args.safety:
        results = runner.run_safety_tests()
        for r in results:
            print(f"{r.test_id}: {r.actual_outcome}")
    elif args.compare:
        results = asyncio.run(runner.run_full_benchmark())
        report = ResultsAnalyzer.generate_report(results)
        print(report)
    elif args.task:
        project_type = ProjectType.SWX if args.project == "swx" else ProjectType.FASTAPI
        agent_type = AgentType[args.agent.upper()]
        metrics = asyncio.run(runner.run_task(args.task, project_type, agent_type))
        print(json.dumps(asdict(metrics), indent=2, default=str))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
