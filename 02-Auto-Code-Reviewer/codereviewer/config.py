"""
Konfiguration & LLM-Provider-Presets (Auto Code Reviewer).

Provider-agnostisch: jeder OpenAI-kompatible Endpunkt (ChatAI der AcademicCloud,
OpenAI, Ollama, ...). Zusaetzlich ein reiner Regel-Modus ("rules"), der ganz ohne
API-Key als statischer Analyzer laeuft.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class ProviderPreset:
    key: str
    label: str
    base_url: str
    default_model: str
    env_key: str
    needs_key: bool = True
    note: str = ""


PROVIDERS: dict[str, ProviderPreset] = {
    # Standard aus der Vorlesung (VL8): ChatAI der GWDG AcademicCloud
    "chatai": ProviderPreset(
        key="chatai",
        label="ChatAI (AcademicCloud)",
        base_url="https://chat-ai.academiccloud.de/v1",
        default_model="qwen3-coder-next",
        env_key="CHATAI_API_KEY",
        note="Uni-Zugang aus der Vorlesung. Code-Modelle wie qwen3-coder-next "
             "oder devstral-2-123b-instruct-2512 sind gut fuer Reviews.",
    ),
    "openai": ProviderPreset(
        key="openai", label="OpenAI",
        base_url="https://api.openai.com/v1", default_model="gpt-4o-mini",
        env_key="OPENAI_API_KEY",
    ),
    "ollama": ProviderPreset(
        key="ollama", label="Ollama (lokal)",
        base_url="http://localhost:11434/v1", default_model="qwen2.5-coder:7b",
        env_key="OLLAMA_API_KEY", needs_key=False,
        note="Lokales Modell. 'ollama serve' muss laufen.",
    ),
    "custom": ProviderPreset(
        key="custom", label="Custom (OpenAI-kompatibel)",
        base_url="", default_model="", env_key="LLM_API_KEY",
    ),
    "offline": ProviderPreset(
        key="offline", label="Offline / Regeln (ohne API)",
        base_url="", default_model="ast-rules", env_key="", needs_key=False,
        note="Nur statische AST-Regelpruefung (wie ein Linter). Kein API-Key noetig.",
    ),
}

DEFAULT_PROVIDER = "chatai"

# Review-Strategien (spiegeln Zero-Shot -> agentisch aus VL8/VL11 wider)
STRATEGIES = {
    "agentic": "Agentisch: LLM-Review (Self-Consistency) + Selbstkritik/Verifikation "
               "(Reflection) — empfohlen",
    "llm": "Nur LLM: Zero-Shot-Review (eine Runde, ohne Verifikation)",
    "rules": "Nur Regeln: statische AST-Analyse (Offline-Baseline, wie ein Linter)",
}

# Kategorien & Schweregrade (fuer Filter/Anzeige/Metriken)
CATEGORIES = ["bug", "security", "performance", "maintainability", "smell", "style", "docs"]
SEVERITIES = ["critical", "high", "medium", "low", "info"]
SEVERITY_RANK = {s: i for i, s in enumerate(SEVERITIES)}


@dataclass
class RunConfig:
    # LLM / Provider
    provider: str = DEFAULT_PROVIDER
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    temperature: float = 0.3

    # Strategie
    strategy: str = "agentic"
    passes: int = 2                 # Review-Durchlaeufe (Self-Consistency, VL5)
    run_verification: bool = True   # Reflection: Findings adversarial pruefen
    run_repair: bool = False        # Program Repair: korrigierte Code-Version erzeugen
    min_severity: str = "info"      # Anzeige-/Filterschwelle

    llm_timeout: int = 120
    extra: dict = field(default_factory=dict)

    def resolve(self) -> "RunConfig":
        preset = PROVIDERS.get(self.provider, PROVIDERS[DEFAULT_PROVIDER])
        if not self.base_url:
            self.base_url = preset.base_url
        if not self.model:
            self.model = preset.default_model
        if not self.api_key and preset.env_key:
            self.api_key = os.environ.get(preset.env_key, "") or os.environ.get("LLM_API_KEY", "")
        return self

    @property
    def is_offline(self) -> bool:
        return self.provider == "offline" or self.strategy == "rules"

    def redacted(self) -> dict:
        return {
            "provider": self.provider, "base_url": self.base_url, "model": self.model,
            "temperature": self.temperature, "strategy": self.strategy,
            "passes": self.passes, "run_verification": self.run_verification,
            "run_repair": self.run_repair, "min_severity": self.min_severity,
        }
