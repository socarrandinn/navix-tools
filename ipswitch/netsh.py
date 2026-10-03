from __future__ import annotations

import subprocess

from .models import StaticProfile
from .shell import Runner, run_command

BASE = ["netsh", "interface", "ipv4"]


class NetshError(RuntimeError):
    pass


def dhcp_commands(adapter: str, address_is_dhcp: bool) -> list[list[str]]:
    commands = []
    if not address_is_dhcp:
        commands.append(BASE + ["set", "address", adapter, "source=dhcp"])
    commands.append(BASE + ["set", "dnsservers", adapter, "source=dhcp"])
    return commands


def static_commands(adapter: str, profile: StaticProfile) -> list[list[str]]:
    profile.validate()
    commands = [
        BASE + ["set", "address", adapter, "source=static", f"address={profile.ip}",
                f"mask={profile.netmask}", f"gateway={profile.gateway}"],
    ]
    if not profile.dns:
        commands.append(BASE + ["set", "dnsservers", adapter, "source=static", "address=none"])
        return commands
    first, *rest = profile.dns
    commands.append(BASE + ["set", "dnsservers", adapter, "source=static", f"address={first}",
                            "register=primary", "validate=no"])
    for index, server in enumerate(rest, start=2):
        commands.append(BASE + ["add", "dnsservers", adapter, f"address={server}",
                                f"index={index}", "validate=no"])
    return commands


def apply_commands(commands: list[list[str]], runner: Runner = run_command) -> None:
    for command in commands:
        result = runner(command)
        if result.returncode != 0:
            raise NetshError(
                f"Falló: {subprocess.list2cmdline(command)}\n\n{result.output}"
            )
