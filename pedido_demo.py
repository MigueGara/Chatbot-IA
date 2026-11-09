"""Pedido simulado, guardado únicamente durante la sesión de Streamlit."""

from dataclasses import dataclass, replace
from html import escape
from pathlib import Path
from uuid import uuid4

import streamlit as st

from belen import PLATOS, soles

EXTRAS = {"Huevo adicional": 200, "Pollo adicional": 400, "Verduras extra": 200}
NIVELES_PICANTE = ("Sin picante", "Suave", "Medio", "Picante")
PRECIO_PERSONALIZADO = 2690
_MAX_CANTIDAD = 99
_ESTILOS = Path(__file__).parent / "static" / "pedido-demo.css"


@dataclass(frozen=True)
class _Linea:
    clave: str
    nombre: str
    detalle: tuple[str, ...]
    precio: int
    cantidad: int = 1


def _lineas():
    return st.session_state.setdefault("pedido_demo_lineas", {})


def _editar():
    st.session_state["pedido_demo_confirmado"] = False


def _agregar(linea):
    lineas = _lineas()
    for identificador, actual in lineas.items():
        if replace(actual, cantidad=linea.cantidad) == linea:
            cantidad = min(_MAX_CANTIDAD, actual.cantidad + linea.cantidad)
            lineas[identificador] = replace(actual, cantidad=cantidad)
            break
    else:
        lineas[uuid4().hex] = linea
    _editar()


def agregar_plato(clave, cantidad=1, picante="", extras=()):
    """Agrega un plato y sus opciones ilustrativas al pedido."""
    plato = PLATOS.get(clave) if isinstance(clave, str) else None
    if not plato or type(cantidad) is not int or not 1 <= cantidad <= _MAX_CANTIDAD:
        return False
    extras = extras if isinstance(extras, (list, tuple)) else ()
    elegidos = tuple(extra for extra in EXTRAS if extra in extras)
    detalle = (picante,) if picante in NIVELES_PICANTE else ()
    precio = plato["precio"] + sum(EXTRAS[extra] for extra in elegidos)
    _agregar(_Linea(clave, plato["nombre"], detalle + elegidos, precio, cantidad))
    return True


def agregar_personalizado(combinacion):
    """Agrega una combinación al precio de referencia de la demo."""
    if not isinstance(combinacion, dict):
        return False
    base = combinacion.get("Base")
    if not isinstance(base, str) or not base.strip():
        return False

    detalle = []
    for clave in ("Base", "Proteína", "Verduras", "Salsa"):
        valor = combinacion.get(clave)
        opciones = valor if isinstance(valor, (list, tuple)) else (valor,)
        detalle.extend(opcion.strip()[:60] for opcion in opciones if isinstance(opcion, str) and opcion.strip())
    _agregar(_Linea("creado", "Mi plato personalizado", tuple(detalle), PRECIO_PERSONALIZADO))
    return True


def total_pedido():
    return sum(linea.precio * linea.cantidad for linea in _lineas().values())


def cantidad_pedido():
    return sum(linea.cantidad for linea in _lineas().values())


def resumen_pedido():
    return tuple(
        {
            "nombre": linea.nombre,
            "cantidad": linea.cantidad,
            "precio_unitario": linea.precio,
            "detalle": linea.detalle,
        }
        for linea in _lineas().values()
    )


def _cambiar_cantidad(identificador, cambio):
    lineas = _lineas()
    linea = lineas.get(identificador)
    if linea is None:
        return
    cantidad = min(_MAX_CANTIDAD, linea.cantidad + cambio)
    if cantidad < 1:
        del lineas[identificador]
    else:
        lineas[identificador] = replace(linea, cantidad=cantidad)
    _editar()


def _eliminar(identificador):
    _lineas().pop(identificador, None)
    _editar()


def _vaciar():
    _lineas().clear()
    _editar()


def _confirmar():
    if cantidad_pedido():
        st.session_state["pedido_demo_confirmado"] = True


def _mostrar_linea(identificador, linea, foto):
    with st.container(key=f"pedido_linea_{identificador}"):
        with st.container(horizontal=True, vertical_alignment="top", gap="small", key=f"pedido_ficha_{identificador}"):
            st.html(f'<div class="pedido-foto">{foto(linea.clave)}</div>', width=67)
            detalle = ", ".join(linea.detalle)
            st.html(
                f'<div class="pedido-texto"><h2>{escape(linea.nombre)}</h2>'
                f'<p>{escape(detalle or "Preparación clásica")}</p></div>'
            )
            st.button("✕", key=f"pedido_eliminar_{identificador}", help=f"Quitar {linea.nombre}",
                      on_click=_eliminar, args=(identificador,))
        with st.container(horizontal=True, vertical_alignment="center", gap="xsmall", key=f"pedido_cantidad_{identificador}"):
            st.button("−", key=f"pedido_menos_{identificador}", help=f"Reducir cantidad de {linea.nombre}",
                      on_click=_cambiar_cantidad, args=(identificador, -1))
            st.html(f'<span class="pedido-numero" aria-label="Cantidad: {linea.cantidad}">{linea.cantidad}</span>', width=23)
            st.button("+", key=f"pedido_mas_{identificador}", help=f"Aumentar cantidad de {linea.nombre}",
                      disabled=linea.cantidad >= _MAX_CANTIDAD,
                      on_click=_cambiar_cantidad, args=(identificador, 1))
            st.html(f'<span class="pedido-precio">{soles(linea.precio * linea.cantidad)}</span>')


def mostrar_pedido(foto, abrir_menu):
    """Presenta el pedido y sus controles dentro de la vista de la demo."""
    st.html(_ESTILOS)
    lineas = _lineas()
    with st.container(key="pedido_demo"):
        with st.container(horizontal=True, vertical_alignment="center", gap="small", key="pedido_encabezado"):
            st.html('<h1 class="pedido-titulo">Tu pedido</h1>')
            st.button("Vaciar", icon=":material/delete_outline:", key="pedido_vaciar",
                      on_click=_vaciar, disabled=not lineas)

        if not lineas:
            st.html(
                '<div class="pedido-vacio"><strong>Tu pedido está vacío</strong>'
                '<p>Explora la carta y agrega lo que se te antoje.</p></div>'
            )
            st.button("Ver la carta", type="primary", width="stretch", key="pedido_menu_vacio", on_click=abrir_menu)
        else:
            for identificador, linea in lineas.items():
                _mostrar_linea(identificador, linea, foto)
            total = soles(total_pedido())
            st.html(
                '<div class="pedido-totales">'
                f'<p><span>Subtotal</span><span>{total}</span></p>'
                f'<p class="pedido-total"><strong>Total</strong><strong>{total}</strong></p>'
                '</div>'
            )
            if st.session_state.get("pedido_demo_confirmado", False):
                st.success("Pedido simulado. Puedes seguir editando o volver a la carta.")
            else:
                st.button("Continuar con el pedido", type="primary", width="stretch", key="pedido_confirmar",
                          on_click=_confirmar)
            st.button("Seguir eligiendo platos", icon=":material/add_circle_outline:", width="stretch",
                      key="pedido_menu", on_click=abrir_menu)

        st.html('<p class="pedido-nota">Pedido simulado · precios ilustrativos · sin compra ni cobro.</p>')
