# IPDock

Barra lateral para Windows con micro-apps: cambio rápido entre DHCP e IP fija (sin UAC en cada
cambio) y uso de los planes de Claude y Codex.

## Instalar la v1

Descargá `IPDock-Setup-1.0.0.exe` y ejecutalo (pide permisos de administrador una vez). Instala en
`C:\Program Files\IPDock`, configura el helper de red y, si querés, lo inicia con Windows.

Para generar el instalador desde el código:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
powershell -ExecutionPolicy Bypass -File build.ps1   # requiere Inno Setup 6
```

## Desde el código (IP Switch)

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

Gota líquida oscura (40 px) pegada al borde izquierdo, derecho o **superior** de la pantalla,
con un ícono por micro-app:

- Clic en un ícono despliega esa app hacia adentro de la pantalla; clic de nuevo la cierra; clic en otro ícono cambia de app.
- Se cierra sola al sacar el mouse, salvo que esté fijada (ícono pin). La X cierra IPDock.
- Arrastrá la gota desde los puntos de agarre: al soltarla se pega al borde más cercano
  (en el borde superior la barra es horizontal y la app se abre hacia abajo).
- Clic derecho: Fijar panel / Salir.
- Efecto líquido: al abrir una app, brota de la barra como una gota que se separa (y se reabsorbe al
  cerrar); al tirar de la barra se estira como líquido y, pasados ~70 px, se despega del borde;
  al pasar el mouse la gota ondula.
- Íconos: [Lucide](https://lucide.dev) (ISC), en `dock/assets/icons`.

Apps incluidas:

- **Cambio de IP** (ícono `network`): DHCP o perfiles de IP fija (requiere `python -m ipswitch install`).
- **Uso de IA** (ícono `gauge`): barras 0-100 % de los límites de Claude (5 h y semana) y Codex, con cuándo reinician.
  - Codex: se lee de `~/.codex/sessions` (el último dato que guardó Codex CLI).
  - Claude: se lee de la status line oficial de Claude Code. Activarlo una vez con
    `.\.venv\Scripts\python -m dock.statusline install` (encadena la status line que ya tenías;
    `uninstall` la restaura). El dato se actualiza mientras usás Claude Code.

Agregar una app: crear `dock/tools/<nombre>.py` con una clase que herede `dock.tool.Tool`
(`title`, `icon` = nombre de un SVG en `dock/assets/icons` o 1-2 caracteres, `refresh_ms`, `create_widget()`, `refresh()`) y `create_tool()`, y sumar
`<nombre>` a `tools` en `dock.json`.

### Configuración

Engranaje de la barra → Configuración (también desde el ícono de la bandeja del sistema):

- **General**: qué apps aparecen en la barra.
- **Planes de IA**: qué planes mostrar (Claude, Codex) y activar/desactivar el registrador de Claude.
- **Red (IP)**: adaptador y perfiles de IP fija (agregar, editar, quitar). Guardar pide UAC una vez:
  los perfiles se validan y se escriben en `C:\ProgramData\ipswitch\config.json` con permisos de admin.
- **Notificaciones**: aviso de Windows cuando un plan llega al umbral (85 % por defecto), una vez por
  ciclo de reinicio; botón "Probar notificación".
- **Apariencia**: borde (derecha, izquierda, arriba), ancho de las apps y efecto líquido.

Config en `%APPDATA%\ipdock\dock.json` (se guarda solo al mover o fijar):

```json
{"edge": "right", "width": 320, "tools": ["ip_switch", "ai_usage"], "pinned": false, "position": 0.5,
 "ai_sources": ["claude", "codex"], "liquid": true}
```
