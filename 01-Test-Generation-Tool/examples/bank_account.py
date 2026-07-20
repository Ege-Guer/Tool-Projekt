"""Beispiel 1: Ein Bankkonto mit Validierung – viele Verzweigungen (gut fuer
Branch Coverage und Mutation Testing)."""


class InsufficientFundsError(Exception):
    """Wird geworfen, wenn eine Abhebung das Guthaben uebersteigt."""


class BankAccount:
    def __init__(self, owner: str, balance: float = 0.0):
        if not owner:
            raise ValueError("owner darf nicht leer sein")
        if balance < 0:
            raise ValueError("balance darf nicht negativ sein")
        self.owner = owner
        self.balance = balance
        self.history: list[str] = []

    def deposit(self, amount: float) -> float:
        if amount <= 0:
            raise ValueError("amount muss positiv sein")
        self.balance += amount
        self.history.append(f"deposit {amount}")
        return self.balance

    def withdraw(self, amount: float) -> float:
        if amount <= 0:
            raise ValueError("amount muss positiv sein")
        if amount > self.balance:
            raise InsufficientFundsError("nicht genug Guthaben")
        self.balance -= amount
        self.history.append(f"withdraw {amount}")
        return self.balance

    def transfer(self, other: "BankAccount", amount: float) -> None:
        if other is self:
            raise ValueError("kann nicht auf dasselbe Konto ueberweisen")
        self.withdraw(amount)
        other.deposit(amount)

    def apply_interest(self, rate: float) -> float:
        """Verzinst positives Guthaben. Negativer Zinssatz ist unzulaessig."""
        if rate < 0:
            raise ValueError("rate darf nicht negativ sein")
        if self.balance > 0:
            self.balance += self.balance * rate
        return round(self.balance, 2)
