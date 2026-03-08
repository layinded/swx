"""
SwX AI Benchmark Framework - Quick Start
=========================================

This document provides a comprehensive framework for measuring whether SwX's 
AI-aware layer genuinely improves AI-assisted development compared to standard FastAPI.

## Quick Start

```bash
# Run the benchmark
python -m benchmarks.runner --compare

# Run safety tests
python -m benchmarks.runner --safety

# Run specific task
python -m benchmarks.runner --task TASK-001 --project swx --agent claude
```

## Project Structure

```
benchmarks/
├── runner.py              # Main benchmark runner
├── results/               # Benchmark results
├── control_fastapi/       # Raw FastAPI project (same features as SwX)
│   └── app/
│       ├── auth/         # JWT implementation
│       ├── middleware/   # Rate limiting
│       ├── events/       # Event system
│       ├── jobs/        # Background jobs
│       └── plugins/     # Plugin system
└── swx_ai_aware/        # SwX project with AI-aware layer
```

## Benchmark Tasks

| ID | Task | Difficulty | Description |
|----|------|------------|-------------|
| TASK-001 | Multi-tenant rate limiting | Medium | Add tenant-specific rate limits |
| TASK-002 | Audit logging | Easy | Add audit trail to admin routes |
| TASK-003 | API key guard | Medium | Replace JWT with API key auth |
| TASK-004 | Billing restrictions | Hard | Plan-based feature access |
| TASK-005 | Event listener | Easy | Subscribe to events |
| TASK-006 | Plugin feature | Medium | Create plugin extension |
| TASK-007 | Provider override | Hard | Refactor service via DI |

## Metrics Measured

### Primary Metrics
- **Determinism Score**: % of runs completing successfully
- **Stability Score**: % of tasks without correction cycles
- **Efficiency Score**: % of correctly modified files

### Secondary Metrics
- Token usage (prompt + completion)
- Time to completion
- Files touched
- Lines changed

### Error Metrics
- Import errors
- Hallucination incidents
- Test failures
- Runtime errors

## Bootstrap Strategies Tested

1. **No context** - Baseline (no architecture info)
2. **AI context export** - Using `swx ai-context`
3. **Architecture JSON** - Using `swx export-architecture`
4. **Dependency graph** - Using `swx export-graph`
5. **Contract registry** - Using `swx export-contracts`
6. **Full bundle** - All exports combined

## Expected Results

Based on the framework design, expected improvements with AI-aware layer:

| Metric | Expected Improvement |
|--------|---------------------|
| Determinism | +15-25% |
| Token efficiency | +10-20% |
| Error rate | -20-40% |
| Stability | +20-30% |

## Safety Tests

The framework also tests that the AI-aware layer correctly:

1. **Blocks CORE modifications** - Prevents editing swx_core files
2. **Enforces contracts** - Warns when contracts aren't implemented
3. **Isolates plugins** - Prevents plugin override conflicts
4. **Allows safe modifications** - APP layer modifications work

## Interpretation Guide

### If improvements are >20%:
**PASS** - AI-aware layer provides meaningful improvement
- Marketing: "XX% more efficient AI development"

### If improvements are 5-20%:
**MARGINAL** - Some benefit, but may not justify adoption
- Marketing: "Improved developer experience"

### If improvements are <5%:
**FAIL** - No meaningful improvement
- Recommendation: Focus on other value propositions

## Running Manual Tests

To manually test an agent:

```python
from benchmarks.runner import BenchmarkRunner, ProjectType, AgentType

runner = BenchmarkRunner()

# Test with SwX project
metrics = await runner.run_task(
    "TASK-001",
    ProjectType.SWX,
    AgentType.CLAUDE
)

print(f"Files touched: {metrics.files_touched}")
print(f"Duration: {metrics.duration_seconds}s")
print(f"Success: {metrics.completed_successfully}")
```

## Integration with CI/CD

```yaml
# .github/workflows/benchmark.yml
name: AI Benchmark
on: [push, pull_request]
jobs:
  benchmark:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run benchmark
        run: python -m benchmarks.runner --compare
      - name: Upload results
        uses: actions/upload-artifact@v2
        with:
          name: benchmark-results
          path: benchmarks/results/
```

## Notes

- This framework requires actual AI agent API access (Claude, GPT, etc.)
- Control FastAPI project provides feature parity with SwX
- Metrics collection includes git diff analysis
- Safety tests verify zone enforcement works correctly

---
Generated: 2026-03-08
Framework Version: 1.0.0
