from dataclasses import dataclass
from typing import Optional
 
@dataclass(frozen=True)
class ListActiveOrdersQuery:
    """
    Запрос: список активных заказов в зале.
    Поддерживает пагинацию и фильтрацию по статусу.
    """
    page: int = 1
    page_size: int = 20
    status_filter: Optional[str] = None     # None = все активные
 
    def __post_init__(self):
        if self.page < 1:
            raise ValueError(f"page должен быть >= 1: {self.page}")
        if not (1 <= self.page_size <= 100):
            raise ValueError(f"page_size должен быть от 1 до 100: {self.page_size}")