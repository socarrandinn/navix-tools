# IP Switch

Cambia el adaptador de red de Windows entre DHCP y perfiles de IP fija, sin UAC en cada cambio.

## Instalación (una vez, terminal de administrador)

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python -m ipswitch install
```

Crea `C:\ProgramData\ipswitch\config.json` (solo administradores pueden editarlo) y la tarea
programada `IPSwitchHelper`, que aplica los cambios con privilegios.

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
