"""
Feature Registry
----------------
This module defines the central registry for all gateable features in the system.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel
from swx_core.models.billing import FeatureType

class FeatureDefinition(BaseModel):
    key: str
    name: str
    description: str
    feature_type: FeatureType
    unit: Optional[str] = None

class FeatureRegistry:
    """
    A central registry for all gateable features.
    Business code should reference feature keys defined here.
    """
    
    _features: Dict[str, FeatureDefinition] = {}

    @classmethod
    def register(cls, definition: FeatureDefinition):
        cls._features[definition.key] = definition

    @classmethod
    def get(cls, key: str) -> Optional[FeatureDefinition]:
        return cls._features.get(key)

    @classmethod
    def list_all(cls) -> List[FeatureDefinition]:
        return list(cls._features.values())

# Core System Features
FeatureRegistry.register(FeatureDefinition(
    key="api.calls",
    name="API Calls",
    description="Number of API requests allowed per period.",
    feature_type=FeatureType.QUOTA,
    unit="requests"
))

FeatureRegistry.register(FeatureDefinition(
    key="llm.tokens",
    name="LLM Tokens",
    description="Number of tokens allowed for LLM operations.",
    feature_type=FeatureType.QUOTA,
    unit="tokens"
))

FeatureRegistry.register(FeatureDefinition(
    key="advanced.analytics",
    name="Advanced Analytics",
    description="Access to advanced reporting and analytics dashboards.",
    feature_type=FeatureType.BOOLEAN
))

FeatureRegistry.register(FeatureDefinition(
    key="team.members",
    name="Team Members",
    description="Maximum number of members allowed in a team.",
    feature_type=FeatureType.QUOTA,
    unit="members"
))

FeatureRegistry.register(FeatureDefinition(
    key="white_labeling",
    name="White Labeling",
    description="Ability to remove SwX branding from the UI.",
    feature_type=FeatureType.BOOLEAN
))
