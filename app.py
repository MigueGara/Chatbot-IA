"""Interfaz móvil del prototipo académico China Wok AI."""

import csv
import io
import os
import re
from decimal import Decimal, InvalidOperation
from html import escape
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import streamlit as st

from avatar import mostrar_belen
from belen import (
    PLATOS, Respuesta, destino_navegacion, normalizar, nuevo_perfil, recomendar, responder, soles,
)
from ia import Inteligencia
from pedido_demo import (
    EXTRAS, NIVELES_PICANTE, PRECIO_PERSONALIZADO, agregar_personalizado,
    actualizar_cantidad, agregar_plato, cantidad_pedido, mostrar_pedido, resumen_pedido, total_pedido,
)
from voz_live import (
    ErrorLiveAPI, MODELO_LIVE, crear_configuracion_websocket, crear_token_live,
)

ROOT = Path(__file__).parent
st.set_page_config(page_title="China Wok AI · Belén", page_icon="🥢", layout="wide")
st.html(ROOT / "static/prototipo.css")
st.html(ROOT / "static/conversacion.css")
S = st.session_state

FOTOS = ("chaufa-pollo", "tallarin-pollo", "lomo", "tipakay", "chaufa-mariscos", "tofu", "duo", "familiar", "creado")
FOTOS_INGREDIENTES = {
    "Arroz blanco": (908, 126, 44, 36), "Arroz chaufa": (963, 129, 42, 32), "Tallarines": (1015, 128, 44, 35),
    "Pollo": (25, 457, 44, 27), "Carne": (88, 457, 44, 27), "Langostinos": (24, 504, 47, 27),
    "Tofu": (151, 504, 45, 27), "Sin proteína adicional": (908, 126, 44, 36),
    "Sin cebolla": (241, 455, 40, 27), "Brócoli": (303, 455, 46, 28), "Zanahoria": (365, 456, 45, 27),
    "Col": (242, 504, 42, 27), "Pimiento": (303, 504, 45, 28), "Champiñones": (366, 504, 44, 27),
    "Cebolla": (241, 455, 40, 27),
    "Sillao": (454, 457, 33, 25), "Ostión": (497, 457, 33, 25), "Teriyaki": (540, 457, 33, 25),
    "Tipakay": (454, 505, 33, 25), "Picante": (497, 505, 33, 25), "Sin salsa": (540, 505, 33, 25),
}
ICONOS_INGREDIENTES = (
    '<path d="M4 12h16c-.6 4.4-3.1 7-8 7s-7.4-2.6-8-7zm3-2c1.6-2.9 8.4-2.9 10 0M9 5h6"/>',
    '<path d="M16 4c3 0 5 2.4 5 5 0 3.1-2.8 5.2-5.5 5.2L11 18l-1.7-.3-.3 1.6c-.9 1-2.7.8-3.4-.4-.9-.5-1.2-2-.4-2.9l1.5-.3.3-1.6 3.8-4.1C10.8 6.9 12.8 4 16 4z"/>',
    '<path d="M18.2 14.6c0 3.2-2.7 5.5-6.2 5.5s-6.2-2.3-6.2-5.5C5.8 10.7 9.4 4 12 4s6.2 6.7 6.2 10.6z"/>',
    '<path d="M20 4c-7.2 0-13 2.4-13 8.4 0 2.8 2 4.6 4.7 4.6C17.5 17 20 10.7 20 4zM4 20l10.4-10.5"/>',
)
PASOS = (
    ("Base", "¿Con qué empezamos?", ["Arroz chaufa", "Arroz blanco", "Tallarines"]),
    ("Proteína", "¿Qué proteína te gustaría?", ["Pollo", "Carne", "Langostinos", "Tofu", "Sin proteína adicional"]),
    ("Verduras", "¿Qué verduras te gustaría agregar?", ["Sin cebolla", "Brócoli", "Zanahoria", "Col", "Pimiento", "Champiñones", "Cebolla"]),
    ("Salsa", "¿Deseas agregar alguna salsa?", ["Sillao", "Ostión", "Teriyaki", "Tipakay", "Picante", "Sin salsa"]),
)
CATEGORIAS_GUSTO = {
    "Arroces": "arroz", "Tallarines": "tallarines", "Carnes": "carne", "Pollo": "pollo", "Vegetales": "verduras",
}
CONSEJOS = (
    "Elige entre el sabor tostado del chaufa, arroz blanco o tallarines.",
    "Con la base lista, ahora puedes decidir qué proteína le queda mejor.",
    "Puedes mezclar varias verduras para darle color y textura a tu plato.",
    "Un toque dulce, salado o picante cambia el sabor de tu combinación.",
)


def nueva_conversacion():
    S.session_id = uuid4().hex
    S.perfil = nuevo_perfil()
    S.resumen = ""
    S.historial = []
    S.metricas = []
    S.platos_sugeridos = ()
    S.pop("pendiente", None)
    S.pop("consulta_en_curso", None)
    S.gesto_avatar = "lista"
    S.respuesta_avatar = ""


def iniciar_llamada():
    ir("Belén")
    S.modo_chat = "voz"
    S.vista_voz_compacta = False
    S.llamada_activa = True
    S.live_token = ""
    S.live_connected = False
    S.live_tool_response = None
    S.live_api_error = ""
    S.gesto_avatar = "saludo"
    S.respuesta_avatar = "" if S.historial else (
        "Hola, soy Belén. Te acompaño a elegir algo rico. "
        "¿Qué te gustaría comer hoy?"
    )


def finalizar_llamada():
    S.llamada_activa = False
    S.live_token = ""
    S.live_connected = False
    S.live_tool_response = None
    S.live_api_error = ""
    S.modo_chat = "texto"
    S.vista_voz_compacta = False
    S.gesto_avatar = "lista"
    S.respuesta_avatar = ""
    S.pop("pantalla_llamada_pendiente", None)
    S.pop("marca_chat", None)


def cambiar_vista_voz():
    S.vista_voz_compacta = not S.get("vista_voz_compacta", False)
    S.pop("marca_chat", None)


if "vista" not in S:
    S.vista = "Inicio"
    S.detalle = None
    S.paso = -1
    S.combinacion = {}
    nueva_conversacion()
S.setdefault("modo_chat", "texto")
S.setdefault("llamada_activa", False)


def ir(vista):
    if vista != S.vista or S.detalle:
        S.subir_pantalla = True
    if S.get("llamada_activa") and vista != S.vista and vista in ("Menú", "Crear", "Pedido"):
        S.pantalla_llamada_pendiente = (vista, None)
    if vista == "Belén" and S.vista != "Belén":
        S.origen_chat = (S.vista, S.detalle)
        S.contexto_chat = contexto_pantalla()
        if S.get("llamada_activa"):
            S.vista_voz_compacta = True
    S.vista = vista
    S.detalle = None


def abrir_detalle(clave):
    if S.get("llamada_activa") and (S.vista != "Menú" or S.detalle != clave):
        S.pantalla_llamada_pendiente = ("Menú", clave)
    S.vista = "Menú"
    S.detalle = clave
    S.subir_pantalla = True


def abrir_menu():
    ir("Menú")


def abrir_busqueda():
    ir("Menú")
    S.mostrar_busqueda = True


def abrir_creador():
    ir("Crear")


def seleccionar_categoria(categoria):
    S.filtro_menu = categoria


def alternar_favorito(clave):
    favoritos = S.setdefault("favoritos", [])
    if clave in favoritos:
        favoritos.remove(clave)
    else:
        favoritos.append(clave)


def boton_favorito(clave, lugar):
    favorito = clave in S.get("favoritos", [])
    st.button("Quitar de favoritos" if favorito else "Guardar en favoritos", icon=":material/favorite:",
              key=f"favorito_{lugar}_{clave}", type="primary" if favorito else "secondary",
              on_click=alternar_favorito, args=(clave,))


def agregar_desde_ficha(clave, cantidad, picante, extras):
    agregar_plato(clave, cantidad, picante, extras)
    ir("Pedido")


def agregar_wok():
    combinacion = S.combinacion.copy()
    cantidad = combinacion.get("Cantidad de salsa")
    if cantidad and combinacion.get("Salsa") not in (None, "Sin salsa"):
        combinacion["Salsa"] += f" ({cantidad.lower()})"
    if agregar_personalizado(combinacion):
        S.combinacion = {}
        S.paso = -1
        S.pop("solicitud_crear", None)
        ir("Pedido")


def contexto_pantalla():
    if S.vista == "Menú":
        return {"plato_id": S.detalle} if S.detalle else {"categoria": S.get("filtro_menu", "Todas")}
    if S.vista == "Crear":
        en_paso = 0 <= S.paso < len(PASOS)
        etapa = PASOS[S.paso][0] if en_paso else "Revisión"
        opciones = PASOS[S.paso][2] if en_paso else []
        return {"etapa": etapa, "opciones": opciones, "seleccion": S.combinacion.copy()}
    return {}


def regresar_del_chat():
    S.vista, S.detalle = S.get("origen_chat", ("Inicio", None))
    S.subir_pantalla = True


def iniciar_pregunta(pregunta):
    ir("Belén")
    S.pendiente = pregunta


def variable(clave, defecto=""):
    valor = os.getenv(clave)
    if valor is not None:
        return valor.strip()
    try:
        return str(st.secrets.get(clave, defecto)).strip()
    except FileNotFoundError:
        return defecto


@st.cache_resource(show_spinner=False)
def inteligencia(config):
    return Inteligencia(config)


def globo(encabezado, texto):
    titulo = f"<strong>{escape(encabezado)}</strong>" if encabezado else ""
    return f'<div class="globo-belen">{titulo}<p>{escape(texto)}</p></div>'


def banda_belen(texto, clave, titulo="", gesto="oferta"):
    with st.container(key=f"banda_{clave}"):
        with st.container(key=f"figura_{clave}"):
            mostrar_belen(gesto=gesto, sesion=S.session_id, modo="banda", clave=f"belen_{clave}")
        st.html(globo(titulo, texto))


def portada():
    with st.container(key="portada_prototipo"):
        with st.container(key="figura_inicio"):
            mostrar_belen(gesto="saludo", sesion=S.session_id, modo="portada", clave="belen_inicio")
        st.html(globo("¡Hola!", "Soy Belén, tu asistente de China Wok. ¿Te gustaría elegir un plato o crear tu propia combinación?"))
        with st.container(key="acciones_inicio"):
            st.button("Elegir un plato", icon=":material/ramen_dining:", on_click=abrir_menu,
                      type="primary", key="inicio_carta", width="stretch")
            st.button("Crear mi propio plato", icon=":material/skillet:", on_click=abrir_creador,
                      key="inicio_crear", width="stretch")
            st.button("Chatear con Belén", icon=":material/chat:", on_click=ir,
                      args=("Belén",), key="inicio_chat", width="stretch")
        st.html('<p class="nota-inicio">Asistente con inteligencia artificial</p>')


def foto(clave, grande=False):
    fila, columna = divmod(FOTOS.index(clave), 3)
    estilo = f"--foto-x:{50 * columna}%;--foto-y:{50 * fila}%"
    clase = "foto-plato foto-grande" if grande else "foto-plato"
    return f'<div class="{clase}" aria-hidden="true"><span style="{estilo}"></span></div>'


def foto_ingrediente(opcion):
    x, y, ancho, alto = FOTOS_INGREDIENTES[opcion]
    estilo = (f"aspect-ratio:{ancho}/{alto};background-size:{106800/ancho:.2f}% {69200/alto:.2f}%;"
              f"background-position:{100*x/(1068-ancho):.2f}% {100*y/(692-alto):.2f}%")
    return f'<div class="foto-ingrediente" style="{estilo}" aria-hidden="true"></div>'


def tarjetas(claves, grupo):
    with st.container(key=f"cuadricula_{grupo}"):
        for inicio in range(0, len(claves), 2):
            columnas = st.columns(2, gap="small")
            for columna, clave in zip(columnas, claves[inicio:inicio + 2]):
                plato = PLATOS[clave]
                with columna, st.container(key=f"card_{grupo}_{clave}"):
                    st.html(f"""
                      {foto(clave)}
                      <div class="tarjeta-texto">
                        <h3>{escape(plato['nombre'])}</h3>
                        <p>{escape(plato['descripcion'])}</p>
                        <strong>{soles(plato['precio'])}</strong>
                      </div>
                    """)
                    st.button("Ver plato", key=f"{grupo}_plato_{clave}", on_click=abrir_detalle,
                              args=(clave,), width="stretch")
                    st.button("Agregar", key=f"{grupo}_agregar_{clave}", on_click=agregar_plato,
                              args=(clave,), type="primary", icon=":material/add:")
                    boton_favorito(clave, "carta")


def menu():
    if S.detalle:
        detalle_plato(S.detalle)
        return

    banda_belen("Aquí tienes nuestro menú. Explora las categorías o dime qué te gustaría.", "menu")
    categorias = (
        ("Favoritos", "star"), ("Arroces", "rice_bowl"), ("Pollo", "restaurant"),
        ("Carnes", "set_meal"), ("Mariscos", "dinner_dining"),
    )
    categoria = S.get("filtro_menu", "Favoritos")
    with st.container(key="panel_carta"):
        with st.container(key="categorias_prototipo", horizontal=True, gap="small"):
            for nombre, icono in categorias:
                st.button(nombre, icon=f":material/{icono}:", key=f"categoria_{nombre}",
                          type="primary" if nombre == categoria else "secondary",
                          on_click=seleccionar_categoria, args=(nombre,), width="stretch")
        terminos = []
        if S.get("mostrar_busqueda"):
            busqueda = st.text_input("Buscar un plato", placeholder="Busca por plato o ingrediente",
                                    label_visibility="collapsed", max_chars=80, icon=":material/search:",
                                    value=S.get("busqueda_menu", ""), key="buscar_plato")
            S.busqueda_menu = busqueda
            terminos = normalizar(busqueda).split()
        claves = [
            clave for clave, plato in PLATOS.items()
            if (categoria == "Favoritos" or categoria == plato["categoria"]
                or (categoria == "Mariscos" and clave == "chaufa-mariscos"))
            and all(termino in normalizar(" ".join((plato["nombre"], *plato["ingredientes"]))) for termino in terminos)
        ]
        if categoria == "Favoritos":
            claves.sort(key=lambda clave: clave not in S.get("favoritos", []))
        if claves:
            tarjetas(claves, "carta")
        else:
            st.info("No encontramos platos con esa búsqueda. Prueba otro ingrediente o cambia de categoría.")
        st.button("Preguntar a Belén", icon=":material/chat:", on_click=ir,
                  args=("Belén",), key="ayuda_carta", width="stretch")


def detalle_plato(clave):
    plato = PLATOS[clave]
    with st.container(key="foto_detalle"):
        st.html(foto(clave, grande=True))
        st.button("Volver a la carta", icon=":material/arrow_back:", on_click=abrir_menu, key="volver_carta")
        boton_favorito(clave, "detalle")
    with st.container(key="detalle_prototipo"):
        nombres = plato["ingredientes"]
        principales = nombres[:3] + ["verduras"] if clave == "chaufa-pollo" else nombres[:4]
        ingredientes = "".join(
            f'<li><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICONOS_INGREDIENTES[i]}</svg>'
            f'{escape(nombre.capitalize())}</li>' for i, nombre in enumerate(principales)
        )
        otros = ", ".join(nombre for nombre in nombres if nombre not in principales)
        nota = f'<p class="otros-ingredientes">También: {escape(otros)}.</p>' if otros else ""
        st.html(f"""
          <article class="detalle-texto">
            <div class="detalle-titulo"><h1>{escape(plato['nombre'])}</h1><strong>{soles(plato['precio'])}</strong></div>
            <p>{escape(plato['descripcion'])}</p>
            <h2>Ingredientes principales</h2>
            <ul class="ingredientes">{ingredientes}</ul>{nota}
            <h2>Personaliza tu plato <small>(opcional)</small></h2>
          </article>
        """)
        picante = st.pills("Nivel de picante", NIVELES_PICANTE, default="Sin picante", key=f"picante_{clave}") or "Sin picante"
        st.html('<p class="label-extra">Extras</p>')
        extras = [
            nombre for nombre, precio in EXTRAS.items()
            if st.checkbox(f"{nombre} · + {soles(precio)}", key=f"extra_{clave}_{nombre}")
        ]
        with st.container(key="agregar_detalle", horizontal=True, vertical_alignment="center", gap="small"):
            cantidad = st.number_input("Cantidad", min_value=1, max_value=20, step=1,
                                       label_visibility="collapsed", key=f"cantidad_{clave}")
            st.button("Agregar al pedido", icon=":material/shopping_cart:", type="primary",
                      on_click=agregar_desde_ficha, args=(clave, cantidad, picante, extras), width="stretch")
        alternativa = PLATOS["tallarin-pollo" if clave == "chaufa-pollo" else "chaufa-pollo"]["nombre"]
        st.button("Comparar con Belén", icon=":material/chat:", key="comparar_plato", on_click=iniciar_pregunta,
                  args=(f"Compara {plato['nombre']} con {alternativa}.",), width="stretch")
        st.caption("Precios ilustrativos. Si tienes alergias, confirma con el local.")


def mensaje_visible(historial, rol, texto):
    with historial, st.chat_message(rol, avatar=":material/auto_awesome:" if rol == "assistant" else ":material/person:"):
        st.markdown(texto)


def descargar_metricas():
    archivo = io.StringIO()
    escritor = csv.DictWriter(archivo, fieldnames=["turno", "tipo", "proveedor", "latencia_ms"])
    escritor.writeheader()
    escritor.writerows(S.metricas)
    st.download_button("Descargar métricas CSV", archivo.getvalue(), "metricas-belen.csv",
                       mime="text/csv", icon=":material/download:")


def mostrar_platos_sugeridos(espacio):
    platos = S.get("platos_sugeridos", ())
    if not platos:
        return
    with espacio.container():
        with st.container(key="platos_sugeridos"):
            st.html('<p class="eyebrow">PLATOS MENCIONADOS</p>')
            columnas = st.columns(min(len(platos), 3), gap="small")
            for columna, clave in zip(columnas, platos):
                plato = PLATOS[clave]
                with columna:
                    st.html(
                        f'{foto(clave)}<p><strong>{escape(plato["nombre"])}</strong><br>'
                        f'<small>{escape(plato["descripcion"])}</small></p>'
                    )
                    st.button("Ver detalles", icon=":material/arrow_forward:",
                              on_click=abrir_detalle, args=(clave,), key=f"chat_plato_{clave}",
                              width="stretch")


def guardar_respuesta(pregunta, respuesta, milisegundos):
    S.historial.extend([("user", pregunta, ""), ("assistant", respuesta.texto, respuesta.fuente)])
    S.historial = S.historial[-80:]
    guardar_mensaje_asistente(respuesta, milisegundos)
    S.pop("consulta_en_curso", None)


def guardar_mensaje_asistente(respuesta, milisegundos=0):
    S.respuesta_avatar = respuesta.texto
    S.gesto_avatar = {
        "error_ia": "error", "derivacion": "precaucion", "faq": "carta",
    }.get(respuesta.tipo, respuesta.tipo)
    S.platos_sugeridos = respuesta.platos
    S.metricas.append({
        "turno": len(S.metricas) + 1,
        "tipo": respuesta.tipo,
        "proveedor": respuesta.proveedor,
        "latencia_ms": milisegundos,
    })
    if len(S.historial) > 8:
        perfil = S.perfil
        grupo = perfil["personas"] or "sin dato"
        presupuesto = soles(perfil["presupuesto"]) if perfil["presupuesto"] is not None else "sin dato"
        exclusiones = ", ".join(perfil["exclusiones"]) or "sin dato"
        S.resumen = (
            f"Personas: {grupo}. Presupuesto: {presupuesto}. Preferencia: {perfil['gusto'] or 'sin dato'}. "
            f"Exclusiones: {exclusiones}. Último plato consultado: {perfil['plato'] or 'sin dato'}."
        )


def respuesta_de_destino(pregunta, destino):
    pagina, plato = destino
    if pagina == "Menú" and plato:
        nombre = PLATOS[plato]["nombre"]
        return Respuesta(
            f"Te acompaño a la ficha de {nombre}. Podemos revisar sus ingredientes o personalizarlo antes de agregarlo.",
            "navegacion",
            platos=(plato,),
        )
    if pagina == "Menú":
        return Respuesta(
            "Te acompaño a la carta. Cuéntame qué sabores te gustan y vemos juntos qué plato elegir.",
            "navegacion",
            platos=("chaufa-pollo", "tallarin-pollo", "tipakay"),
        )
    if pagina == "Crear":
        _, _, opciones = PASOS[0]
        return Respuesta(
            f"Vamos a personalizar tu plato. Empezamos con la base: "
            f"{', '.join(opciones)}. Dime cuál prefieres o selecciónala en pantalla.",
            "navegacion",
        )
    if pagina == "Pedido":
        return Respuesta(
            "Llegamos a tu pedido. Desde aquí tú decides cómo continuar y el pago te corresponde a ti. "
            "Si tienes otra duda antes de terminar, pregúntame; cuando estés listo puedes finalizar la llamada. "
            "¡Que disfrutes tu comida!",
            "limite_asistencia",
        )
    return Respuesta("Volvemos al inicio. Si quieres, podemos seguir explorando la carta.", "navegacion")


def procesar_eleccion_creador_por_voz(pregunta):
    paso = S.get("paso", -1)
    if S.vista != "Crear" or not 0 <= paso < len(PASOS):
        return None

    etiqueta, _, opciones = PASOS[paso]
    texto = normalizar(pregunta)
    elegidas = [
        opcion for opcion in opciones
        if re.search(rf"\b{re.escape(normalizar(opcion))}\b", texto)
        and not (opcion == "Cebolla" and re.search(r"\bsin cebolla\b", texto))
    ]
    if not elegidas:
        return None

    if etiqueta == "Verduras":
        for opcion in elegidas:
            elegir_ingrediente(etiqueta, opcion)
    else:
        S.combinacion[etiqueta] = elegidas[0]

    siguiente = paso + 1
    S.paso = siguiente
    if siguiente == len(PASOS):
        respuesta = (
            f"Elegí {', '.join(elegidas)} para {etiqueta.lower()}. "
            "Ya puedes revisar tu plato en pantalla; si quieres cambiar algo, usa Editar ingredientes."
        )
    else:
        siguiente_etiqueta, pregunta_siguiente, opciones_siguientes = PASOS[siguiente]
        respuesta = (
            f"Perfecto, elegí {', '.join(elegidas)} para {etiqueta.lower()}. "
            f"Ahora {pregunta_siguiente.lower()} Opciones: {', '.join(opciones_siguientes)}. "
            "Dime cuál prefieres o selecciónala en pantalla."
        )
    return Respuesta(respuesta, "personalizacion")


def ejecutar_accion_live(nombre, argumentos):
    argumentos = argumentos if isinstance(argumentos, dict) else {}
    if nombre == "navigate_screen":
        pantalla = argumentos.get("screen")
        plato = argumentos.get("dish_id")
        if pantalla == "menu":
            if isinstance(plato, str) and plato in PLATOS:
                abrir_detalle(plato)
                S.pop("pantalla_llamada_pendiente", None)
                return f"Abrí la ficha de {PLATOS[plato]['nombre']} en la carta."
            abrir_menu()
            S.pop("pantalla_llamada_pendiente", None)
            return "Abrí la carta."
        if pantalla == "customizer":
            ir("Crear")
            S.pop("pantalla_llamada_pendiente", None)
            if not 0 <= S.get("paso", -1) < len(PASOS):
                S.paso = 0
                S.combinacion = {}
            etiqueta, _, opciones = PASOS[S.paso]
            return f"Abrí el creador. La etapa actual es {etiqueta}; opciones: {', '.join(opciones)}."
        if pantalla == "order":
            ir("Pedido")
            S.pop("pantalla_llamada_pendiente", None)
            return "Abrí el pedido. La persona revisa y confirma el pedido y el pago por su cuenta."
        if pantalla == "home":
            ir("Inicio")
            S.pop("pantalla_llamada_pendiente", None)
            return "Volví al inicio."
        return "No pude abrir esa sección. Pregunta cuál sección quiere ver."

    if nombre == "select_custom_options":
        paso = S.get("paso", -1)
        if S.vista != "Crear" or not 0 <= paso < len(PASOS):
            return "No está abierto el creador. Abre personalizar mi plato antes de elegir opciones."
        opciones = argumentos.get("options")
        if not isinstance(opciones, list):
            return "No entendí qué opción seleccionar. Repite el nombre de una opción visible."
        _, _, disponibles = PASOS[paso]
        elegidas = [
            opcion for opcion in disponibles
            if any(normalizar(opcion) == normalizar(str(dicha)) for dicha in opciones)
        ]
        if not elegidas:
            return f"No seleccioné nada. En esta etapa puedes elegir: {', '.join(disponibles)}."
        if PASOS[paso][0] == "Verduras":
            for opcion in elegidas:
                elegir_ingrediente("Verduras", opcion)
        else:
            S.combinacion[PASOS[paso][0]] = elegidas[0]
        S.paso = paso + 1
        if S.paso >= len(PASOS):
            return f"Seleccioné {', '.join(elegidas)}. Ya puedes revisar tu plato en pantalla."
        etiqueta, pregunta, siguientes = PASOS[S.paso]
        return (
            f"Seleccioné {', '.join(elegidas)}. Etapa: {etiqueta}. {pregunta} "
            f"Opciones disponibles: {', '.join(siguientes)}."
        )
    if nombre == "recommend_menu":
        personas = argumentos.get("people")
        monto = argumentos.get("budget_soles")
        if type(personas) is not int or not 1 <= personas <= 30 or isinstance(monto, bool):
            return "Necesito un grupo de 1 a 30 personas y un presupuesto válido en soles."
        try:
            presupuesto = Decimal(str(monto))
        except (InvalidOperation, ValueError):
            return "No pude interpretar ese presupuesto. Confírmalo en soles."
        if not presupuesto.is_finite() or presupuesto <= 0 or presupuesto > 1_000_000:
            return "El presupuesto debe ser mayor que cero y menor o igual a S/ 1,000,000."
        centimos = int(presupuesto * 100)
        perfil = {**S.perfil, "exclusiones": S.perfil["exclusiones"].copy()}
        perfil.update(personas=personas, presupuesto=centimos, recomendando=True)
        S.perfil.update(perfil)
        plan = recomendar(perfil)
        if not plan.datos:
            return plan.instruccion
        opciones = "\n".join(f"- {valor}" for valor in plan.datos.values())
        registros = "\nCatálogo e identificadores: " + ", ".join(
            f'{clave}={PLATOS[clave]["nombre"]}' for clave in plan.registros
        )
        return f"{plan.instruccion}\n{opciones}{registros}"
    if nombre == "add_menu_dish":
        clave = argumentos.get("dish_id")
        cantidad = argumentos.get("quantity", 1)
        picante = argumentos.get("spicy", "")
        extras = argumentos.get("extras", [])
        if (
            not isinstance(clave, str)
            or clave not in PLATOS
            or type(cantidad) is not int
            or not 1 <= cantidad <= 99
            or not isinstance(picante, str)
            or picante not in ("", *NIVELES_PICANTE)
            or not isinstance(extras, list)
            or any(not isinstance(extra, str) or extra not in EXTRAS for extra in extras)
        ):
            return "No agregué el plato: revisemos el nombre, la cantidad y las opciones de la carta."
        if not agregar_plato(clave, cantidad, picante, extras):
            return "No pude agregar ese plato. Revisa las opciones disponibles en la carta."
        return (
            f"Agregué {cantidad} × {PLATOS[clave]['nombre']} al pedido local. "
            f"El total ilustrativo actual es {soles(total_pedido())}. No se confirmó ni pagó."
        )
    if nombre == "add_customized_dish":
        cantidad = argumentos.get("quantity", 1)
        if type(cantidad) is not int or not 1 <= cantidad <= 99:
            return "Indica una cantidad entre 1 y 99 para actualizar el pedido."
        combinacion = S.combinacion if (
            S.vista == "Crear" and S.paso >= len(PASOS) and S.combinacion.get("Base")
        ) else S.get("ultima_combinacion_personalizada")
        if not combinacion:
            return "El plato aún está incompleto y no hay una combinación anterior para repetir."
        if not agregar_personalizado(combinacion, cantidad):
            return "No pude agregar la combinación. Revisa que tenga una base seleccionada."
        S.ultima_combinacion_personalizada = {
            clave: valor[:] if isinstance(valor, list) else valor
            for clave, valor in combinacion.items()
        }
        S.combinacion = {}
        S.paso = 0
        etiqueta, pregunta, opciones = PASOS[S.paso]
        return (
            f"Agregué {cantidad} combinación(es) personalizada(s) al pedido local. El total ilustrativo es "
            f"{soles(total_pedido())}. Si quieres armar otro plato, empezamos con {etiqueta}: "
            f"{', '.join(opciones)}. También puedes abrir tu pedido."
        )
    if nombre == "update_order_quantity":
        clave = argumentos.get("dish_id")
        cantidad = argumentos.get("quantity")
        if (
            not isinstance(clave, str)
            or clave not in (*PLATOS, "creado")
            or type(cantidad) is not int
            or not 0 <= cantidad <= 99
        ):
            return "Indica el identificador del plato y una cantidad entre 0 y 99."
        if not actualizar_cantidad(clave, cantidad):
            return "No encontré ese plato en el pedido actual. Puedes agregarlo primero."
        accion = "Quité" if cantidad == 0 else "Actualicé"
        return f"{accion} {clave}; ahora hay {cantidad} unidad(es). El total ilustrativo es {soles(total_pedido())}."
    return "No reconozco esa acción dentro de China Wok AI."


def procesar_consulta_pendiente():
    en_curso = S.get("consulta_en_curso")
    if not en_curso:
        return
    pregunta = en_curso["pregunta"]
    if re.search(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}|(?:\d[ .-]?){8,}\d", pregunta, flags=re.IGNORECASE):
        respuesta = Respuesta(
            "Por privacidad, no puedo procesar correos, teléfonos ni números de identificación. "
            "Puedes volver a preguntarme sin esos datos.",
            "precaucion",
        )
        guardar_respuesta(pregunta, respuesta, 0)
        st.rerun()

    eleccion = procesar_eleccion_creador_por_voz(pregunta)
    if eleccion:
        guardar_respuesta(pregunta, eleccion, 0)
        st.rerun()

    # Las consultas escritas sobre la carta deben resolverse en el hilo. La voz
    # conserva la navegación por acciones para no interrumpir la llamada.
    destino = destino_navegacion(pregunta) if S.get("llamada_activa") else None
    if destino:
        pagina, plato = destino
        if pagina == "Menú":
            S.filtro_menu = "Favoritos"
            abrir_detalle(plato) if plato else abrir_menu()
        elif pagina == "Crear":
            ir("Crear")
            S.paso = 0
            S.combinacion = {}
            S.pop("solicitud_crear", None)
            S.pop("escribir_creacion", None)
        else:
            ir(pagina)
        S.pop("pantalla_llamada_pendiente", None)
        guardar_respuesta(pregunta, respuesta_de_destino(pregunta, destino), 0)
        st.rerun()

    inicio = perf_counter()
    config = {
        "gemini_key": variable("GEMINI_API_KEY"),
        "gemini_model": variable("GEMINI_MODEL", "gemini-3.5-flash-lite"),
        "embedding_model": variable("GEMINI_EMBEDDINGS_MODEL"),
        "groq_key": variable("GROQ_API_KEY"),
        "groq_model": variable("GROQ_MODEL", "openai/gpt-oss-20b"),
    }
    proveedores = config["gemini_key"] or config["groq_key"]
    ultimos = [(rol, texto) for rol, texto, _ in S.historial[-8:]]
    respuesta = responder(
        pregunta,
        S.perfil,
        ultimos,
        S.resumen,
        inteligencia(config) if proveedores else None,
        contexto_interfaz=en_curso["contexto"],
    )
    guardar_respuesta(pregunta, respuesta, round((perf_counter() - inicio) * 1000))
    if S.get("llamada_activa") and respuesta.tipo == "recomendacion":
        S.filtro_menu = "Favoritos"
        ir("Menú")
        S.pop("pantalla_llamada_pendiente", None)
    st.rerun()


def montar_llamada():
    activa = S.get("llamada_activa", False)
    if not activa and S.vista != "Belén":
        return
    with st.container(key="llamada_activa"):
        estado = "Modo voz"
        if activa:
            estado = "Voz de respaldo" if S.get("live_api_error") else "Voz en directo"
        compacto = S.vista != "Belén" or S.get("vista_voz_compacta", False)
        principal = activa and not compacto
        with st.container(key="cabecera_llamada", horizontal=True, vertical_alignment="center"):
            st.html(
                f'<p class="estado-llamada" data-activa="{str(activa).lower()}" '
                f'data-principal="{str(principal).lower()}"><span></span>{estado}</p>'
            )
            if activa and S.vista != "Belén":
                st.button("Ver chat", icon=":material/chat:", key="abrir_chat_llamada",
                          on_click=ir, args=("Belén",))
        avatar = mostrar_belen(
            gesto="pensando" if S.get("consulta_en_curso") else S.get("gesto_avatar", "lista"),
            sesion=S.session_id,
            turno=len(S.metricas),
            respuesta=S.get("respuesta_avatar", ""),
            modo="llamada" if activa else "prellamada",
            compacto=compacto,
            live_token=S.get("live_token", ""),
            live_model=MODELO_LIVE,
            live_config=crear_configuracion_websocket() if S.get("live_token") else {},
            live_tool_response=S.get("live_tool_response"),
            live_error=S.get("live_api_error", ""),
            live_connected=S.get("live_connected", False),
            app_context={
                "pantalla": S.vista,
                "conversacion_iniciada": bool(S.historial),
                "turnos_escritos_recientes": [
                    {"rol": rol, "texto": texto[:600]}
                    for rol, texto, _ in [turno for turno in S.historial if turno[2] != "Gemini Live"][-8:]
                ] if activa else [],
                "plato": S.detalle,
                "paso": PASOS[S.paso][0] if 0 <= S.get("paso", -1) < len(PASOS) else None,
                "opciones": PASOS[S.paso][2] if 0 <= S.get("paso", -1) < len(PASOS) else [],
                "seleccion": S.get("combinacion", {}),
                "perfil": {
                    "personas": S.perfil.get("personas"),
                    "presupuesto": soles(S.perfil["presupuesto"]) if S.perfil.get("presupuesto") else None,
                    "preferencia": S.perfil.get("gusto"),
                    "exclusiones": S.perfil.get("exclusiones", []),
                },
                "pedido": {
                    "lineas": resumen_pedido(),
                    "total": soles(total_pedido()),
                    "cantidad": cantidad_pedido(),
                },
            },
            clave="belen_llamada_persistente",
        )
    evento = avatar.get("llamada_iniciada")
    if not activa and evento and evento.get("id") != S.get("ultima_llamada_iniciada"):
        S.ultima_llamada_iniciada = evento["id"]
        iniciar_llamada()
        if evento.get("token_required"):
            try:
                S.live_token = crear_token_live(variable("GEMINI_API_KEY"))
                S.live_api_error = ""
            except ErrorLiveAPI as error:
                S.live_token = ""
                S.live_api_error = str(error)
                st.warning(f"{S.live_api_error} Usaré la voz de respaldo.")
        st.rerun()
    actualizar_componente = False
    evento = avatar.get("live_transcript")
    if isinstance(evento, dict) and evento.get("id") != S.get("ultima_transcripcion_live"):
        texto = evento.get("text", "").strip()
        rol = evento.get("role")
        if texto and rol in ("user", "assistant"):
            S.ultima_transcripcion_live = evento["id"]
            S.historial.append((rol, texto, "Gemini Live"))
            S.historial = S.historial[-80:]
            if rol == "assistant":
                S.respuesta_avatar = texto
    evento = avatar.get("live_status")
    if (
        isinstance(evento, dict)
        and evento.get("estado") == "conectada"
        and not S.get("live_connected")
    ):
        S.live_connected = True
        actualizar_componente = True
    evento = avatar.get("live_tool_calls")
    if activa and isinstance(evento, dict) and evento.get("id") != S.get("ultimo_tool_live"):
        S.ultimo_tool_live = evento["id"]
        respuestas = []
        for llamada in evento.get("calls", []):
            if not isinstance(llamada, dict) or not llamada.get("id") or not llamada.get("name"):
                continue
            resultado = ejecutar_accion_live(llamada["name"], llamada.get("args"))
            respuestas.append({
                "id": llamada["id"],
                "name": llamada["name"],
                "response": {"result": resultado},
            })
        if respuestas:
            S.live_tool_response = {"id": uuid4().hex, "function_responses": respuestas}
            actualizar_componente = True
    evento = avatar.get("live_error")
    if isinstance(evento, dict) and evento.get("id") != S.get("ultimo_error_live"):
        S.ultimo_error_live = evento["id"]
        S.live_token = ""
        S.live_connected = False
        S.live_api_error = evento.get("message") or "Gemini Live se desconectó; usaré la voz de respaldo."
        actualizar_componente = True
    evento = avatar.get("llamada_finalizada")
    if activa and evento and evento.get("id") != S.get("ultima_llamada_finalizada"):
        S.ultima_llamada_finalizada = evento["id"]
        parcial = evento.get("transcripcion")
        if isinstance(parcial, str) and parcial.strip():
            S.historial.append(("assistant", parcial.strip(), "Gemini Live"))
            S.historial = S.historial[-80:]
        finalizar_llamada()
        st.rerun()
    evento = avatar.get("dictado")
    if isinstance(evento, dict) and evento.get("id") and evento["id"] != S.get("ultimo_dictado"):
        S.ultimo_dictado = evento["id"]
        texto = evento.get("texto")
        if isinstance(texto, str) and texto.strip():
            S.consulta_en_curso = {"pregunta": texto[:500], "contexto": contexto_pantalla()}
    if S.get("live_api_error"):
        st.warning(f"{S.live_api_error} La llamada seguirá con la voz de respaldo.")
    if actualizar_componente:
        st.rerun()


def procesar_pantalla_llamada_pendiente():
    pendiente = S.pop("pantalla_llamada_pendiente", None)
    if not pendiente or not S.get("llamada_activa"):
        return
    pagina, plato = pendiente
    respuesta = respuesta_de_destino("", (pagina, plato))
    guardar_mensaje_asistente(respuesta)
    st.rerun()


def chat():
    _, detalle = S.get("origen_chat", ("Inicio", None))
    contexto = S.get("contexto_chat", {})
    gusto = CATEGORIAS_GUSTO.get(contexto.get("categoria"))
    en_curso = S.get("consulta_en_curso")
    modo_voz = S.modo_chat == "voz"
    inmersivo = modo_voz and not S.get("vista_voz_compacta", False)
    with st.container(key="chat_header", horizontal=True, vertical_alignment="center", gap="small"):
        if S.get("llamada_activa"):
            st.button("Ver chat" if inmersivo else "Vista de voz",
                      icon=":material/keyboard:" if inmersivo else ":material/graphic_eq:",
                      on_click=cambiar_vista_voz, key="alternar_vista_voz")
        else:
            st.button("Volver", icon=":material/arrow_back:", on_click=regresar_del_chat, key="volver_chat")
        st.html("""
            <div class="identidad-chat">
              <span class="marca-chat" aria-hidden="true">B</span>
              <div><strong>Belén</strong><small>China Wok AI</small></div>
            </div>
        """)
        with st.popover("Más", icon=":material/more_vert:", type="secondary"):
            st.caption("Evita compartir datos personales. Tus consultas se procesan con el proveedor de IA configurado.")
            if S.get("llamada_activa") and S.get("origen_chat", ("Inicio", None))[0] != "Inicio":
                st.button("Volver a la pantalla anterior", icon=":material/arrow_back:", on_click=regresar_del_chat)
            if not S.get("llamada_activa"):
                st.button("Nueva conversación", icon=":material/restart_alt:", on_click=nueva_conversacion)
            if S.metricas and not S.get("llamada_activa"):
                descargar_metricas()
    if inmersivo:
        with st.container(key="voz_transcripcion"):
            st.caption("Puedes interrumpir a Belén o volver al chat en cualquier momento.")
        return

    vacio = not S.historial and not en_curso and "pendiente" not in S
    with st.container(key="chat_cuerpo"):
        if vacio:
            subtitulo = "Explora la carta, encuentra algo para compartir o arma tu propio plato."
            if detalle:
                subtitulo = f"Estamos viendo {PLATOS[detalle]['nombre']}. Pregúntame por sus ingredientes o su precio."
            elif contexto.get("etapa"):
                subtitulo = "Puedo ayudarte a elegir lo que mejor combina con tu plato."
            st.html(f"""
                <div class="bienvenida-chat">
                  <span class="marca-chat" aria-hidden="true">B</span>
                  <h1>¿En qué te ayudo hoy?</h1>
                  <p>{escape(subtitulo)}</p>
                </div>
            """)
        historial = st.container(key="chat_historial")
        for rol, texto, _ in S.historial:
            mensaje_visible(historial, rol, texto)
        if en_curso:
            mensaje_visible(historial, "user", en_curso["pregunta"])
            historial.html('<p class="pensando-chat" role="status"><span></span><span></span><span></span> Belén está pensando</p>')
        if not en_curso and "pendiente" not in S:
            mostrar_platos_sugeridos(historial)
            sugerencias = (
                (("Ingredientes", "¿Qué lleva?", "restaurant"), ("Precio", "¿Cuánto cuesta?", "payments")) if detalle else
                (("Elegir ingredientes", "Ayúdame a elegir los ingredientes.", "skillet"),) if contexto.get("etapa") else
                (("Ver carta", "¿Qué venden aquí?", "restaurant_menu"),
                 ("Para 4 · S/ 100", "Somos 4 y tenemos S/ 100", "groups"),
                 ("Armar mi plato", "Quiero personalizar mi plato", "skillet")) if vacio else
                (("Personalizar", "Quiero personalizar mi plato", "skillet"),
                 ("Mi pedido", "Quiero revisar mi pedido", "shopping_bag"))
            )
            if gusto:
                sugerencias = (("Recomiéndame algo", f"¿Qué me recomiendas? Prefiero {gusto}.", "auto_awesome"), *sugerencias)
            with st.container(key="chat_sugerencias", horizontal=True, gap="small"):
                for etiqueta, pregunta, icono in sugerencias:
                    st.button(etiqueta, icon=f":material/{icono}:", key=f"sugerencia_{etiqueta}",
                              on_click=iniciar_pregunta, args=(pregunta,))
        marca = (S.historial[-1] if S.historial else None, en_curso["pregunta"] if en_curso else "")
        if marca != S.get("marca_chat") and not vacio:
            S.marca_chat = marca
            st.html("""
                <script>
                  requestAnimationFrame(() => {
                    const hilo = document.querySelector(".st-key-chat_cuerpo")?.parentElement;
                    if (hilo) hilo.scrollTop = hilo.scrollHeight;
                  });
                </script>
            """, unsafe_allow_javascript=True)
    with st.container(key="chat_compositor", horizontal=True, vertical_alignment="bottom"):
        entrada = st.chat_input("Escribe a Belén…", max_chars=500, disabled=bool(en_curso))
        if not S.get("llamada_activa"):
            montar_llamada()
    pregunta = S.pop("pendiente", None) or entrada
    if pregunta:
        S.consulta_en_curso = {"pregunta": pregunta, "contexto": contexto}
        st.rerun()


def cambiar_paso(paso):
    S.paso = paso
    S.subir_pantalla = True


def guardar_solicitud(texto):
    normal = normalizar(texto)
    propuesta = {}
    bases = (("chaufa", "Arroz chaufa"), ("tallarin", "Tallarines"), ("arroz", "Arroz blanco"))
    for patron, opcion in bases:
        if patron in normal:
            propuesta["Base"] = opcion
            break
    for opcion in PASOS[1][2]:
        if normalizar(opcion) in normal and f"sin {normalizar(opcion)}" not in normal:
            propuesta["Proteína"] = opcion
            break
    verduras = []
    for opcion in PASOS[2][2]:
        palabra = normalizar(opcion)
        if re.search(rf"\b{re.escape(palabra)}\b", normal) and (opcion == "Sin cebolla" or f"sin {palabra}" not in normal):
            verduras.append(opcion)
    if verduras:
        propuesta["Verduras"] = verduras
    for opcion in PASOS[3][2]:
        if normalizar(opcion) in normal or (opcion == "Sillao" and "salsa de soya" in normal):
            propuesta["Salsa"] = opcion
            break
    if propuesta.get("Salsa") and "poca" in normal:
        propuesta["Cantidad de salsa"] = "Poca"
    S.solicitud_crear = {"texto": texto, "propuesta": propuesta}
    S.pop("solicitud_texto", None)


def confirmar_solicitud():
    S.combinacion = S.solicitud_crear["propuesta"].copy()
    cambiar_paso(0)


def corregir_solicitud():
    S.pop("solicitud_crear", None)
    S.escribir_creacion = True


def solicitud():
    seleccion = S.get("solicitud_crear")
    if seleccion:
        banda_belen("Voy a preparar tu combinación. Revisa los ingredientes antes de continuar.", "solicitud", "¡Perfecto!", "oferta")
        with st.container(key="interpreta_crear"):
            st.html(f'<p>Esto entendí de tu solicitud</p><blockquote>«{escape(seleccion["texto"])}»</blockquote>')
            if seleccion["propuesta"]:
                st.caption("Seleccioné las opciones que encontré en el creador. Puedes corregirlas en los siguientes pasos.")
            else:
                st.caption("Puedes indicar una base, una proteína, verduras o salsa y elegirlas en los siguientes pasos.")
            st.button("Confirmar y continuar", type="primary", width="stretch", on_click=confirmar_solicitud)
            st.button("Corregir solicitud", width="stretch", on_click=corregir_solicitud)
        return

    with st.container(key="voz_creador"):
        voz = mostrar_belen(gesto="lista", sesion=S.session_id, modo="solicitud", clave="belen_solicitud")
        evento = voz.get("dictado")
        if isinstance(evento, dict) and evento.get("id") and evento["id"] != S.get("ultimo_dictado"):
            S.ultimo_dictado = evento["id"]
            texto = evento.get("texto")
            if isinstance(texto, str) and texto.strip():
                guardar_solicitud(texto.strip()[:200])
                st.rerun()
        if S.get("escribir_creacion"):
            with st.form("texto_creador"):
                texto = st.text_input("¿Cómo te gustaría tu plato?", max_chars=200,
                                      value=S.get("solicitud_texto", ""),
                                      placeholder="Quiero chaufa con pollo, brócoli y sin cebolla")
                enviado = st.form_submit_button("Revisar mi solicitud", type="primary", width="stretch")
                if enviado and texto.strip():
                    guardar_solicitud(texto.strip())
                    st.rerun()
        else:
            st.button("Prefiero escribir", icon=":material/edit:", width="stretch", on_click=corregir_solicitud)
        st.button("Elegir ingredientes", icon=":material/arrow_forward:", width="stretch",
                  on_click=cambiar_paso, args=(0,))


def elegir_ingrediente(etiqueta, opcion):
    if etiqueta != "Verduras":
        S.combinacion[etiqueta] = opcion
        return
    valores = S.combinacion.get(etiqueta, [])
    if opcion in valores:
        S.combinacion[etiqueta] = [valor for valor in valores if valor != opcion]
        return
    contrario = {"Sin cebolla": "Cebolla", "Cebolla": "Sin cebolla"}.get(opcion)
    S.combinacion[etiqueta] = [valor for valor in valores if valor != contrario] + [opcion]


def mostrar_progreso(paso):
    etiquetas = [etiqueta for etiqueta, _, _ in PASOS] + ["Revisar"]
    st.html(
        '<ol class="pasos-creador" aria-label="Progreso de tu plato">'
        + "".join(
            f'<li class="{"hecho" if i < paso else "actual" if i == paso else ""}"'
            f'{" aria-current=step" if i == paso else ""}><span>{i + 1}</span>{etiqueta}</li>'
            for i, etiqueta in enumerate(etiquetas)
        ) + "</ol>"
    )


def ingredientes_actuales(hasta=4):
    valores = []
    for etiqueta, _, _ in PASOS[:hasta]:
        valor = S.combinacion.get(etiqueta)
        if valor:
            texto = ", ".join(valor) if isinstance(valor, list) else valor
            if etiqueta == "Salsa" and valor != "Sin salsa" and S.combinacion.get("Cantidad de salsa"):
                texto += f' ({S.combinacion["Cantidad de salsa"].lower()})'
            valores.append(f"<div><dt>{escape(etiqueta)}</dt><dd>{escape(texto)}</dd></div>")
    return "".join(valores)


def creador():
    paso = S.paso
    if paso < 0:
        solicitud()
        return
    mostrar_progreso(paso)
    if paso == 4:
        banda_belen("Aquí tienes tu combinación. ¿Quieres agregarla a tu pedido?", "resumen", "¡Listo!", "recomendacion")
        st.html(f"""
          <article class="resumen-creador">
            {foto("creado", grande=True)}
            <div class="resumen-texto">
              <div class="detalle-titulo"><h2>Mi plato personalizado</h2><strong>{soles(PRECIO_PERSONALIZADO)}</strong></div>
              <dl>{ingredientes_actuales()}</dl>
            </div>
          </article>
        """)
        with st.container(key="acciones_resumen", horizontal=True, gap="small"):
            st.button("Editar ingredientes", icon=":material/edit:", on_click=cambiar_paso, args=(0,),
                      key="editar_plato", width="stretch")
            st.button("Agregar al pedido", icon=":material/shopping_cart:", on_click=agregar_wok,
                      type="primary", width="stretch")
        return

    etiqueta, pregunta, opciones = PASOS[paso]
    banda_belen(pregunta + " " + CONSEJOS[paso], "paso", gesto="oferta")
    seleccion = S.combinacion.get(etiqueta)
    with st.container(key="elecciones_creador"):
        for inicio in range(0, len(opciones), 3):
            columnas = st.columns(3, gap="small")
            for columna, opcion in zip(columnas, opciones[inicio:inicio + 3]):
                marcado = opcion in (seleccion or []) if isinstance(seleccion, list) else seleccion == opcion
                with columna, st.container(key=f"opcion_{paso}_{opciones.index(opcion)}"):
                    st.html(foto_ingrediente(opcion))
                    st.button(opcion, key=f"ingrediente_{opcion}", type="primary" if marcado else "secondary",
                              on_click=elegir_ingrediente, args=(etiqueta, opcion), width="stretch")
        if etiqueta == "Salsa" and seleccion not in (None, "Sin salsa"):
            S.combinacion["Cantidad de salsa"] = st.pills(
                "Cantidad", ("Poca", "Normal", "Extra"),
                default=S.combinacion.get("Cantidad de salsa") or "Normal", key="cantidad_salsa",
            ) or "Normal"
    st.html(f'<div class="preview-wok">{foto("creado", grande=True)}<aside><strong>Tu plato</strong>'
            f'<dl>{ingredientes_actuales(paso + 1) or "<dd>Elige una base</dd>"}</dl></aside></div>')
    with st.container(key="botones_creador"):
        atras, adelante = st.columns(2, gap="small")
        atras.button("Atrás", icon=":material/arrow_back:", on_click=cambiar_paso, args=(paso - 1,),
                     width="stretch")
        adelante.button("Revisar" if paso == 3 else "Siguiente", icon=":material/arrow_forward:",
                        on_click=cambiar_paso, args=(paso + 1,), disabled=seleccion is None and etiqueta != "Verduras",
                        type="primary", width="stretch")
    st.button("Consultar a Belén", icon=":material/chat:", key="ayuda_creador", on_click=iniciar_pregunta,
              args=(f"Ayúdame a elegir {etiqueta.lower()} para mi plato.",))


marca_pantalla = st.empty()
if S.pop("subir_pantalla", False):
    marca_pantalla.html("""
      <script>
        requestAnimationFrame(() => {
          const pantalla = document.querySelector('[data-testid="stAppScrollToBottomContainer"]');
          if (pantalla) pantalla.scrollTo({top: 0, behavior: 'instant'});
        });
      </script>
    """, unsafe_allow_javascript=True)

with st.container(key="cabecera_prototipo", horizontal=True, vertical_alignment="center", gap="small"):
    st.html('<header class="cabecera"><strong class="marca-proto">CHINA<br>WOK</strong><span class="idioma-proto">◎ ES</span></header>')
    if S.vista in ("Menú", "Pedido"):
        st.button(f"Mi pedido ({cantidad_pedido()})", key="pedido_cabecera", icon=":material/shopping_cart:",
                  type="primary", on_click=ir, args=("Pedido",))

with st.container(key="navegacion", horizontal=True, gap="small", wrap=False, horizontal_alignment="distribute"):
    st.button("Inicio", icon=":material/home:", type="primary" if S.vista == "Inicio" else "secondary",
              key="nav_Inicio", on_click=ir, args=("Inicio",), width="stretch")
    if S.vista == "Menú" and not S.detalle:
        st.button("Categorías", icon=":material/grid_view:", key="nav_Menú", on_click=abrir_menu, width="stretch")
        st.button("Buscar", icon=":material/search:", key="nav_buscar", on_click=abrir_busqueda, width="stretch")
    else:
        st.button("Menú", icon=":material/restaurant_menu:", key="nav_Menú", on_click=abrir_menu, width="stretch")
    pedido = "Mi pedido"
    if cantidad_pedido():
        pedido = f"Mi pedido · {soles(total_pedido())}" if S.vista == "Menú" else f"Mi pedido ({cantidad_pedido()})"
    st.button(pedido, icon=":material/shopping_cart:", type="primary" if S.vista == "Pedido" else "secondary",
              key="nav_Pedido", on_click=ir, args=("Pedido",), width="stretch")

procesar_pantalla_llamada_pendiente()
if S.get("llamada_activa"):
    montar_llamada()

if S.vista == "Pedido":
    mostrar_pedido(foto, abrir_menu)
else:
    {"Inicio": portada, "Menú": menu, "Crear": creador, "Belén": chat}[S.vista]()

procesar_consulta_pendiente()
