"""Reglas de conversación y datos de China Wok AI."""

import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

CATALOGO = json.loads((Path(__file__).parent / "data/carta.json").read_text(encoding="utf-8"))
PLATOS = {plato["id"]: plato for plato in CATALOGO["platos"]}
FAQ = {registro["id"]: registro for registro in CATALOGO["preguntas"]}
SALUDO = "¡Hola! Soy Belén. ¿Qué se te antoja? Puedo mostrarte la carta o ayudarte a elegir según tu presupuesto."
IDENTIDAD = "Belén, la asistente virtual de China Wok"

EXCLUSIONES = {
    "mariscos": ("marisco", "langostin", "camaron", "calamar", "pulpo"),
    "pescado": ("pescado", "atun", "salmon"),
    "gluten": ("gluten", "trigo"),
    "soya": ("soya", "soja", "sillao", "tofu"),
    "maní": ("mani", "cacahuate"),
    "huevo": ("huevo",),
    "cebolla": ("cebolla",),
    "pollo": ("pollo",),
    "carne": ("res", "cerdo", "pollo", "pescado", "langostin", "calamar"),
}
GUSTOS = {
    "arroz": ("arroz", "chaufa"), "tallarín": ("tallarin", "fideo"),
    "pollo": ("pollo",), "carne": ("res", "lomo", "carne"),
    "verduras": ("verdura", "vegetal", "tofu"), "mariscos": EXCLUSIONES["mariscos"],
}
NUMEROS = {
    "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
}
PERSONAS = r"(\d{1,2}|uno|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)"
MONTO = r"(\d{1,5}(?:[.,]\d{1,2})?)(?![\d.,])"
PALABRAS_VACIAS = set("a al algo con cual de del el en es hay la las lo los me para por que se si tiene un una y".split())


@dataclass(frozen=True)
class Respuesta:
    texto: str
    tipo: str
    fuente: str = ""
    proveedor: str = "Sistema"
    platos: tuple[str, ...] = ()


@dataclass(frozen=True)
class Plan:
    tipo: str
    instruccion: str
    datos: dict[str, str] = field(default_factory=dict)
    fuente: str = ""
    registros: tuple[str, ...] = ()


def normalizar(texto):
    return "".join(
        caracter for caracter in unicodedata.normalize("NFD", texto.lower())
        if unicodedata.category(caracter) != "Mn"
    )


def tokens(texto):
    return set(re.findall(r"[a-z0-9]+", normalizar(texto))) - PALABRAS_VACIAS


def soles(centimos):
    return f"S/ {centimos // 100}.{centimos % 100:02d}"


def nuevo_perfil():
    return {"personas": None, "presupuesto": None, "exclusiones": [], "gusto": None, "plato": None, "recomendando": False}


def es_manipulacion(texto):
    return bool(re.search(
        r"(ignora|olvida|omite|desobedece)\s+(todas?\s+)?(las?\s+|tus?\s+|mis?\s+)?"
        r"(reglas|instrucciones|indicaciones|prompt)|system prompt|prompt (del|de) sistema|"
        r"revela.{0,35}(instrucciones|clave|api key)|ignore.{0,20}instructions",
        texto,
    ))


def actualizar_perfil(texto, perfil):
    grupo = re.search(rf"\b(?:somos|seremos|para|grupo de)\s+{PERSONAS}\b|\b{PERSONAS}\s+personas\b", texto)
    if re.search(r"\b(?:solo|sola|solamente|por mi cuenta)\b|\bpara mi\b|\bsoy yo\b|\buna persona\b", texto):
        perfil["personas"] = 1
    dato_breve = texto.strip(" ¡¿").rstrip(".!?").strip()
    espera_personas = perfil["recomendando"] and perfil["personas"] is None
    espera_presupuesto = (
        perfil["recomendando"] and perfil["personas"] is not None and perfil["presupuesto"] is None
    )
    grupo_breve = re.fullmatch(PERSONAS, dato_breve) if espera_personas else None
    if grupo or grupo_breve:
        valor = (grupo[1] or grupo[2]) if grupo else grupo_breve[1]
        cantidad = int(valor) if valor.isdigit() else NUMEROS[valor]
        if 1 <= cantidad <= 30:
            perfil["personas"] = cantidad

    monto = re.search(rf"s\s*/\s*{MONTO}|{MONTO}\s*(?:soles?|pen)\b", texto)
    if not monto:
        monto = re.search(rf"\b(?:presupuesto(?: de)?|tenemos|hasta|maximo)\s+{MONTO}", texto)
    if not monto and espera_presupuesto:
        monto = re.fullmatch(MONTO, dato_breve)
    if monto:
        numero = next(valor for valor in monto.groups() if valor is not None)
        perfil["presupuesto"] = int(Decimal(numero.replace(",", ".")) * 100)

    if re.search(r"\b(sin restricciones|cualquier ingrediente|como de todo)\b", texto):
        perfil["exclusiones"] = []
    evitados = re.findall(r"\b(?:sin nada de|sin|no como|evito|quita)\s+([^,.;!?]+)", texto)
    evitados = [re.split(r"\b(?:con|prefiero|me gusta)\b", frase, maxsplit=1)[0] for frase in evitados]
    for etiqueta, terminos in EXCLUSIONES.items():
        if any(any(termino in frase for termino in terminos) for frase in evitados):
            if etiqueta not in perfil["exclusiones"]:
                perfil["exclusiones"].append(etiqueta)

    preferencia = re.search(r"\b(?:prefiero|me gusta|que sea de|se me antoja|con ganas de)\s+([^.;!?]+)", texto)
    if preferencia:
        for gusto, variantes in GUSTOS.items():
            if any(variante in preferencia[1] for variante in variantes):
                perfil["gusto"] = gusto
                break


def plato_mencionado(texto):
    consulta = tokens(texto)
    coincidencias = []
    for identificador, plato in PLATOS.items():
        nombre = tokens(plato["nombre"])
        interseccion = nombre & consulta
        if nombre <= consulta or len(interseccion) >= 2:
            coincidencias.append((len(interseccion), -len(nombre - consulta), identificador))
    if coincidencias:
        return max(coincidencias)[2]
    for palabra, clave in (("lomo", "lomo"), ("tipakay", "tipakay"), ("tofu", "tofu")):
        if palabra in consulta:
            return clave
    return None


def destino_navegacion(mensaje):
    texto = normalizar(mensaje)
    if re.search(r"\b(?:carta|menu)\b|\bque\s+(?:venden|ofrecen|tienen|sirven)\b", texto):
        return "Menú", None
    if re.search(r"\b(?:personaliz\w*|customiz\w*)\b", texto) or (
        re.search(r"\b(?:crear|armar|configurar|combin\w*)\b", texto)
        and re.search(r"\b(?:plato|comida|ingredientes?|wok|combinacion|mi)\b", texto)
    ):
        return "Crear", None
    if re.search(r"\bmi\s+pedido\b|\bcarrito\b|\b(?:ver|abrir|ir|revisar|mostrar)\b.{0,18}\bpedido\b"
                 r"|\b(?:pagar|pago|checkout)\b"
                 r"|\b(?:mi\s+)?(?:pedido|carrito)\b.{0,18}\b(?:ver|abrir|revisar)\b", texto):
        return "Pedido", None
    if re.search(r"\b(?:volver|ir|regresar)\s+(?:al?\s+)?inicio\b", texto):
        return "Inicio", None

    clave = plato_mencionado(texto)
    if clave and (
        re.search(r"\b(?:muestrame|ver|abrir|ir a|llevame|pedir|ordenar|agregar|agrega|"
                  r"seleccionar|selecciona|elegir|elige|anadir|quiero pedir|quisiera pedir)\b", texto)
        or re.search(r"\b(?:quiero|quisiera|deseo|me gustaria)\s+(?:el|la|un|una)?\s*"
                     r"(?:arroz|pollo|tallarin|lomo|tofu|duo|banquete|chaufa)\b", texto)
    ):
        return "Menú", clave
    return None


def fichas():
    fichas_platos = {
        clave: (
            f'{plato["nombre"]}. {plato["categoria"]}. {plato["descripcion"]} '
            f'Ingredientes: {", ".join(plato["ingredientes"])}. '
            f'Precio de muestra: {soles(plato["precio"])}. Porciones: {plato["personas"]}.'
        )
        for clave, plato in PLATOS.items()
    }
    fichas_faq = {clave: f'{dato["consulta"]}. {dato["texto"]}' for clave, dato in FAQ.items()}
    return fichas_platos | fichas_faq


def recomendar(perfil):
    personas = perfil["personas"]
    presupuesto = perfil["presupuesto"]
    if not personas and presupuesto is None:
        return Plan(
            "aclaracion",
            "Pregunta si la comida es solo para la persona usuaria o para cuántas personas en total. Pregunta solo eso.",
        )
    if personas is None:
        return Plan("aclaracion", "Confirma el presupuesto y pregunta para cuántas personas es.",
                    {"PRESUPUESTO": soles(presupuesto)})
    if presupuesto is None:
        return Plan("aclaracion", "Confirma el tamaño del grupo y pregunta por el presupuesto total en soles.",
                    {"GRUPO": "una persona" if personas == 1 else f"{personas} personas"})

    candidatos = []
    for plato in PLATOS.values():
        detalle = normalizar(" ".join(plato["ingredientes"]))
        if any(termino in detalle for etiqueta in perfil["exclusiones"] for termino in EXCLUSIONES[etiqueta]):
            continue
        if perfil["gusto"] and not any(termino in detalle for termino in GUSTOS[perfil["gusto"]]):
            continue
        candidatos.append(plato)

    preferencia_ampliada = False
    if not candidatos and perfil["gusto"]:
        candidatos = [
            plato for plato in PLATOS.values()
            if not any(
                termino in normalizar(" ".join(plato["ingredientes"]))
                for etiqueta in perfil["exclusiones"] for termino in EXCLUSIONES[etiqueta]
            )
        ]
        preferencia_ampliada = bool(candidatos)
    if not candidatos:
        return Plan(
            "sin_resultado",
            "No recomiendes un ingrediente excluido. Explica que no puedes encontrar una opción "
            "responsable con las restricciones indicadas y ofrece revisar la carta juntos o ajustar "
            "una preferencia que no sea una restricción de salud.",
            {"GRUPO": f"{personas} personas", "PRESUPUESTO": soles(presupuesto)},
        )

    def combinaciones(limite):
        estados = {0: [(0, ())]}
        for cubiertas in range(personas):
            for precio, ids in tuple(estados.get(cubiertas, ())):
                for plato in candidatos:
                    total = precio + plato["precio"]
                    if limite is not None and total > limite:
                        continue
                    siguiente = min(personas, cubiertas + plato["personas"])
                    opcion = (total, tuple(sorted((*ids, plato["id"]))))
                    opciones = estados.setdefault(siguiente, [])
                    if all(actual[1] != opcion[1] for actual in opciones):
                        opciones.append(opcion)
                        opciones.sort(key=lambda actual: (actual[0], len(actual[1]), actual[1]))
                        del opciones[5:]
        return estados.get(personas, [])

    completas = combinaciones(presupuesto)
    completas_dentro = bool(completas)
    if not completas:
        completas = combinaciones(None)

    opciones = []
    if completas:
        for precio, ids in completas[:3 if completas_dentro else 1]:
            conteo = Counter(ids)
            platos = " + ".join(
                f'{cantidad} × {PLATOS[clave]["nombre"]}'
                for clave, cantidad in sorted(conteo.items())
            )
            total = soles(precio)
            if precio > presupuesto:
                total += f" (supera el presupuesto por {soles(precio - presupuesto)})"
            opciones.append((platos, total, ids, True))

    if not completas_dentro:
        individuales = sorted(
            candidatos,
            key=lambda plato: (
                plato["precio"] > presupuesto,
                max(0, personas - plato["personas"]),
                plato["precio"],
                plato["nombre"],
            ),
        )
        for plato in individuales:
            ids = (plato["id"],)
            if any(actual[2] == ids for actual in opciones):
                continue
            nota = f"plato de muestra para {plato['personas']} personas"
            if plato["personas"] < personas:
                nota += f" (faltaría completar para {personas})"
            total = f'{soles(plato["precio"])} · {nota}'
            if plato["precio"] > presupuesto:
                total += f" · supera el presupuesto por {soles(plato['precio'] - presupuesto)}"
            opciones.append((plato["nombre"], total, ids, False))
            if len(opciones) == 3:
                break

    marcadores = ("OPCIONUNO", "OPCIONDOS", "OPCIONTRES")
    datos = {
        marcador: f"**{nombre}** · {precio}"
        for marcador, (nombre, precio, _, _) in zip(marcadores, opciones)
    }
    ids_mostrados = tuple(dict.fromkeys(
        clave for _, _, ids, _ in opciones for clave in ids
    ))
    instruccion = (
        f"Recomienda opciones de la carta de muestra para {personas} personas y el presupuesto "
        f"de {soles(presupuesto)}. Presenta todas las opciones en viñetas, con un marcador por "
        "viñeta, y pregunta cuál quiere revisar o agregar. No inventes precios."
    )
    if not completas_dentro:
        instruccion += (
            " Ninguna combinación completa entra en el presupuesto. Sé transparente: muestra "
            "una alternativa parcial dentro del presupuesto si existe y una combinación completa "
            "con su diferencia; nunca digas que la alternativa parcial alcanza para todo el grupo."
        )
    if preferencia_ampliada:
        instruccion += (
            " No hubo platos que cumplieran el gusto indicado; dilo con claridad y presenta "
            "alternativas del catálogo que sí respetan las restricciones explícitas."
        )
    if perfil["exclusiones"]:
        instruccion += (
            f" Se excluyeron {', '.join(perfil['exclusiones'])}; no garantices seguridad "
            "alimentaria ni ausencia de contaminación cruzada."
        )
    return Plan(
        "recomendacion", instruccion, datos, registros=ids_mostrados
    )


def plan_plato(clave, ingredientes):
    plato = PLATOS[clave]
    if ingredientes:
        anteriores, ultimo = plato["ingredientes"][:-1], plato["ingredientes"][-1]
        lista = f"{', '.join(anteriores)} y {ultimo}" if anteriores else ultimo
        return Plan("carta", "Responde qué ingredientes registra la carta de muestra para el plato.",
                    {"PLATO": plato["nombre"], "INGREDIENTES": lista})
    return Plan("carta", "Indica el precio del plato en la carta de muestra.",
                {"PLATO": plato["nombre"], "PRECIO": soles(plato["precio"])})


def plan_faq(clave):
    registro = FAQ[clave]
    if clave == "oferta":
        return Plan(
            "oferta",
            "Explica que esta app tiene una carta local de muestra. El marcador CARTA contiene solo platos "
            "registrados en el proyecto; ofrece abrir la carta dentro de la app.",
            {"CARTA": registro["ejemplos"]}, registro.get("fuente", ""),
            ("oferta", "chaufa-pollo", "tallarin-pollo", "tipakay"),
        )
    if clave == "ceviche":
        return Plan(
            "disponibilidad",
            "Di que el ceviche no aparece en la carta local de esta app. Sugiere el [[ALTERNATIVA]] del catálogo "
            "si busca mariscos. El marcador es el nombre del plato. Evita afirmar que ningún local vende ceviche.",
            {"ALTERNATIVA": PLATOS["chaufa-mariscos"]["nombre"].lower()}, registro.get("fuente", ""),
            ("ceviche", "chaufa-mariscos"),
        )
    return Plan("faq", "Responde con la información local disponible y muéstrala tal cual.",
                {"DATO": registro["texto"]}, registro.get("fuente", ""))


def responder(mensaje, perfil, historial=(), resumen="", inteligencia=None, contexto_interfaz=None):
    mensaje = "".join(caracter for caracter in mensaje if not unicodedata.category(caracter).startswith("C")).strip()
    texto = normalizar(mensaje)
    if not texto or len(texto) > 500 or not re.search(r"\w", texto):
        return Respuesta("Escribe una consulta de hasta 500 caracteres sobre la carta o tu próxima comida.", "entrada")
    if es_manipulacion(texto):
        return Respuesta("Puedo ayudarte con la carta, los ingredientes y las recomendaciones de esta demo.", "fuera_de_alcance")

    plato = plato_mencionado(texto)
    pregunta_sensible = re.search(r"\b(contiene|tiene|lleva|es seguro|puedo comer)\b", texto) and re.search(
        r"\b(mani|cacahuate|soya|soja|gluten|mariscos?|huevo)\b", texto,
    )
    if pregunta_sensible or re.search(r"alerg|anafil|celiac|intoleran|trazas|contaminacion cruzada|reaccion", texto):
        return Respuesta(
            "Para consultas de alérgenos, confirma los ingredientes y la contaminación cruzada con el personal del local.",
            "derivacion",
        )
    if re.search(r"\b(reclamo|queja|reembolso|devolucion|pedido perdido|pedido no|seguimiento|pagar|quejarme)\b", texto):
        return Respuesta("Para revisar ese caso, contacta directamente al personal de China Wok.", "derivacion")

    pregunta_identidad = re.fullmatch(
        r"(?:hola+[, ]+)?(?:(?:tu\s+)?e+re+s+\s+be+l+e+n+|quien\s+e+re+s+|"
        r"como\s+te\s+llamas|cual\s+es\s+tu\s+nombre)",
        texto.strip(" ¡¿,.!?"),
    )
    if pregunta_identidad:
        if inteligencia is not None:
            plan = Plan(
                "saludo",
                "Preséntate con el marcador de identidad y ofrece ayuda con la carta, una recomendación "
                "o la personalización de un plato. Adapta la primera frase a la pregunta.",
                {"IDENTIDAD": IDENTIDAD},
            )
            respuesta, _ = inteligencia.generar(
                mensaje, texto, perfil, historial, resumen, plan, None,
                contexto_interfaz=contexto_interfaz or {},
            )
            if respuesta.tipo != "error_ia":
                return respuesta
        return Respuesta(f"Soy {IDENTIDAD}. Puedo mostrarte la carta o ayudarte a armar tu plato.", "saludo")

    if inteligencia is None:
        return Respuesta("Configura una clave de Gemini o Groq para conversar con Belén.", "error_ia", proveedor="IA sin configurar")

    # Los datos del turno solo se guardan cuando hay una respuesta válida de la IA.
    borrador = {**perfil, "exclusiones": perfil["exclusiones"].copy()}
    contexto = contexto_interfaz or {}
    plan, consulta, plato = preparar_turno(texto, borrador, plato, contexto)
    argumentos = (mensaje, consulta, borrador, historial, resumen, plan, plato)
    respuesta, opcion = inteligencia.generar(*argumentos, contexto_interfaz=contexto)
    if respuesta.tipo != "error_ia":
        if opcion == "recomendar":
            borrador["recomendando"] = True
        if opcion.startswith(("precio:", "ingredientes:")):
            borrador["plato"] = opcion.split(":", 1)[1]
        perfil.update(borrador)
    return respuesta


def preparar_turno(texto, perfil, plato, contexto):
    if re.search(r"\b(compara|comparar|diferencia)\b", texto):
        nombres = {clave: normalizar(dato["nombre"]) for clave, dato in PLATOS.items()}
        pares = (
            (primero, segundo)
            for primero, nombre_a in nombres.items()
            for segundo, nombre_b in nombres.items()
            if primero != segundo and (f"{nombre_a} con {nombre_b}" in texto or f"{nombre_a} y {nombre_b}" in texto)
        )
        comparados = max(pares, key=lambda par: sum(len(nombres[clave]) for clave in par), default=())
        if comparados:
            opciones = [PLATOS[clave] for clave in comparados]
            datos = {
                marcador: f'**{dato["nombre"]}** · {soles(dato["precio"])} — {dato["descripcion"].rstrip(".")}'
                for marcador, dato in zip(("PRIMERO", "SEGUNDO"), opciones)
            }
            plan = Plan("comparacion", "Presenta los precios como valores de la carta de muestra. "
                        "Escribe una frase breve, luego una viñeta por plato con solo su marcador, "
                        "y una pregunta breve para ayudar a decidir. Evita repetir o cambiar los sabores de las fichas.",
                        datos, registros=comparados)
            return plan, texto, None

    if contexto.get("etapa") and re.search(r"\b(ayudame a elegir|que cambiarias|que combina|que salsa sugieres)\b", texto):
        plan = Plan("personalizacion", "Orienta sobre la etapa del creador de platos como sugerencia de sabor. "
                    "Usa la selección y las opciones visibles del creador. Menciona una sugerencia concreta "
                    "sin atribuirle precio, disponibilidad ni alérgenos. La combinación es ilustrativa.")
        return plan, texto, None

    if re.fullmatch(
        r"[\s¡¿]*(?:hola+|buenas|buenos dias|buenas tardes|buenas noches)"
        r"(?:[\s,!]+be+l+e+n+)?(?:[\s,.!¿?]+como estas)?[\s,.!¿?]*",
        texto,
    ):
        if perfil["recomendando"] and (perfil["personas"] is None or perfil["presupuesto"] is None):
            pendiente = recomendar(perfil)
            return Plan(pendiente.tipo, "Saluda brevemente. " + pendiente.instruccion, pendiente.datos), texto, None
        return Plan("saludo", "Saluda de forma cordial y ofrece ayuda con la carta o una recomendación."), texto, None

    if re.search(r"\b(ceviche|cebiche|seviche)\b", texto):
        return plan_faq("ceviche"), texto, None

    if re.search(
        r"\bque(?:\s+(?:cosas|comida|platos|opciones|tipo de comida))?\s+"
        r"(?:venden|tienen|ofrecen|sirven|preparan|hay|puedo pedir|se puede pedir)\b"
        r"|\b(?:muestra(?:me)?|ver|conocer)\s+(?:la carta|el menu)\b|\b(?:cual es|como es)\s+(?:la carta|el menu)\b",
        texto,
    ):
        return plan_faq("oferta"), texto, None

    antes = (perfil["personas"], perfil["presupuesto"], tuple(perfil["exclusiones"]), perfil["gusto"])
    if perfil["recomendando"] and perfil["personas"] is None:
        dato_breve = texto.strip(" ¡¿").rstrip(".!?").strip()
        if dato_breve.isdecimal() and (len(dato_breve) > 2 or not 1 <= int(dato_breve) <= 30):
            plan = Plan("aclaracion", "Pide un tamaño de grupo dentro del intervalo indicado.", {"RANGO": "1 a 30 personas"})
            return plan, texto, None
    actualizar_perfil(texto, perfil)
    despues = (perfil["personas"], perfil["presupuesto"], tuple(perfil["exclusiones"]), perfil["gusto"])
    if plato:
        perfil["plato"] = plato

    pide_recomendacion = bool(re.search(
        r"recomiend|recomend|sugier|suger|escog\w*|eleg\w*|"
        r"que (pido|como|podemos pedir)|me alcanza|me conviene|(?:quiero|ayudame a)\s+comer",
        texto,
    ))
    sigue_recomendacion = antes != despues and not plato and (perfil["recomendando"] or perfil["personas"])

    referencia = contexto.get("plato_id") or perfil["plato"]
    if not plato and referencia in PLATOS and re.search(r"\b(cuesta|precio|ingredientes|lleva|contiene|viene)\b", texto):
        if tokens(texto) <= tokens("cuanto cuesta precio ingredientes lleva contiene viene cuanto vale ese esa plato opcion cuesta tiene que y cual"):
            plato = referencia
    if pide_recomendacion or sigue_recomendacion:
        perfil["recomendando"] = True
        return recomendar(perfil), f"{texto} carta porciones precio {perfil['gusto'] or 'combo'}", None
    if plato:
        ingredientes = bool(re.search(r"\b(ingredientes?|lleva|contiene|tiene|hecho|incluye)\b", texto))
        return plan_plato(plato, ingredientes), f"{texto} {PLATOS[plato]['nombre']}", plato

    faq = next((clave for clave, dato in FAQ.items()
                if clave not in ("oferta", "ceviche") and tokens(texto) & tokens(dato["consulta"])), None)
    if faq:
        return plan_faq(faq), f"{texto} {faq}", faq
    if re.search(r"\b(menu|carta|platos|opciones)\b", texto):
        return plan_faq("oferta"), texto, None
    if re.fullmatch(r"(muchas )?(gracias|genial|perfecto|listo|adios|hasta luego)[! .?¡¿]*", texto):
        return Plan("cierre", "Agradece o despídete cordialmente según lo que dijo el usuario."), texto, None
    return None, texto, None
