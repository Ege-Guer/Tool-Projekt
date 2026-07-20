"""Beispiel 2: String-Hilfsfunktionen mit vielen Verzweigungen (gut fuer Coverage)."""


def slugify(text: str) -> str:
    """Wandelt Text in einen URL-Slug um (Kleinbuchstaben, Bindestriche)."""
    if not text:
        return ""
    result = []
    for ch in text.strip().lower():
        if ch.isalnum():
            result.append(ch)
        elif ch in (" ", "-", "_"):
            result.append("-")
    slug = "".join(result)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")


def is_palindrome(text: str) -> bool:
    """Prueft, ob ein Text ein Palindrom ist (ignoriert Gross/Klein & Leerzeichen)."""
    cleaned = "".join(c.lower() for c in text if c.isalnum())
    return cleaned == cleaned[::-1]


def truncate(text: str, length: int, suffix: str = "...") -> str:
    """Kuerzt Text auf `length` Zeichen und haengt `suffix` an."""
    if length < 0:
        raise ValueError("length darf nicht negativ sein")
    if len(text) <= length:
        return text
    return text[:length].rstrip() + suffix


def count_words(text: str) -> int:
    """Zaehlt die Woerter in einem Text."""
    return len([w for w in text.split() if w])
