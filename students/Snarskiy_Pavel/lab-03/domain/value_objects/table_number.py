from dataclasses import dataclass
 
@dataclass(frozen=True)
class TableNumber:
    """
    Value Object: Номер столика в зале.
    Валидирует допустимый диапазон номеров.
    """
    value: int
 
    MIN_TABLE = 1
    MAX_TABLE = 999
 
    def __post_init__(self):
        if not isinstance(self.value, int):
            raise TypeError(f"Номер столика должен быть целым числом: {self.value!r}")
        if not (self.MIN_TABLE <= self.value <= self.MAX_TABLE):
            raise ValueError(
                f"Номер столика вне допустимого диапазона "
                f"[{self.MIN_TABLE}, {self.MAX_TABLE}]: {self.value}"
            )
 
    def __str__(self) -> str:
        return f"Столик №{self.value}"