"""Entrada de cli\ipswitch.exe (de consola): CLI de ipswitch y registrador de la status line de Claude."""

import sys


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["statusline"]:
        import dock.statusline as statusline

        return statusline.main(argv[1:])
    import ipswitch.__main__ as cli

    return cli.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
