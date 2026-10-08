class DomainError(ValueError):
    """A rejected command; the input state remains unchanged."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)
