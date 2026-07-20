"""
Evaluationsmetriken.

Enthaelt u.a. die pass@k-Metrik aus VL5 (Folie 43). pass@k schaetzt die
Wahrscheinlichkeit, dass unter k von n gezogenen Stichproben mindestens eine
"korrekt" ist:

    pass@k = E[ 1 - C(n-c, k) / C(n, k) ]

Hier interpretieren wir eine generierte Test-Suite als "korrekt", wenn sie
lauffaehig ist (kompiliert) und alle enthaltenen Tests bestehen (kein Failure).
Das ueberprueft die Zuverlaessigkeit der Generierung ueber mehrere Stichproben.
"""
from __future__ import annotations

from math import comb

from .models import TestCandidate


def pass_at_k(n: int, c: int, k: int) -> float:
    """Unverzerrter pass@k-Schaetzer (Chen et al., 2021; VL5).

    n: Anzahl generierter Stichproben
    c: Anzahl korrekter Stichproben
    k: erlaubte Versuche
    """
    if n <= 0 or k <= 0:
        return 0.0
    k = min(k, n)
    if c <= 0:
        return 0.0
    if n - c < k:
        # dann ist mind. eine der k Ziehungen sicher korrekt
        return 1.0
    return round(1.0 - comb(n - c, k) / comb(n, k), 4)


def is_clean_suite(candidate: TestCandidate) -> bool:
    """Eine Suite gilt als 'korrekt': laeuft & alle Tests bestehen & >=1 Test."""
    e = candidate.execution
    return bool(e and e.compiles and e.passed > 0 and e.failed == 0 and e.errors == 0)


def compute_pass_at_k(samples: list[TestCandidate], ks=(1, 3, 5)) -> dict:
    """Berechnet pass@k ueber eine Liste gleichrangiger Stichproben."""
    n = len(samples)
    c = sum(1 for s in samples if is_clean_suite(s))
    values = {f"pass@{k}": pass_at_k(n, c, k) for k in ks if k <= max(1, n)}
    return {"n": n, "c": c, "values": values}
