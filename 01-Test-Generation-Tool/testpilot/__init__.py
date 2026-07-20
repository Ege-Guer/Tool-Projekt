"""
TestPilot – Agentische, Coverage-gesteuerte Unit-Test-Generierung fuer Python.

Projekt "KI im Software Engineering" (Tool-Projekt).
Oeffentliche API:
    from testpilot import generate, RunConfig
"""
from .config import RunConfig, PROVIDERS, STRATEGIES, DEFAULT_PROVIDER
from .agent import generate, TestPilotAgent
from .models import RunReport, TestCandidate, CodeAnalysis
from .analysis import analyze_source

__all__ = [
    "generate", "TestPilotAgent", "RunConfig",
    "PROVIDERS", "STRATEGIES", "DEFAULT_PROVIDER",
    "RunReport", "TestCandidate", "CodeAnalysis", "analyze_source",
]

__version__ = "1.0.0"
