<p align="center">
  <img src="branding/navix-mark.svg" width="96" alt="Navix Tools">
</p>

<h1 align="center">Navix Tools</h1>

<p align="center">
  Una navaja de utilidades para Windows: una barra líquida pegada al borde de la pantalla,
  con una micro-app en cada hoja.
</p>

---

> **Antes se llamaba IPDock.** Al instalar Navix Tools se cierra y borra la versión anterior, y la
> configuración de `%APPDATA%\ipdock` se mueve sola a `%APPDATA%\navix`.

## Qué incluye

| App | Ícono | Qué hace |
| --- | --- | --- |
| **Cambio de IP** | `network` | Pasa el adaptador de red entre DHCP y perfiles de IP fija con un clic, **sin UAC en cada cambio**. |
| **Uso de IA** | `gauge` | Barras de 0 a 100 % de los límites de Claude (5 h y semana) y Codex, con el tiempo que falta para que se reinicien y avisos de Windows al llegar al umbral. |

Y la barra en sí:

- **Gota líquida** pegada al borde izquierdo, derecho o superior. Al abrir una app, esta brota de la barra como una gota que se separa, y se reabsorbe al cerrarla.
- **Bulto al pasar el mouse:** la barra se hincha bajo el ícono, más allá de su grosor, y el ícono crece adentro del bulto.
- **Arrastrar y pegar:** tirás de la barra desde el agarre y se estira como líquido; pasados unos 70 px se despega, y al soltarla se pega al borde más cercano.
- **Fijar** el panel abierto, o dejar que se cierre solo al sacar el mouse.
- Ícono en la **bandeja del sistema** con acceso a la configuración.

## Instalar

1. Descargá `Navix-Tools-Setup-1.1.0.exe` desde [Releases](https://github.com/socarrandinn/navix-tools/releases).
2. Ejecutalo. Pide permisos de administrador **una sola vez**: instala en `C:\Program Files\Navix Tools`, configura el helper de red y, si querés, lo inicia con Windows.

### Generar el instalador

Requiere Python 3.13 e [Inno Setup 6](https://jrsoftware.org/isinfo.php).

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
powershell -ExecutionPolicy Bypass -File build.ps1
```

## Usar desde el código

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m ipswitch install   # una vez, en una terminal de administrador
.\.venv\Scripts\pythonw -m dock              # abre la barra
```

### Barra

- **Clic** en un ícono abre esa app; otro clic la cierra; clic en otro ícono cambia de app.
- **Clic derecho** o engranaje: Configuración, Fijar/Soltar panel, Salir.

### Configuración

Engranaje de la barra → **Configuración** (también desde la bandeja del sistema):

| Sección | Opciones |
| --- | --- |
| General | Qué apps aparecen en la barra. |
| Planes de IA | Qué planes mostrar (Claude, Codex) y activar o desactivar el registrador de Claude. |
| Red (IP) | Adaptador y perfiles de IP fija. Guardar pide UAC una vez y escribe en `C:\ProgramData\ipswitch\config.json`. |
| Notificaciones | Umbral de aviso (85 % por defecto), una vez por ciclo de reinicio, y botón "Probar notificación". |
| Apariencia | Borde (derecha, izquierda, arriba), ancho de las apps y efecto líquido. |

La configuración de la barra se guarda en `%APPDATA%\navix\dock.json`:

```json
{"edge": "right", "width": 320, "tools": ["ip_switch", "ai_usage"], "pinned": false,
 "position": 0.5, "ai_sources": ["claude", "codex"], "liquid": true}
```

## Cambio de IP

### Cómo evita el UAC

`ipswitch install` (como administrador):

1. Crea `C:\ProgramData\ipswitch\config.json`, que solo los administradores pueden editar.
2. Copia el helper y un Python aislado a `C:\Program Files\ipswitch`.
3. Registra la tarea programada `IPSwitchHelper`, que aplica los cambios con privilegios y solo ejecuta esa copia protegida.

Así, un usuario sin permisos de administrador puede **elegir** un perfil, pero no **modificar** lo que se ejecuta con privilegios. Después de actualizar el código, volvé a ejecutar `install` para refrescar la copia.

### CLI

```powershell
.\.venv\Scripts\python -m ipswitch status
.\.venv\Scripts\python -m ipswitch dhcp
.\.venv\Scripts\python -m ipswitch profile Casa
.\.venv\Scripts\python -m ipswitch uninstall
```

### Perfiles

Desde Configuración → Red (IP), o editando `C:\ProgramData\ipswitch\config.json` como administrador:

```json
{
  "adapter": "Wi-Fi",
  "profiles": [
    {"name": "Casa", "ip": "192.168.0.100", "prefix": 24, "gateway": "192.168.0.254",
     "dns": ["192.168.0.254", "8.8.8.8"]}
  ]
}
```

## Uso de IA

Los datos se leen de fuentes locales; no se usa ninguna API ni credencial.

- **Codex:** se lee de `~/.codex/sessions` (el último dato que guardó Codex CLI).
- **Claude:** se lee de la [status line](https://code.claude.com/docs/en/statusline) de Claude Code. Se activa una vez con:

  ```powershell
  .\.venv\Scripts\python -m dock.statusline install    # encadena la status line que ya tenías
  .\.venv\Scripts\python -m dock.statusline uninstall  # la restaura
  ```

  El dato se actualiza mientras usás Claude Code.

## Agregar una herramienta

1. Creá `dock/tools/<nombre>.py` con una clase que herede de `dock.tool.Tool`:
   - `title`
   - `icon`: nombre de un SVG en `dock/assets/icons`, o 1-2 caracteres
   - `refresh_ms`
   - `create_widget()` y `refresh()`
2. Exponé `create_tool()` en ese módulo.
3. Sumá `<nombre>` a `tools` en `dock.json`.

## Estructura

```
dock/          barra, panel líquido, configuración y micro-apps (PySide6)
  tools/       una micro-app por archivo
ipswitch/      motor de red: netsh, helper con privilegios, tarea programada, CLI
installer/     script de Inno Setup
branding/      logo, ícono y guía de marca
tests/         pytest + pytest-qt
```

## Desarrollo

```powershell
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python -m pytest
```

## Créditos

- Íconos de interfaz: [Lucide](https://lucide.dev) (ISC), en `dock/assets/icons`.
- Marca Navix: ver [`branding/README.md`](branding/README.md).
