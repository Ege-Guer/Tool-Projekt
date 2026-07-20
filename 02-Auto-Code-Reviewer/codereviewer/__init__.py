"""
Auto Code Reviewer – Agentisches, LLM-gestuetztes Code-Review fuer Python.

Projekt "KI im Software Engineering" (Tool-Projekt).
Oeffentliche API:
    from codereviewer import review, RunConfig
"""
from .config import RunConfig, PROVIDERS, STRATEGIES, DEFAULT_PROVIDER, CATEGORIES, SEVERITIES
from .agent import review, ReviewAgent
from .models import ReviewReport, Finding, CodeStructure
from .analysis import analyze_source
from . import rules, report

__all__ = [
    "review", "ReviewAgent", "RunConfig",
    "PROVIDERS", "STRATEGIES", "DEFAULT_PROVIDER", "CATEGORIES", "SEVERITIES",
    "ReviewReport", "Finding", "CodeStructure", "analyze_source", "rules", "report",
]

__version__ = "1.0.0"
