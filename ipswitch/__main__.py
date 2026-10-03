from __future__ import annotations

import argparse
import sys

from .actions import active_label
from .client import HelperError, request_switch
from .config import ConfigError, default_config_path, load_config
from .helper import run_helper, runtime_dir
from .install import InstallError, install, is_admin, uninstall
from .status import StatusError, describe, read_status


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ipswitch", description="Cambia entre DHCP y perfiles de IP fija")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="muestra el estado del adaptador")
    sub.add_parser("dhcp", help="cambia a DHCP")
    profile = sub.add_parser("profile", help="cambia a un perfil de IP fija")
    profile.add_argument("name")
    sub.add_parser("install", help="(admin) crea config, permisos y tarea programada")
    sub.add_parser("uninstall", help="(admin) borra la tarea programada")
    sub.add_parser("helper", help="uso interno de la tarea programada")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.command == "status":
            config = load_config(default_config_path())
            status = read_status(config.adapter)
            print(f"{config.adapter} ({active_label(status, config.profiles)})")
            print(describe(status))
            return 0
        if args.command in ("dhcp", "profile"):
            result = request_switch("dhcp") if args.command == "dhcp" else request_switch("profile", args.name)
            print(result.message)
            return 0 if result.ok else 1
        if args.command in ("install", "uninstall"):
            if not is_admin():
                print("Requiere una terminal abierta como administrador.", file=sys.stderr)
                return 1
            if args.command == "install":
                install()
                print(f"Instalado. Perfiles en {default_config_path()}")
            else:
                uninstall()
                print("Tarea eliminada.")
            return 0
        results = run_helper(runtime_dir(), default_config_path())
        return 0 if all(r.ok for r in results) else 1
    except (ConfigError, StatusError, HelperError, InstallError) as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
