from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class NotificationEntry:
    created_at: str
    title: str
    message: str


class Notifier:
    def send(self, title: str, message: str) -> None:
        raise NotImplementedError


class NullNotifier(Notifier):
    def send(self, title: str, message: str) -> None:
        return


class WindowsNotifier(Notifier):
    def __init__(self, app_id: str = "시간 관리 매니저") -> None:
        self.app_id = app_id
        self.last_error: str | None = None

    def status(self) -> dict[str, object]:
        try:
            import winotify  # noqa: F401
        except ImportError:
            return {
                "available": False,
                "message": "Windows 알림 모듈을 찾을 수 없어 알림을 표시할 수 없습니다.",
            }
        if self.last_error:
            return {"available": False, "message": f"최근 알림 표시 실패: {self.last_error}"}
        return {
            "available": True,
            "message": "Windows 알림을 사용할 수 있습니다. 표시되지 않으면 Windows 알림 설정을 확인하세요.",
        }

    def send(self, title: str, message: str) -> None:
        try:
            from winotify import Notification
        except ImportError:
            self.last_error = "winotify가 설치되어 있지 않습니다."
            return

        try:
            toast = Notification(app_id=self.app_id, title=title, msg=message)
            toast.show()
            self.last_error = None
        except Exception:
            self.last_error = "Windows가 알림 요청을 거부했습니다."
            return


class RecordingNotifier(Notifier):
    def __init__(self, delegate: Notifier | None = None, limit: int = 100, enabled: bool = True) -> None:
        self.delegate = delegate or NullNotifier()
        self.limit = limit
        self.enabled = enabled
        self._history: list[NotificationEntry] = []

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled

    def status(self) -> dict[str, object]:
        if not self.enabled:
            return {"available": True, "message": "앱 알림이 꺼져 있습니다."}
        if hasattr(self.delegate, "status"):
            return self.delegate.status()
        return {"available": True, "message": "앱 알림이 켜져 있습니다."}

    def send(self, title: str, message: str) -> None:
        if not self.enabled:
            return
        entry = NotificationEntry(
            created_at=datetime.now().astimezone().strftime("%Y-%m-%d %H:%M"),
            title=title,
            message=message,
        )
        self._history.insert(0, entry)
        del self._history[self.limit :]
        self.delegate.send(title, message)

    def alert(self, title: str, message: str) -> None:
        # 알림 활성화 여부와 무관하게 전송 — 포커스 타이머처럼 사용자가 직접 시작한 경우
        entry = NotificationEntry(
            created_at=datetime.now().astimezone().strftime("%Y-%m-%d %H:%M"),
            title=title,
            message=message,
        )
        self._history.insert(0, entry)
        del self._history[self.limit :]
        self.delegate.send(title, message)

    def recent(self) -> list[NotificationEntry]:
        return list(self._history)


def default_notifier() -> Notifier:
    return RecordingNotifier(WindowsNotifier())
