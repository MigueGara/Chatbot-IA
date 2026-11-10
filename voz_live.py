"""Configuración y acceso seguro a Gemini Live para la asistencia por voz."""

from datetime import datetime, timedelta, timezone

from belen import PLATOS

MODELO_LIVE = "gemini-3.8-live"
VOZ_LIVE = "Kore"


class ErrorLiveAPI(RuntimeError):
    """Error de configuración o conexión con Gemini Live."""


DECLARACIONES = [
    {
        "name": "navigate_screen",
        "description": (
            "Abre una sección de China Wok AI. Úsala cuando la persona quiera ver la carta, "
            "personalizar su plato, volver al inicio o revisar su pedido."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "screen": {
                    "type": "STRING",
                    "enum": ["menu", "customizer", "order", "home"],
                },
                "dish_id": {"type": "STRING"},
            },
            "required": ["screen"],
        },
    },
    {
        "name": "select_custom_options",
        "description": (
            "Selecciona en el creador las opciones que la persona acaba de pedir por voz. "
            "Usa los nombres de las opciones visibles; puedes seleccionar varias verduras."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "options": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                },
            },
            "required": ["options"],
        },
    },
    {
        "name": "recommend_menu",
        "description": (
            "Obtiene alternativas calculadas con el catálogo local para el grupo y presupuesto "
            "que la persona confirmó. Úsala antes de recomendar opciones con precio."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "people": {"type": "INTEGER"},
                "budget_soles": {"type": "NUMBER"},
            },
            "required": ["people", "budget_soles"],
        },
    },
    {
        "name": "add_menu_dish",
        "description": (
            "Agrega al carrito local un plato existente de la carta cuando la persona lo pida "
            "claramente. No confirma el pedido ni realiza un pago."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "dish_id": {"type": "STRING"},
                "quantity": {"type": "INTEGER"},
                "spicy": {"type": "STRING"},
                "extras": {"type": "ARRAY", "items": {"type": "STRING"}},
            },
            "required": ["dish_id"],
        },
    },
    {
        "name": "add_customized_dish",
        "description": (
            "Agrega al carrito el plato personalizado actual o repite el último plato personalizado "
            "que se agregó. Usa quantity para agregar varias unidades en una sola acción; no obligues "
            "a la persona a repetir el proceso uno por uno."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {"quantity": {"type": "INTEGER"}},
        },
    },
    {
        "name": "update_order_quantity",
        "description": (
            "Actualiza la cantidad de cualquier plato que ya esté en el pedido. Usa quantity como "
            "cantidad final; usa 0 para quitarlo. Sirve para agregar o disminuir unidades sin repetir "
            "la personalización."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "dish_id": {"type": "STRING"},
                "quantity": {"type": "INTEGER"},
            },
            "required": ["dish_id", "quantity"],
        },
    },
]


def crear_configuracion_live():
    carta = "\n".join(
        f"- {plato['id']}: {plato['nombre']}; {plato['descripcion']} "
        f"Ingredientes: {', '.join(plato['ingredientes'])}. Precio de muestra: "
        f"S/ {plato['precio'] // 100}.{plato['precio'] % 100:02d}."
        for plato in PLATOS.values()
    )
    instrucciones = f"""Eres Belén, la asistente por voz de China Wok AI.
Habla siempre en español latinoamericano natural, con calidez, pronunciación clara y ritmo conversacional. Usa un estilo femenino, cercano y amable; si es natural, emplea expresiones peruanas suaves, sin exagerarlas. Responde en frases breves, con pausas naturales.
Ayuda únicamente con la carta y las pantallas de esta app. No inventes productos, ingredientes, precios, disponibilidad ni funciones. Los precios son ilustrativos.
Carta local:
{carta}

Cuando la persona quiera navegar, usa navigate_screen para abrir la pantalla real antes de decir que ya la abriste. Si pide personalizar su plato, abre customizer; el creador mostrará las opciones y la persona puede elegirlas hablando o tocando la pantalla. Cuando mencione una opción válida de la etapa actual, usa select_custom_options; no afirmes que la seleccionaste hasta recibir confirmación.
Antes de recomendar con precios según grupo y presupuesto, confirma ambos datos y usa recommend_menu. Si la persona elige un plato de la carta y pide agregarlo, usa add_menu_dish. Si termina de personalizar una combinación y pide añadirla, usa add_customized_dish. Si pide otra unidad o varias unidades de la misma combinación, vuelve a usar add_customized_dish con quantity; no le digas que debe repetir el proceso uno por uno. Para aumentar, disminuir o quitar cualquier línea ya agregada, usa update_order_quantity con la cantidad final y el identificador del pedido. Al recomendar un plato, puedes abrir la carta usando navigate_screen con screen=menu. Antes de entrar al pedido, acompaña la elección; al llegar al pedido, explica con amabilidad que la confirmación final y el pago los realiza la persona, no tú. No completes ni afirmes pagos.
Usa el contexto actual de la app para no perder la pantalla, las opciones seleccionadas ni el contenido del carrito. Si una alternativa no alcanza para todo el grupo o supera el presupuesto, dilo con claridad y ofrece una opción realista; no inventes precios ni disponibilidad. La app solo guarda un pedido de muestra local.
Si no entiendes una opción o no aparece en la carta, pregunta o aclara en lugar de adivinar. No repitas respuestas largas ni menciones que eres un modelo."""

    return {
        "response_modalities": ["AUDIO"],
        "speech_config": {
            "voice_config": {"prebuilt_voice_config": {"voice_name": VOZ_LIVE}},
        },
        "input_audio_transcription": {},
        "output_audio_transcription": {},
        "system_instruction": {"parts": [{"text": instrucciones}]},
        "tools": [{"function_declarations": DECLARACIONES}],
    }


def crear_configuracion_websocket():
    from google.genai import types

    configuracion = types.LiveConnectConfig.model_validate(
        crear_configuracion_live()
    ).model_dump(mode="json", by_alias=True, exclude_none=True)
    generacion = {
        clave: configuracion.pop(clave)
        for clave in ("responseModalities", "speechConfig")
    }
    return {**configuracion, "generationConfig": generacion}


def crear_token_live(api_key):
    if not isinstance(api_key, str) or not api_key.strip():
        raise ErrorLiveAPI("Configura GEMINI_API_KEY para iniciar la voz neuronal.")

    import httpx
    from google import genai
    from google.genai import types
    from google.genai.errors import APIError

    ahora = datetime.now(timezone.utc)
    try:
        cliente = genai.Client(
            api_key=api_key.strip(),
            http_options=types.HttpOptions(api_version="v1alpha"),
        )
        token = cliente.auth_tokens.create(config={
            "uses": 1,
            "new_session_expire_time": ahora + timedelta(minutes=1),
            "expire_time": ahora + timedelta(minutes=20),
            "live_connect_constraints": {
                "model": MODELO_LIVE,
                "config": crear_configuracion_live(),
            },
        })
    except (APIError, httpx.HTTPError, TimeoutError, ValueError) as error:
        raise ErrorLiveAPI("No se pudo crear una sesión de voz de Gemini Live.") from error
    if not token.name:
        raise ErrorLiveAPI("Gemini no devolvió un token efímero para Live API.")
    return token.name
