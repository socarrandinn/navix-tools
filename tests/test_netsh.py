import subprocess

import pytest

from ipswitch.models import StaticProfile
from ipswitch.netsh import NetshError, apply_commands, dhcp_commands, static_commands
from ipswitch.shell import CommandResult

BASE = ["netsh", "interface", "ipv4"]
CASA = StaticProfile("Casa", "192.168.0.100", 24, "192.168.0.254", ("192.168.0.254", "8.8.8.8"))


def test_dhcp_commands():
    assert dhcp_commands("Wi-Fi", address_is_dhcp=False) == [
        BASE + ["set", "address", "Wi-Fi", "source=dhcp"],
        BASE + ["set", "dnsservers", "Wi-Fi", "source=dhcp"],
    ]


def test_dhcp_commands_skip_address_when_already_dhcp():
    assert dhcp_commands("Wi-Fi", address_is_dhcp=True) == [
        BASE + ["set", "dnsservers", "Wi-Fi", "source=dhcp"],
    ]


def test_static_commands_with_two_dns():
    assert static_commands("Wi-Fi", CASA) == [
        BASE + ["set", "address", "Wi-Fi", "source=static", "address=192.168.0.100",
                "mask=255.255.255.0", "gateway=192.168.0.254"],
        BASE + ["set", "dnsservers", "Wi-Fi", "source=static", "address=192.168.0.254",
                "register=primary", "validate=no"],
        BASE + ["add", "dnsservers", "Wi-Fi", "address=8.8.8.8", "index=2", "validate=no"],
    ]


def test_static_commands_without_dns_clears_dns():
    profile = StaticProfile("X", "10.0.0.5", 8, "10.0.0.1", ())
    assert static_commands("Wi-Fi", profile)[1] == BASE + [
        "set", "dnsservers", "Wi-Fi", "source=static", "address=none"]


def test_static_commands_validate_profile_first():
    bad = StaticProfile("X", "10.0.0.5", 8, "192.168.0.1", ())
    with pytest.raises(ValueError):
        static_commands("Wi-Fi", bad)


def test_adapter_name_with_spaces_is_single_argument():
    name = "Conexión de área local* 1"
    cmd = dhcp_commands(name, address_is_dhcp=False)[0]
    assert cmd[5] == name
    assert '"Conexión de área local* 1"' in subprocess.list2cmdline(cmd)


def test_apply_commands_runs_all_in_order():
    calls = []

    def runner(args):
        calls.append(list(args))
        return CommandResult(0, "Aceptar.")

    commands = static_commands("Wi-Fi", CASA)
    apply_commands(commands, runner=runner)
    assert calls == commands


def test_apply_commands_stops_and_reports_failing_command():
    calls = []

    def runner(args):
        calls.append(list(args))
        if "dnsservers" in args:
            return CommandResult(1, "El servidor DNS no es válido.")
        return CommandResult(0, "")

    with pytest.raises(NetshError) as info:
        apply_commands(static_commands("Wi-Fi", CASA), runner=runner)
    message = str(info.value)
    assert "dnsservers" in message
    assert "El servidor DNS no es válido." in message
    assert len(calls) == 2
