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

- Círculo azul "IP" de 50 px pegado al borde de la pantalla.
- Pasá el mouse (o hacé clic) para abrir el panel; se cierra solo al sacar el mouse.
- Arrastrá el círculo para moverlo: al soltarlo se pega al borde izquierdo o derecho más cercano.
- 📌 deja el panel fijo abierto; ✕ cierra la app. Clic derecho en el círculo: Fijar panel / Salir.
- El botón del modo activo (DHCP o perfil) aparece resaltado.

Config en `%APPDATA%\ipdock\dock.json` (se guarda solo al mover o fijar):

```json
{"edge": "right", "width": 320, "backdrop": "acrylic", "tools": ["ip_switch"], "pinned": false, "position": 0.5}
```
