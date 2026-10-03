# IP Switch

Cambia el adaptador de red de Windows entre DHCP y perfiles de IP fija, sin UAC en cada cambio.

## Instalación (una vez, terminal de administrador)

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python -m ipswitch install
```

Crea `C:\ProgramData\ipswitch\config.json` (solo administradores pueden editarlo), copia el
helper y un Python aislado a `C:\Program Files\ipswitch` y registra la tarea programada
`IPSwitchHelper`, que aplica los cambios con privilegios. La tarea solo ejecuta esa copia, que un
usuario sin admin no puede modificar.

Después de actualizar el código, ejecutá `install` de nuevo para refrescar la copia.

## Uso (terminal normal)

```powershell
.\.venv\Scripts\python -m ipswitch status
.\.venv\Scripts\python -m ipswitch dhcp
.\.venv\Scripts\python -m ipswitch profile Casa
```

## Perfiles

Editar `C:\ProgramData\ipswitch\config.json` con un editor abierto como administrador:

```json
{
  "adapter": "Wi-Fi",
  "profiles": [
    {"name": "Casa", "ip": "192.168.0.100", "prefix": 24, "gateway": "192.168.0.254", "dns": ["192.168.0.254", "8.8.8.8"]}
  ]
}
```

## Desinstalar

```powershell
.\.venv\Scripts\python -m ipswitch uninstall
```

## Desarrollo

```powershell
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python -m pytest
```

## Panel (IPDock)

```powershell
.\.venv\Scripts\pythonw -m dock
```

Barra chica (40 px) pegada al borde de la pantalla, estilo dock de mac/linux, con un ícono por micro-app:

- Clic en un ícono despliega esa app al lado de la barra; clic de nuevo la cierra; clic en otro ícono cambia de app.
- Se cierra sola al sacar el mouse, salvo que esté fijada con 📌. ✕ cierra IPDock.
- Arrastrá la barra (desde el `⋯` o el fondo) para moverla: al soltarla se pega al borde izquierdo o derecho más cercano.
- Clic derecho en la barra: Fijar panel / Salir.
- En la app de IP, el botón del modo activo (DHCP o perfil) aparece resaltado.

Apps incluidas:

- 🌐 **Cambio de IP**: DHCP o perfiles de IP fija (requiere `python -m ipswitch install`).
- 📊 **Uso de IA**: barras 0-100 % de los límites de Claude (5 h y semana) y Codex, con cuándo reinician.
  - Codex: se lee de `~/.codex/sessions` (el último dato que guardó Codex CLI).
  - Claude: se lee de la status line oficial de Claude Code. Activarlo una vez con
    `.\.venv\Scripts\python -m dock.statusline install` (encadena la status line que ya tenías;
    `uninstall` la restaura). El dato se actualiza mientras usás Claude Code.

Agregar una app: crear `dock/tools/<nombre>.py` con una clase que herede `dock.tool.Tool`
(`title`, `icon`, `refresh_ms`, `create_widget()`, `refresh()`) y `create_tool()`, y sumar
`<nombre>` a `tools` en `dock.json`.

Config en `%APPDATA%\ipdock\dock.json` (se guarda solo al mover o fijar):

```json
{"edge": "right", "width": 320, "backdrop": "acrylic", "tools": ["ip_switch"], "pinned": false, "position": 0.5}
```
