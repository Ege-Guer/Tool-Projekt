"""
LLM-Anbindung (provider-agnostisch, OpenAI-kompatibel).

Spricht jeden OpenAI-kompatiblen Endpunkt an (ChatAI der AcademicCloud, OpenAI,
Ollama, ...). Die eigentliche Client-Bibliothek (`openai`) wird erst beim ersten
Aufruf importiert, damit der Offline-Modus ganz ohne diese Abhaengigkeit laeuft.

Fuer den Reviewer brauchen wir strukturierte Ausgaben (JSON-Listen von Findings),
daher gibt es robuste Extraktions-Helfer fuer Code- UND JSON-Antworten.
"""
from __future__ import annotations

import json
import re

from .config import RunConfig


class LLMError(RuntimeError):
    pass


_CODE_FENCE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
_JSON_FENCE = re.compile(r"```(?:json)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_code(text: str) -> str:
    """Holt Python-Code aus einer LLM-Antwort (mit oder ohne Codeblock)."""
    if not text:
        return ""
    matches = _CODE_FENCE.findall(text)
    if matches:
        return max(matches, key=len).strip()
    if "def " in text or "import " in text:
        return text.strip()
    return ""


def extract_json(text: str):
    """Extrahiert das erste JSON-Objekt/-Array aus einer LLM-Antwort.

    Toleriert Codebloecke, Vor-/Nachtext und zusaetzliches Geschwafel.
    Gibt das geparste Objekt zurueck oder None.
    """
    if not text:
        return None
    # 1) ```json ...``` Block
    for m in _JSON_FENCE.findall(text):
        try:
            return json.loads(m.strip())
        except json.JSONDecodeError:
            pass
    # 2) direkt parsen
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    # 3) groesste [...] oder {...} Klammer heuristisch herausschneiden
    for open_c, close_c in (("[", "]"), ("{", "}")):
        start = text.find(open_c)
        end = text.rfind(close_c)
        if 0 <= start < end:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                continue
    return None


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
                "`pip install openai` oder nutze den Offline-Modus (Regeln)."
            ) from exc
        cfg = self.config
        if not cfg.base_url:
            raise LLMError("Keine base_url konfiguriert.")
        api_key = cfg.api_key or "not-needed"
        self._client = OpenAI(base_url=cfg.base_url, api_key=api_key,
                              timeout=float(cfg.llm_timeout))

    def complete(self, system: str, user: str, temperature: float | None = None) -> str:
        """Ein einzelner Chat-Completion-Aufruf. Gibt den rohen Text zurueck."""
        self._ensure_client()
        cfg = self.config
        try:
            resp = self._client.chat.completions.create(
                model=cfg.model,
                temperature=cfg.temperature if temperature is None else temperature,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
        except Exception as exc:
            raise LLMError(f"LLM-Aufruf fehlgeschlagen: {exc}") from exc
        if not resp.choices:
            raise LLMError("Leere Antwort vom Modell.")
        return resp.choices[0].message.content or ""

    def complete_json(self, system: str, user: str, temperature: float | None = None):
        """Wie complete(), gibt aber das geparste JSON zurueck (oder None)."""
        return extract_json(self.complete(system, user, temperature))

    def complete_code(self, system: str, user: str, temperature: float | None = None) -> str:
        return extract_code(self.complete(system, user, temperature))


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
