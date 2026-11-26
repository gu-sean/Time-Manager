"""영상·회의를 보는 중인지 확인 (Windows).

- 입력이 없어도 사용 중인 경우를 자리 비움과 구분
- 두 조건을 모두 만족해야 함: 보고 있는 앱에서 소리가 남 + 화면 켜짐 유지 요청이 있음
  - 화면 켜짐 요청은 어느 프로그램 것인지 알 수 없고, 계속 켜져 있는 PC 도 있어 단독으로 쓰지 않음
  - 음악만 재생하는 앱은 보통 화면 켜짐을 요청하지 않음
- 소리의 크기만 읽고 내용은 읽지 않음
"""
from __future__ import annotations

import ctypes
from ctypes import POINTER, c_float, c_int, c_uint, c_ulong, c_void_p, wintypes
from pathlib import Path
from typing import Iterator

from comtypes import CLSCTX_ALL, COMMETHOD, GUID, HRESULT, CoCreateInstance, IUnknown

_SYSTEM_EXECUTION_STATE = 16
_ES_DISPLAY_REQUIRED = 0x2
_RENDER = 0
_DEVICE_ACTIVE = 0x1
# 이보다 작은 값은 무음으로 봄
_SILENCE = 1e-5
_CLSID_DEVICE_ENUMERATOR = GUID("{BCDE0395-E52F-467C-8E3D-C4579291692E}")


def _method(name: str, *arguments: tuple) -> object:
    return COMMETHOD([], HRESULT, name, *arguments)


def _out(kind: type, name: str = "value") -> tuple:
    return (["out"], POINTER(kind), name)


def _in(kind: type, name: str) -> tuple:
    return (["in"], kind, name)


class _AudioMeter(IUnknown):
    _iid_ = GUID("{C02216F6-8C67-4B5B-9D00-D008E73E0064}")
    _methods_ = [_method("GetPeakValue", _out(c_float))]


class _SessionControl(IUnknown):
    _iid_ = GUID("{F4B1A599-7266-4319-A8CA-E70ACB11E8CD}")
    # 쓰지 않는 메서드도 순서를 맞추려면 선언해야 함
    _methods_ = [
        _method("GetState", _out(c_int)),
        _method("GetDisplayName", _out(c_void_p)),
        _method("SetDisplayName", _in(wintypes.LPCWSTR, "name"), _in(c_void_p, "context")),
        _method("GetIconPath", _out(c_void_p)),
        _method("SetIconPath", _in(wintypes.LPCWSTR, "path"), _in(c_void_p, "context")),
        _method("GetGroupingParam", _out(GUID)),
        _method("SetGroupingParam", _in(c_void_p, "grouping"), _in(c_void_p, "context")),
        _method("RegisterAudioSessionNotification", _in(c_void_p, "events")),
        _method("UnregisterAudioSessionNotification", _in(c_void_p, "events")),
    ]


class _SessionControl2(_SessionControl):
    _iid_ = GUID("{BFB7FF88-7239-4FC9-8FA2-07C950BE9C6D}")
    _methods_ = [
        _method("GetSessionIdentifier", _out(c_void_p)),
        _method("GetSessionInstanceIdentifier", _out(c_void_p)),
        _method("GetProcessId", _out(c_ulong)),
    ]


class _SessionList(IUnknown):
    _iid_ = GUID("{E2F5BB11-0570-40CA-ACDD-3AA01277DEE8}")
    _methods_ = [
        _method("GetCount", _out(c_int)),
        _method("GetSession", _in(c_int, "index"), _out(POINTER(_SessionControl), "session")),
    ]


class _SessionManager(IUnknown):
    _iid_ = GUID("{77AA99A0-1BD6-484F-8BC7-2C654C9A9B6F}")
    _methods_ = [
        _method("GetAudioSessionControl", _in(c_void_p, "guid"), _in(c_ulong, "flags"), _out(c_void_p)),
        _method("GetSimpleAudioVolume", _in(c_void_p, "guid"), _in(c_ulong, "flags"), _out(c_void_p)),
        _method("GetSessionEnumerator", _out(POINTER(_SessionList), "sessions")),
    ]


class _Device(IUnknown):
    _iid_ = GUID("{D666063F-1587-4E43-81F1-B948E807363F}")
    _methods_ = [
        _method(
            "Activate",
            _in(POINTER(GUID), "iid"), _in(c_ulong, "context"), _in(c_void_p, "params"),
            _out(POINTER(IUnknown), "interface"),
        )
    ]


class _DeviceList(IUnknown):
    _iid_ = GUID("{0BD7A1BE-7A1A-44DB-8397-CC5392387B5E}")
    _methods_ = [
        _method("GetCount", _out(c_uint)),
        _method("Item", _in(c_uint, "index"), _out(POINTER(_Device), "device")),
    ]


class _DeviceEnumerator(IUnknown):
    _iid_ = GUID("{A95664D2-9614-4F35-A746-DE8DB63617E6}")
    _methods_ = [
        _method(
            "EnumAudioEndpoints",
            _in(c_int, "flow"), _in(c_ulong, "mask"), _out(POINTER(_DeviceList), "devices"),
        )
    ]


def display_required() -> bool:
    """어떤 프로그램이든 화면을 켜 두라고 요청한 상태인지."""
    state = c_ulong()
    status = ctypes.WinDLL("powrprof").CallNtPowerInformation(
        _SYSTEM_EXECUTION_STATE, None, 0, ctypes.byref(state), ctypes.sizeof(state)
    )
    return status == 0 and bool(state.value & _ES_DISPLAY_REQUIRED)


def audio_sessions() -> Iterator[tuple[int, float]]:
    """사용 중인 모든 출력 장치의 (프로세스 id, 지금 음량). COM 이 초기화된 스레드에서 호출."""
    enumerator = CoCreateInstance(_CLSID_DEVICE_ENUMERATOR, _DeviceEnumerator, CLSCTX_ALL)
    devices = enumerator.EnumAudioEndpoints(_RENDER, _DEVICE_ACTIVE)
    for device_index in range(devices.GetCount()):
        raw = devices.Item(device_index).Activate(ctypes.byref(_SessionManager._iid_), CLSCTX_ALL, None)
        sessions = raw.QueryInterface(_SessionManager).GetSessionEnumerator()
        for session_index in range(sessions.GetCount()):
            control = sessions.GetSession(session_index)
            pid = control.QueryInterface(_SessionControl2).GetProcessId()
            yield int(pid), float(control.QueryInterface(_AudioMeter).GetPeakValue())


def app_is_audible(app_name: str, process_name: "callable") -> bool:
    """``app_name`` 이름의 프로세스에서 지금 소리가 나는지.

    - 브라우저는 소리를 별도 프로세스에서 내므로 프로세스 id 가 아니라 실행 파일 이름으로 비교
    """
    wanted = app_name.lower()
    return any(
        peak > _SILENCE and Path(process_name(pid) or "").name.lower() == wanted
        for pid, peak in audio_sessions()
    )
