"""Escala de radios de borde, de afuera hacia adentro (cada capa interna más chica).

Los estilos usan marcadores @surface, @card, @control, @small y @icon que ``themed`` reemplaza.
"""

R_SURFACE = 22  # gota de la app y extremos de la barra
R_CARD = 14     # tarjetas dentro de la app, tabla de configuración
R_CONTROL = 10  # botones, campos, ítems de lista
R_SMALL = 6     # barras de progreso, casillas, pie de la gota al estirarse


def themed(style: str, icon: int = 30, header: int = 28) -> str:
    return (style.replace("@surface", str(R_SURFACE)).replace("@card", str(R_CARD))
            .replace("@control", str(R_CONTROL)).replace("@small", str(R_SMALL))
            .replace("@icon", str(icon // 2)).replace("@header", str(header // 2)))
