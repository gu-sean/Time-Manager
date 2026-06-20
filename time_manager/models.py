from dataclasses import dataclass
from enum import StrEnum
from typing import Optional


class Category(StrEnum):
    PRODUCTIVE = "productive"
    UNPRODUCTIVE = "unproductive"
    NEUTRAL = "neutral"


@dataclass(frozen=True)
class ActiveTarget:
    app_name: str
    window_title: str
    url: Optional[str] = None

    @property
    def identity(self) -> str:
        if self.url:
            return self.url
        if self.window_title:
            return f"{self.app_name} | {self.window_title}"
        return self.app_name


@dataclass(frozen=True)
class ClassifiedActivity:
    target: ActiveTarget
    category: Category
    reason: str

