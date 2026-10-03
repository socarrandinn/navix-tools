"""Entrada de IPDock.exe (sin consola): la barra, más el helper elevado y el guardado de perfiles."""

import sys

ELEVATED_COMMANDS = {"helper", "save-config"}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] in ELEVATED_COMMANDS:
        import ipswitch.__main__ as cli

        return cli.main(argv)
    import dock.__main__ as dock

    return dock.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
