from __future__ import annotations

import ipaddress
from dataclasses import dataclass


class ProfileError(ValueError):
    pass


@dataclass(frozen=True)
class StaticProfile:
    name: str
    ip: str
    prefix: int
    gateway: str
    dns: tuple[str, ...] = ()

    @property
    def netmask(self) -> str:
        return str(ipaddress.IPv4Network(f"0.0.0.0/{self.prefix}").netmask)

    def validate(self) -> None:
        if not self.name.strip():
            raise ProfileError("El perfil necesita un nombre")
        if not 1 <= self.prefix <= 30:
            raise ProfileError(f"[{self.name}] prefijo inválido: {self.prefix} (usar 1-30)")
        try:
            iface = ipaddress.IPv4Interface(f"{self.ip}/{self.prefix}")
        except ValueError as exc:
            raise ProfileError(f"[{self.name}] IP inválida: {self.ip}") from exc
        network = iface.network
        if iface.ip == network.network_address:
            raise ProfileError(f"[{self.name}] {iface.ip} es la dirección de red de {network}")
        if iface.ip == network.broadcast_address:
            raise ProfileError(f"[{self.name}] {iface.ip} es la dirección broadcast de {network}")
        try:
            gateway = ipaddress.IPv4Address(self.gateway)
        except ValueError as exc:
            raise ProfileError(f"[{self.name}] Gateway inválido: {self.gateway}") from exc
        if gateway not in network:
            raise ProfileError(f"[{self.name}] Gateway {gateway} fuera de la red {network}")
        if gateway == iface.ip:
            raise ProfileError(f"[{self.name}] Gateway igual a la IP {iface.ip}")
        for server in self.dns:
            try:
                ipaddress.IPv4Address(server)
            except ValueError as exc:
                raise ProfileError(f"[{self.name}] DNS inválido: {server}") from exc
