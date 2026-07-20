"""Beispiel 3: Ein kleiner Rechner mit Randfaellen (Division durch 0 etc.).

Angelehnt an das softmax-/Division-Beispiel aus VL7 (Grenzwerte finden).
"""


def divide(a: float, b: float) -> float:
    """Teilt a durch b. Wirft ZeroDivisionError bei b == 0."""
    if b == 0:
        raise ZeroDivisionError("Division durch 0")
    return a / b


def power(base: float, exp: int) -> float:
    """Berechnet base hoch exp (nur nicht-negative ganzzahlige Exponenten)."""
    if exp < 0:
        raise ValueError("exp muss >= 0 sein")
    result = 1.0
    for _ in range(exp):
        result *= base
    return result


def clamp(value: float, low: float, high: float) -> float:
    """Begrenzt value auf das Intervall [low, high]."""
    if low > high:
        raise ValueError("low darf nicht groesser als high sein")
    if value < low:
        return low
    if value > high:
        return high
    return value


def sign(x: float) -> int:
    """Gibt -1, 0 oder 1 je nach Vorzeichen zurueck."""
    if x > 0:
        return 1
    if x < 0:
        return -1
    return 0
