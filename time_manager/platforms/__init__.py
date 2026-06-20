from time_manager.models import ActiveTarget


class PlatformMonitor:
    def get_active_target(self) -> ActiveTarget:
        raise NotImplementedError

    def idle_seconds(self) -> int:
        return 0
