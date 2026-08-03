"""Prompt Injection Detector
---------------------------
Regex-based detector for common prompt-injection patterns in user input.

Provides:
- ``detect_injection(text, patterns)`` — functional API, returns detection result
- ``PromptInjectionDetector`` — class API, configurable patterns

Default patterns cover instruction override, role manipulation, jailbreak
attempts, and other known attack vectors.  Patterns are overridable via
SystemConfig key ``safety.injection_patterns`` (JSON list of pattern dicts).

Risk levels:  MEDIUM / HIGH / CRITICAL
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


class RiskLevel(str, Enum):
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class InjectionMatch:
    """A single pattern match."""
    pattern_name: str
    risk: RiskLevel
    matched_text: str


@dataclass
class InjectionResult:
    """Result of an injection-detection scan."""
    detected: bool
    risk_level: RiskLevel | None = None
    matches: list[InjectionMatch] = field(default_factory=list)
    score: float = 0.0


# ---------------------------------------------------------------------------
# Default patterns — 12 categories covering known attack vectors
# ---------------------------------------------------------------------------

_DEFAULT_PATTERNS: list[dict[str, Any]] = [
    # Instruction override
    {"name": "ignore_previous", "pattern": r"(?i)ignore\s+(all\s+)?previous\s+(instructions?|prompts?|rules?)", "risk": "critical"},
    {"name": "disregard_instructions", "pattern": r"(?i)disregard\s+(all\s+)?(previous\s+)?(instructions?|rules?|guidelines?)", "risk": "critical"},
    {"name": "forget_everything", "pattern": r"(?i)forget\s+(everything|all|previous|prior|above)", "risk": "critical"},
    # Role manipulation
    {"name": "pretend_role", "pattern": r"(?i)(pretend|act|扮演|扮演)\s+(you\s+are|to\s+be|as\s+(?:a|an|the))\s+\w+", "risk": "high"},
    {"name": "you_are_now", "pattern": r"(?i)you\s+are\s+now\s+(?:a|an)\s+\w+", "risk": "high"},
    {"name": "system_prompt_leak", "pattern": r"(?i)(?:reveal|show|tell|print|display|output)\s+(?:the\s+)?(?:system|initial|original|hidden)\s+(?:prompt|instructions?|message)", "risk": "critical"},
    # Jailbreak
    {"name": "jailbreak", "pattern": r"(?i)jailbreak|逃狱|脱獄", "risk": "critical"},
    {"name": "dan_mode", "pattern": r"(?i)(?:enable\s+)?DAN\s+mode|do\s+anything\s+now", "risk": "critical"},
    # Output manipulation
    {"name": "inject_output_format", "pattern": r"(?i)(?:output|respond|reply|return)\s+(?:only\s+)?(?:with|as)\s+(?:the\s+)?(?:following|this|JSON|XML|raw)", "risk": "medium"},
    {"name": "base64_escape", "pattern": r"(?i)(?:decode|interpret|execute|run)\s+(?:this\s+)?(?:base64|b64|binary|hex)", "risk": "high"},
    # Privilege escalation
    {"name": "sudo_admin", "pattern": r"(?i)(?:sudo|admin|root|superuser|administrator)\s+(?:mode|access|privileges?|command)", "risk": "high"},
    {"name": "bypass_filter", "pattern": r"(?i)bypass\s+(?:the\s+)?(?:filter|safety|security|check|guard|restriction)", "risk": "high"},
]


def _compile_patterns(patterns: list[dict[str, Any]] | None = None) -> list[tuple[str, re.Pattern[str], RiskLevel]]:
    """Compile raw pattern dicts into (name, compiled_regex, risk) tuples.

    Skips patterns with invalid regex and logs a warning.
    """
    source = patterns if patterns is not None else _DEFAULT_PATTERNS
    compiled: list[tuple[str, re.Pattern[str], RiskLevel]] = []
    for entry in source:
        name = entry.get("name", "unknown")
        pattern = entry.get("pattern", "")
        risk_str = entry.get("risk", "medium")
        risk = RiskLevel(risk_str)
        try:
            compiled.append((name, re.compile(pattern), risk))
        except re.error:
            logger.warning("Skipping invalid regex pattern '%s': %s", name, pattern)
    return compiled


_RISK_WEIGHT: dict[RiskLevel, float] = {
    RiskLevel.MEDIUM: 0.3,
    RiskLevel.HIGH: 0.6,
    RiskLevel.CRITICAL: 1.0,
}


def detect_injection(
    text: str,
    patterns: list[dict[str, Any]] | None = None,
) -> InjectionResult:
    """Functional API: scan *text* for prompt-injection patterns.

    Args:
        text: The user input to scan.
        patterns: Optional list of pattern dicts (each with ``name``,
            ``pattern``, ``risk``).  Defaults to ``_DEFAULT_PATTERNS``.

    Returns:
        An ``InjectionResult`` with detection status, risk level, matches,
        and a score (0.0–1.0+ based on match weights).
    """
    compiled = _compile_patterns(patterns)
    matches: list[InjectionMatch] = []
    total_score = 0.0

    for name, regex, risk in compiled:
        m = regex.search(text)
        if m:
            matches.append(InjectionMatch(pattern_name=name, risk=risk, matched_text=m.group(0)))
            total_score += _RISK_WEIGHT[risk]

    if not matches:
        return InjectionResult(detected=False, risk_level=None, matches=[], score=0.0)

    # Highest risk level among matches
    highest = max(matches, key=lambda m: _RISK_WEIGHT[m.risk])
    return InjectionResult(detected=True, risk_level=highest.risk, matches=matches, score=round(total_score, 2))


class PromptInjectionDetector:
    """Class API for prompt-injection detection.

    Patterns default to ``_DEFAULT_PATTERNS`` but can be overridden per
    instance or loaded from SystemConfig at runtime.
    """

    def __init__(self, patterns: list[dict[str, Any]] | None = None) -> None:
        self._patterns = patterns
        self._compiled: list[tuple[str, re.Pattern[str], RiskLevel]] | None = None

    @property
    def compiled(self) -> list[tuple[str, re.Pattern[str], RiskLevel]]:
        if self._compiled is None:
            self._compiled = _compile_patterns(self._patterns)
        return self._compiled

    def detect(self, text: str) -> InjectionResult:
        """Scan text using the detector's configured patterns."""
        return detect_injection(text, self._patterns)

    async def detect_with_db_patterns(self, text: str, session: AsyncSession) -> InjectionResult:
        """Scan text with patterns potentially overridden from SystemConfig.

        SystemConfig key: ``safety.injection_patterns`` (JSON list of pattern dicts).
        Falls back to the detector's instance patterns if the key is absent.
        """
        db_patterns = await self._load_patterns_from_db(session)
        effective = db_patterns if db_patterns is not None else self._patterns
        return detect_injection(text, effective)

    async def _load_patterns_from_db(self, session: AsyncSession) -> list[dict[str, Any]] | None:
        """Attempt to load custom injection patterns from SystemConfig."""
        from swx_core.services.settings_service import get_setting
        from swx_core.models.system_config import SettingValueType

        value = await get_setting(session, "safety.injection_patterns", default=None, value_type=SettingValueType.JSON)
        if isinstance(value, list) and len(value) > 0:
            return value
        return None