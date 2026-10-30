DEFAULT_MAX_LOANS_PER_MEMBER = 10


class Policy:
    """Library rules that staff can change without editing code (F7)."""

    def __init__(self, max_loans_per_member=DEFAULT_MAX_LOANS_PER_MEMBER):
        self.max_loans_per_member = max_loans_per_member

    def to_dict(self):
        return {"max_loans_per_member": self.max_loans_per_member}