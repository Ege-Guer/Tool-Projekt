"""
Konfiguration & LLM-Provider-Presets.

Das Tool ist provider-agnostisch: es spricht jeden OpenAI-kompatiblen Endpunkt an
(ChatAI der AcademicCloud, OpenAI, Ollama, ...). Zusaetzlich gibt es einen
Offline-Modus ("heuristic"), der ohne API-Key funktioniert.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


# --------------------------------------------------------------------------- #
# Provider-Presets (OpenAI-kompatible base_urls aus der Vorlesung)
# --------------------------------------------------------------------------- #
@dataclass
class ProviderPreset:
    key: str
    label: str
    base_url: str
    default_model: str
    env_key: str                       # Umgebungsvariable fuer den API-Key
    needs_key: bool = True
    note: str = ""


PROVIDERS: dict[str, ProviderPreset] = {
    # Standard aus der Vorlesung (VL8, Folie 35): ChatAI der GWDG AcademicCloud
    "chatai": ProviderPreset(
        key="chatai",
        label="ChatAI (AcademicCloud)",
        base_url="https://chat-ai.academiccloud.de/v1",
        default_model="meta-llama-3.1-8b-instruct",
        env_key="CHATAI_API_KEY",
        note="Uni-Zugang aus der Vorlesung. API-Key ueber die AcademicCloud.",
    ),
    "openai": ProviderPreset(
        key="openai",
        label="OpenAI",
        base_url="https://api.openai.com/v1",
        default_model="gpt-4o-mini",
        env_key="OPENAI_API_KEY",
    ),
    "ollama": ProviderPreset(
        key="ollama",
        label="Ollama (lokal)",
        base_url="http://localhost:11434/v1",
        default_model="qwen2.5-coder:7b",
        env_key="OLLAMA_API_KEY",
        needs_key=False,
        note="Lokales Modell. 'ollama serve' muss laufen.",
    ),
    "custom": ProviderPreset(
        key="custom",
        label="Custom (OpenAI-kompatibel)",
        base_url="",
        default_model="",
        env_key="LLM_API_KEY",
    ),
    "offline": ProviderPreset(
        key="offline",
        label="Offline / Heuristik (ohne API)",
        base_url="",
        default_model="ast-heuristic",
        env_key="",
        needs_key=False,
        note="Erzeugt Tests per statischer AST-Analyse (SBST-Baseline). Kein API-Key noetig.",
    ),
}

DEFAULT_PROVIDER = "chatai"

# Generierungsstrategien (spiegeln die drei Ansaetze aus VL11 wider)
STRATEGIES = {
    "hybrid": "Hybrid: LLM-Erstwurf + agentischer Feedback-Loop (empfohlen, wie TestForge/CoverUp)",
    "llm": "Nur LLM: Zero-Shot Erstwurf + LLM-Reparatur (Dialogue-based)",
    "heuristic": "Nur Heuristik: SBST-artige AST-Generierung (Offline-Baseline, wie Pynguin)",
}


@dataclass
class RunConfig:
    """Alle Parameter fuer einen Generierungslauf."""
    # LLM / Provider
    provider: str = DEFAULT_PROVIDER
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    temperature: float = 0.4

    # Strategie & Suche
    strategy: str = "hybrid"
    max_iterations: int = 5            # Stopp-Kriterium T (Zeit-/Iterationsbudget, VL11)
    target_coverage: float = 100.0     # Ziel-Branch-Coverage in %
    samples_per_step: int = 1          # n Kandidaten pro Schritt (fuer pass@k)

    # Feature-Toggles
    run_mutation: bool = True
    run_pareto: bool = True

    # Fitness-Gewichte (SBSE)
    w_line: float = 0.5
    w_branch: float = 0.5

    # Ausfuehrung
    pytest_timeout: int = 60           # Sekunden pro pytest-Lauf

    extra: dict = field(default_factory=dict)

    def resolve(self) -> "RunConfig":
        """Fuellt base_url/model/api_key aus dem Preset + Umgebungsvariablen."""
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
        return self.provider == "offline" or self.strategy == "heuristic"

    def redacted(self) -> dict:
        """Config fuer den Report – ohne den API-Key."""
        d = {
            "provider": self.provider,
            "base_url": self.base_url,
            "model": self.model,
            "temperature": self.temperature,
            "strategy": self.strategy,
            "max_iterations": self.max_iterations,
            "target_coverage": self.target_coverage,
            "samples_per_step": self.samples_per_step,
            "run_mutation": self.run_mutation,
            "run_pareto": self.run_pareto,
        }
        return d
