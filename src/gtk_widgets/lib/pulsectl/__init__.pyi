# Types for the pulsectl names that widgets/audio/ uses; the vendored code
# beside it is outside the gate (exclude in .claude/workshop.conf).
from collections.abc import Callable
from typing import override

from . import _pulsectl as _pulsectl

# Not exported by the package: only its values reach the widgets.
class _EnumValue:
    @override
    def __eq__(self, val: object) -> bool: ...
    @override
    def __hash__(self) -> int: ...

class PulseError(Exception): ...
class PulseIndexError(PulseError): ...
class PulseDisconnected(Exception): ...

class PulseVolumeInfo:
    values: list[float]
    def __init__(
        self, struct_or_values: list[float] | float, channels: int | None = None
    ) -> None: ...

class PulsePortInfo:
    name: str
    description: str
    available: _EnumValue
    priority: int

class PulseCardProfileInfo:
    name: str
    description: str
    priority: int
    available: int

class PulseCardPortInfo(PulsePortInfo):
    latency_offset: int

class PulseServerInfo:
    default_sink_name: str
    default_source_name: str

class _Device:
    index: int
    name: str
    description: str
    mute: int
    card: int
    state: _EnumValue
    proplist: dict[str, str]
    volume: PulseVolumeInfo
    base_volume: float
    channel_list: list[str]
    port_list: list[PulsePortInfo]
    port_active: PulsePortInfo | None

class PulseSinkInfo(_Device):
    monitor_source: int

class PulseSourceInfo(_Device):
    monitor_of_sink: int

class _Stream:
    index: int
    name: str
    mute: int
    client: int
    proplist: dict[str, str]
    volume: PulseVolumeInfo
    channel_list: list[str]

class PulseSinkInputInfo(_Stream):
    sink: int

class PulseSourceOutputInfo(_Stream):
    source: int

class PulseCardInfo:
    index: int
    name: str
    proplist: dict[str, str]
    port_list: list[PulseCardPortInfo]
    profile_list: list[PulseCardProfileInfo]
    profile_active: PulseCardProfileInfo

class PulseExtStreamRestoreInfo:
    name: str
    volume: PulseVolumeInfo
    channel_list: list[str]
    mute: int
    device: str | None
    def __init__(
        self,
        struct_or_name: str,
        volume: PulseVolumeInfo,
        channel_list: list[str],
        mute: bool = False,
        device: str | None = None,
    ) -> None: ...

class PulseEventInfo:
    t: _EnumValue
    facility: _EnumValue
    index: int

class Pulse:
    connected: bool
    @property
    def mainloop(self) -> _pulsectl.MainloopPointer: ...
    @property
    def context(self) -> _pulsectl.ContextPointer: ...
    def __init__(self, client_name: str) -> None: ...
    def close(self) -> None: ...
    def server_info(self) -> PulseServerInfo: ...
    def card_list(self) -> list[PulseCardInfo]: ...
    def sink_list(self) -> list[PulseSinkInfo]: ...
    def source_list(self) -> list[PulseSourceInfo]: ...
    def sink_input_list(self) -> list[PulseSinkInputInfo]: ...
    def source_output_list(self) -> list[PulseSourceOutputInfo]: ...
    def card_info(self, index: int) -> PulseCardInfo: ...
    def sink_info(self, index: int) -> PulseSinkInfo: ...
    def source_info(self, index: int) -> PulseSourceInfo: ...
    def sink_input_info(self, index: int) -> PulseSinkInputInfo: ...
    def source_output_info(self, index: int) -> PulseSourceOutputInfo: ...
    def stream_restore_list(self) -> list[PulseExtStreamRestoreInfo]: ...
    def stream_restore_write(
        self,
        obj: PulseExtStreamRestoreInfo,
        mode: str = "merge",
        apply_immediately: bool = False,
    ) -> None: ...
    def sink_volume_set(self, index: int, vol: PulseVolumeInfo) -> None: ...
    def source_volume_set(self, index: int, vol: PulseVolumeInfo) -> None: ...
    def sink_input_volume_set(self, index: int, vol: PulseVolumeInfo) -> None: ...
    def source_output_volume_set(self, index: int, vol: PulseVolumeInfo) -> None: ...
    def sink_mute(self, index: int, mute: bool) -> None: ...
    def source_mute(self, index: int, mute: bool) -> None: ...
    def sink_input_mute(self, index: int, mute: bool) -> None: ...
    def source_output_mute(self, index: int, mute: bool) -> None: ...
    def sink_default_set(self, name: str) -> None: ...
    def source_default_set(self, name: str) -> None: ...
    def sink_port_set(self, index: int, port: str) -> None: ...
    def source_port_set(self, index: int, port: str) -> None: ...
    def sink_input_move(self, index: int, sink: int) -> None: ...
    def source_output_move(self, index: int, source: int) -> None: ...
    def sink_input_kill(self, index: int) -> None: ...
    def source_output_kill(self, index: int) -> None: ...
    def card_profile_set_by_index(self, index: int, profile: str) -> None: ...
    def event_mask_set(self, *masks: str) -> None: ...
    def event_callback_set(
        self, func: Callable[[PulseEventInfo], object] | None
    ) -> None: ...
    def event_listen(self) -> None: ...
    def event_listen_stop(self) -> None: ...
