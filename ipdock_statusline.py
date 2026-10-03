"""Punto de entrada para la statusLine de Claude Code (se ejecuta desde cualquier carpeta)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dock.statusline import main  # noqa: E402

raise SystemExit(main())
