from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Sequence

from .shell import CommandResult, Runner, run_command


class StatusError(RuntimeError):
    pass


@dataclass(frozen=True)
class AdapterStatus:
    dhcp: bool
    ip: str | None
    prefix: int | None
    gateway: str | None
    dns: tuple[str, ...]


def utf8_runner(args: Sequence[str]) -> CommandResult:
    # PowerShell escribe registros de progreso (CLIXML) en stderr aunque el comando funcione.
    return run_command(args, encoding="utf-8", stdout_only_on_success=True)


def ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def status_script(adapter: str) -> str:
    return "\n".join([
        "[Console]::OutputEncoding = [Text.Encoding]::UTF8",
        "$ProgressPreference = 'SilentlyContinue'",
        "$ErrorActionPreference = 'Stop'",
        f"$a = {ps_quote(adapter)}",
        "$i = Get-NetIPInterface -InterfaceAlias $a -AddressFamily IPv4",
        "$ip = Get-NetIPAddress -InterfaceAlias $a -AddressFamily IPv4 -ErrorAction SilentlyContinue | Select-Object -First 1",
        "$gw = Get-NetRoute -InterfaceAlias $a -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue | Select-Object -First 1",
        "$dns = (Get-DnsClientServerAddress -InterfaceAlias $a -AddressFamily IPv4).ServerAddresses",
        "[pscustomobject]@{ dhcp = [string]$i.Dhcp; ip = $ip.IPAddress; prefix = $ip.PrefixLength;"
        " gateway = $gw.NextHop; dns = @($dns) } | ConvertTo-Json -Compress",
    ])


ADAPTERS_SCRIPT = "\n".join([
    "[Console]::OutputEncoding = [Text.Encoding]::UTF8",
    "$ProgressPreference = 'SilentlyContinue'",
    "ConvertTo-Json -Compress -InputObject @(Get-NetAdapter | ForEach-Object Name)",
])


def powershell_args(script: str) -> list[str]:
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    return ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded]


def _as_tuple(value) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(v) for v in value)


def parse_status(text: str) -> AdapterStatus:
    try:
        raw = json.loads(text)
        return AdapterStatus(
            dhcp=str(raw["dhcp"]) == "Enabled",
            ip=raw.get("ip"),
            prefix=int(raw["prefix"]) if raw.get("prefix") is not None else None,
            gateway=raw.get("gateway") or None,
            dns=_as_tuple(raw.get("dns")),
        )
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise StatusError(f"Respuesta inesperada de PowerShell:\n{text}") from exc


def read_status(adapter: str, runner: Runner = utf8_runner) -> AdapterStatus:
    result = runner(powershell_args(status_script(adapter)))
    if result.returncode != 0:
        raise StatusError(f"No se pudo leer el adaptador {adapter}:\n{result.output}")
    return parse_status(result.output)


def list_adapters(runner: Runner = utf8_runner) -> list[str]:
    result = runner(powershell_args(ADAPTERS_SCRIPT))
    if result.returncode != 0:
        raise StatusError(f"No se pudieron listar adaptadores:\n{result.output}")
    try:
        return list(_as_tuple(json.loads(result.output)))
    except ValueError as exc:
        raise StatusError(f"Respuesta inesperada de PowerShell:\n{result.output}") from exc


def describe(status: AdapterStatus) -> str:
    dash = "—"
    ip = f"{status.ip}/{status.prefix}" if status.ip else dash
    return "\n".join([
        f"Modo:    {'DHCP' if status.dhcp else 'IP fija'}",
        f"IP:      {ip}",
        f"Gateway: {status.gateway or dash}",
        f"DNS:     {', '.join(status.dns) if status.dns else dash}",
    ])
