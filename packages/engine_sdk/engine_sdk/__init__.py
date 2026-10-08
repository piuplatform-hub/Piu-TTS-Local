"""
AI Voice Studio — Engine Adapter SDK (v1.0)
Standardized capability-driven adapter framework for AI inference workers.
"""

from .manifest import EngineManifest, CapabilityEnum
from .protocol import SynthesisRequest, SynthesisResponse, HealthResponse, InfoResponse, ErrorResponse

__all__ = [
    "EngineManifest",
    "CapabilityEnum",
    "SynthesisRequest",
    "SynthesisResponse",
    "HealthResponse",
    "InfoResponse",
    "ErrorResponse",
]
