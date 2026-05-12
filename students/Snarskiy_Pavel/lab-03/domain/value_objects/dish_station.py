from dataclasses import dataclass
 
@dataclass(frozen=True)
class DishStation:
    """
    Value Object: Кухонная станция приготовления блюда.
    Определяет, на какой станции готовится блюдо.
    """
    value: str
 
    VALID_STATIONS = frozenset({"GRILL", "PASTA", "DESSERT", "BAR", "COLD"})
 
    def __post_init__(self):
        if self.value not in self.VALID_STATIONS:
            raise ValueError(
                f"Неизвестная станция: '{self.value}'. "
                f"Допустимые: {sorted(self.VALID_STATIONS)}"
            )
 
    def __str__(self) -> str:
        return self.value
 
GRILL   = DishStation("GRILL")
PASTA   = DishStation("PASTA")
DESSERT = DishStation("DESSERT")
BAR     = DishStation("BAR")
COLD    = DishStation("COLD")