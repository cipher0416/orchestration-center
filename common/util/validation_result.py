class ValidationResult:
    def __init__(self, is_valid: bool, message:str):
        self.is_valid = is_valid
        self.message = message

    def __str__(self) -> str:
        return f"{self.is_valid},msg: {self.message}"