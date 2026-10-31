class LateFeePolicy:
    """Late-return fee rules the Director can change without editing the code (F27, F28)."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.fines_enabled = True
        self.grace_period_days = 0
        self.daily_rate = 0.25
        self.max_fine = None

    def to_dict(self):
        return {
            "fines_enabled": self.fines_enabled,
            "grace_period_days": self.grace_period_days,
            "daily_rate": self.daily_rate,
            "max_fine": self.max_fine,
        }

    def fine_for(self, days_late):
        if not self.fines_enabled:
            return 0.0
        charged_days = max(0, days_late - self.grace_period_days)
        amount = charged_days * self.daily_rate
        if self.max_fine is not None:
            amount = min(amount, self.max_fine)
        return round(amount, 2)