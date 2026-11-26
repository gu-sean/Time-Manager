from time_manager.models import ActiveTarget


class PlatformMonitor:
    def get_active_target(self) -> ActiveTarget:
        raise NotImplementedError

    def idle_seconds(self) -> int:
        return 0

    def media_playing(self, app_name: str) -> bool:
        """지금 보고 있는 앱에서 영상·회의가 재생 중인지."""
        return False
