# 한국어 전용. t()는 호출 지점 변경 없이 제거 가능하도록 pass-through로 유지.

SUPPORTED_LANGUAGES = ("ko",)

_current_language = "ko"


def set_language(language: str) -> None:
    # 호환성 유지용 — 항상 한국어로 고정
    global _current_language
    _current_language = "ko"


def get_language() -> str:
    return _current_language


def t(text: str) -> str:
    return text
