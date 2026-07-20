"""
LLM-Anbindung (provider-agnostisch, OpenAI-kompatibel).

Spricht jeden OpenAI-kompatiblen Endpunkt an (ChatAI der AcademicCloud, OpenAI,
Ollama, ...). Die eigentliche Client-Bibliothek (`openai`) wird erst beim ersten
Aufruf importiert, damit der Offline-Modus ganz ohne diese Abhaengigkeit laeuft.
"""
from __future__ import annotations

import re

from .config import RunConfig


class LLMError(RuntimeError):
    pass


# Extrahiert den ersten (Python-)Codeblock aus einer Modellantwort.
_CODE_FENCE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_code(text: str) -> str:
    """Holt den Python-Code aus einer LLM-Antwort (mit oder ohne Codeblock)."""
    if not text:
        return ""
    matches = _CODE_FENCE.findall(text)
    if matches:
        # laengsten Codeblock nehmen (i.d.R. die Testdatei)
        return max(matches, key=len).strip()
    # Fallback: falls kein Fence vorhanden ist, aber "def test_" vorkommt
    if "def test" in text or "import " in text:
        return text.strip()
    return ""


class LLMClient:
    """Duenner Wrapper um den OpenAI-kompatiblen Chat-Client."""

    def __init__(self, config: RunConfig):
        self.config = config
        self._client = None

    def _ensure_client(self):
        if self._client is not None:
            return
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover
            raise LLMError(
                "Das Paket 'openai' ist nicht installiert. Installiere es mit "
                "`pip install openai` oder nutze den Offline-Modus."
            ) from exc
        cfg = self.config
        if not cfg.base_url:
            raise LLMError("Keine base_url konfiguriert.")
        # Ollama/manche Endpunkte brauchen keinen echten Key -> Dummy setzen.
        api_key = cfg.api_key or "not-needed"
        self._client = OpenAI(base_url=cfg.base_url, api_key=api_key, timeout=120.0)

    def complete(self, system: str, user: str) -> str:
        """Ein einzelner Chat-Completion-Aufruf. Gibt den rohen Text zurueck."""
        self._ensure_client()
        cfg = self.config
        try:
            resp = self._client.chat.completions.create(
                model=cfg.model,
                temperature=cfg.temperature,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
        except Exception as exc:  # Netzwerk / Auth / Rate-Limit
            raise LLMError(f"LLM-Aufruf fehlgeschlagen: {exc}") from exc
        if not resp.choices:
            raise LLMError("Leere Antwort vom Modell.")
        return resp.choices[0].message.content or ""

    def generate_tests(self, system: str, user: str) -> str:
        """Wie complete(), extrahiert aber direkt den Testcode."""
        raw = self.complete(system, user)
        return extract_code(raw)


def probe_connection(config: RunConfig) -> tuple[bool, str]:
    """Prueft, ob der konfigurierte Endpunkt erreichbar ist (fuer die UI)."""
    if config.is_offline:
        return True, "Offline-Modus (keine Verbindung noetig)."
    try:
        client = LLMClient(config)
        out = client.complete("Antworte mit genau: OK", "ping")
        return True, f"Verbindung ok. Antwort: {out.strip()[:40]}"
    except Exception as exc:
        return False, str(exc)
