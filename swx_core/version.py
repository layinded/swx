"""
SwX Version Information.

Provides semantic versioning with build metadata.

Usage:
    from swx_core.version import __version__, VERSION, get_version_info
    
    print(__version__)  # "2.0.0"
    print(VERSION)      # (2, 0, 0, "final", 0)
    
    info = get_version_info()
    print(info["full"])  # "2.0.0"
    print(info["major"]) # 2
"""

import sys
from typing import NamedTuple, Optional, Dict, Any


class VersionInfo(NamedTuple):
    """Semantic version tuple with release level."""
    major: int
    minor: int
    patch: int
    releaselevel: str  # "alpha", "beta", "candidate", "final"
    serial: int        # Pre-release serial number


# Version components
VERSION_MAJOR = 2
VERSION_MINOR = 0
VERSION_PATCH = 0
VERSION_RELEASE = "final"  # alpha, beta, candidate, final
VERSION_SERIAL = 0

# Computed version
VERSION: VersionInfo = VersionInfo(
    major=VERSION_MAJOR,
    minor=VERSION_MINOR,
    patch=VERSION_PATCH,
    releaselevel=VERSION_RELEASE,
    serial=VERSION_SERIAL
)

# String representation
if VERSION.releaselevel == "final":
    __version__ = f"{VERSION.major}.{VERSION.minor}.{VERSION.patch}"
else:
    __version__ = f"{VERSION.major}.{VERSION.minor}.{VERSION.patch}{VERSION.releaselevel}{VERSION.serial}"


def get_version_info() -> Dict[str, Any]:
    """
    Get detailed version information.
    
    Returns:
        Dictionary with version details.
    """
    return {
        "major": VERSION.major,
        "minor": VERSION.minor,
        "patch": VERSION.patch,
        "releaselevel": VERSION.releaselevel,
        "serial": VERSION.serial,
        "full": __version__,
        "python": sys.version_info[:3],
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    }


def get_version() -> str:
    """Return the version string."""
    return __version__


def get_major_minor_version() -> str:
    """Return major.minor version string (e.g., '2.0')."""
    return f"{VERSION.major}.{VERSION.minor}"


def is_prerelease() -> bool:
    """Check if this is a pre-release version."""
    return VERSION.releaselevel != "final"


# Version comparison helpers
def parse_version(version_str: str) -> tuple:
    """
    Parse a version string into a comparable tuple.
    
    Args:
        version_str: Version string like "2.0.0" or "2.0.0rc1"
    
    Returns:
        Tuple suitable for comparison.
    """
    import re
    
    # Match semantic version with optional prerelease
    match = re.match(r'(\d+)\.(\d+)\.(\d+)(?:(a|b|rc|alpha|beta|candidate)(\d+))?', version_str)
    if not match:
        raise ValueError(f"Invalid version string: {version_str}")
    
    major, minor, patch = int(match.group(1)), int(match.group(2)), int(match.group(3))
    
    if match.group(4):
        # Pre-release versions sort before final
        level = match.group(4)
        serial = int(match.group(5)) if match.group(5) else 0
        level_map = {'a': 0, 'alpha': 0, 'b': 1, 'beta': 1, 'rc': 2, 'candidate': 2}
        return (major, minor, patch, level_map.get(level, 0), serial)
    
    return (major, minor, patch, 3, 0)  # Final release


def check_version_compatible(required: str) -> bool:
    """
    Check if current version is compatible with required version.
    
    Uses semantic versioning: compatible if major version matches
    and current >= required.
    
    Args:
        required: Required version string (e.g., ">=2.0.0", "2.0.0")
    
    Returns:
        True if compatible.
    """
    import re
    
    # Parse operator
    match = re.match(r'([><=!]+)?(.+)', required)
    if not match:
        return False
    
    op = match.group(1) or "=="
    req_version = match.group(2)
    
    current = parse_version(__version__)
    required_ver = parse_version(req_version)
    
    if op == "==":
        return current == required_ver
    elif op == "!=":
        return current != required_ver
    elif op == ">=":
        return current >= required_ver
    elif op == ">":
        return current > required_ver
    elif op == "<=":
        return current <= required_ver
    elif op == "<":
        return current < required_ver
    elif op == "~=":
        # Compatible release: >=2.0.0, <3.0.0
        return (current[:2] == required_ver[:2] and current >= required_ver)
    
    return False