from __future__ import annotations

from typing import Callable, Sequence

from .models import StaticProfile
from .netsh import apply_commands, dhcp_commands, static_commands
from .shell import Runner, run_command
from .status import AdapterStatus, StatusError, read_status

Reader = Callable[[str], AdapterStatus]


def switch_to_dhcp(adapter: str, reader: Reader = read_status, runner: Runner = run_command) -> None:
    try:
        already = reader(adapter).dhcp
    except StatusError:
        already = False
    apply_commands(dhcp_commands(adapter, address_is_dhcp=already), runner=runner)


def switch_to_profile(adapter: str, profile: StaticProfile, runner: Runner = run_command) -> None:
    apply_commands(static_commands(adapter, profile), runner=runner)


def active_label(status: AdapterStatus, profiles: Sequence[StaticProfile]) -> str:
    if status.dhcp:
        return "DHCP"
    for profile in profiles:
        if profile.ip == status.ip and profile.prefix == status.prefix:
            return f"Fija: {profile.name}"
    return f"Fija: {status.ip or '—'}"
