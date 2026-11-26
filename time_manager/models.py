from dataclasses import dataclass
from enum import StrEnum
from typing import Optional


# 맞는 분류 규칙이 없어 중립이 된 기록의 근거
NO_RULE_REASON = "no matching rule"
# 비공개 창: 시간만 기록 (제목·주소는 저장하지 않음)
PRIVATE_REASON = "private window"
PRIVATE_TITLE = "비공개 창"
# 사용자가 직접 추가한 기록 (PC 밖에서 한 일)
MANUAL_ENTRY_REASON = "manual entry"
MANUAL_APP = "직접 입력"


class Category(StrEnum):
    PRODUCTIVE = "productive"
    UNPRODUCTIVE = "unproductive"
    NEUTRAL = "neutral"


@dataclass(frozen=True)
class ActiveTarget:
    app_name: str
    window_title: str
    url: Optional[str] = None
    # 창 소유 프로세스: 실행 파일 이름과 무관하게 이 앱을 식별
    process_id: Optional[int] = None
    # 브라우저의 비공개 창 (InPrivate, 시크릿 모드 등)
    private: bool = False

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

