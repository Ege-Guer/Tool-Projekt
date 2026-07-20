"""
Multi-Objective-Optimierung: Non-Dominated Sorting + Crowding Distance (NSGA-II).

Direkte Umsetzung von VL7 (Folien 48-58). Wir betrachten das Test-Archiv als
Loesungsmenge und optimieren zwei *konfliktaere* Ziele gleichzeitig:

    Objective 1:  Branch Coverage   -> MAXIMIEREN
    Objective 2:  Anzahl Tests       -> MINIMIEREN  (Proxy fuer Ausfuehrungszeit)

Beide Ziele stehen im Konflikt (mehr Coverage braucht i.d.R. mehr Tests), daher
gibt es nicht *die eine* beste Loesung, sondern eine Pareto-Front von
Kompromissen. Wie in VL7 (Folie 57) angemerkt, liegt selbst die (fast) leere
Suite auf der Front: schlechte Coverage, aber minimale Laufzeit.

Wir implementieren NSGA-II bewusst selbst (statt pymoo zu importieren), um den
Algorithmus transparent zu machen.
"""
from __future__ import annotations

from .models import TestCandidate


def dominates(a: TestCandidate, b: TestCandidate) -> bool:
    """Pareto-Dominanz (Minimierung beider objectives()).

    a dominiert b, wenn a in KEINEM Ziel schlechter und in MINDESTENS einem
    Ziel echt besser ist (VL7, Folie 49).
    """
    oa, ob = a.objectives(), b.objectives()
    not_worse = all(x <= y for x, y in zip(oa, ob))
    strictly_better = any(x < y for x, y in zip(oa, ob))
    return not_worse and strictly_better


def non_dominated_sort(pop: list[TestCandidate]) -> list[list[TestCandidate]]:
    """Fast Non-Dominated Sorting (Deb et al., 2002). Liefert Fronten F1, F2, ..."""
    n = len(pop)
    S = [[] for _ in range(n)]        # von i dominierte Individuen
    dom_count = [0] * n               # Anzahl der i dominierenden Individuen
    fronts: list[list[int]] = [[]]

    for p in range(n):
        for q in range(n):
            if p == q:
                continue
            if dominates(pop[p], pop[q]):
                S[p].append(q)
            elif dominates(pop[q], pop[p]):
                dom_count[p] += 1
        if dom_count[p] == 0:
            fronts[0].append(p)

    i = 0
    while fronts[i]:
        nxt = []
        for p in fronts[i]:
            for q in S[p]:
                dom_count[q] -= 1
                if dom_count[q] == 0:
                    nxt.append(q)
        i += 1
        fronts.append(nxt)
    fronts.pop()  # letzte (leere) Front entfernen

    return [[pop[idx] for idx in front] for front in fronts]


def crowding_distance(front: list[TestCandidate]) -> dict[str, float]:
    """Crowding Distance je Individuum einer Front (VL7, Folie 55).

    Loesungen in duenn besetzten Regionen bekommen hoehere Distanz -> werden
    bevorzugt, um die Front gut zu verteilen.
    """
    size = len(front)
    dist = {c.id: 0.0 for c in front}
    if size <= 2:
        for c in front:
            dist[c.id] = float("inf")
        return dist

    num_obj = len(front[0].objectives())
    for m in range(num_obj):
        ordered = sorted(front, key=lambda c: c.objectives()[m])
        dist[ordered[0].id] = float("inf")
        dist[ordered[-1].id] = float("inf")
        lo = ordered[0].objectives()[m]
        hi = ordered[-1].objectives()[m]
        span = hi - lo or 1.0
        for k in range(1, size - 1):
            prev = ordered[k - 1].objectives()[m]
            nxt = ordered[k + 1].objectives()[m]
            dist[ordered[k].id] += (nxt - prev) / span
    return dist


def pareto_front(pop: list[TestCandidate]) -> list[TestCandidate]:
    """Erste (nicht-dominierte) Pareto-Front, sortiert nach Coverage."""
    valid = [c for c in pop if c.is_valid]
    if not valid:
        return []
    fronts = non_dominated_sort(valid)
    front = fronts[0] if fronts else []
    return sorted(front, key=lambda c: (-c.branch_cov, c.num_tests))


def rank_population(pop: list[TestCandidate]) -> list[tuple[TestCandidate, int, float]]:
    """Gibt (Kandidat, Front-Rang, Crowding-Distance) fuer die ganze Population."""
    valid = [c for c in pop if c.is_valid]
    fronts = non_dominated_sort(valid)
    out = []
    for rank, front in enumerate(fronts):
        cd = crowding_distance(front)
        for c in front:
            out.append((c, rank, cd[c.id]))
    return out


def knee_point(front: list[TestCandidate]) -> TestCandidate | None:
    """Bester Kompromiss auf der Front ("Knie"): naeheste Loesung zum Idealpunkt.

    Normiert beide Ziele auf [0,1] und waehlt die Loesung mit minimalem Abstand
    zum Idealpunkt (max Coverage, min Tests).
    """
    if not front:
        return None
    if len(front) == 1:
        return front[0]
    covs = [c.branch_cov for c in front]
    tests = [c.num_tests for c in front]
    cmin, cmax = min(covs), max(covs)
    tmin, tmax = min(tests), max(tests)
    c_span = (cmax - cmin) or 1.0
    t_span = (tmax - tmin) or 1.0

    best, best_d = None, float("inf")
    for c in front:
        # Ideal: Coverage = cmax (norm 1), Tests = tmin (norm 0)
        nc = (c.branch_cov - cmin) / c_span
        nt = (c.num_tests - tmin) / t_span
        d = (1 - nc) ** 2 + nt ** 2
        if d < best_d:
            best, best_d = c, d
    return best
