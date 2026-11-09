# China Wok AI con Belén

Aplicación en español cuyo foco es Belén, un chatbot conectado a Gemini o Groq. El chat conserva el contexto de la conversación y consulta una base de conocimiento local. Puedes alternar entre chat escrito y una pantalla de voz de Belén. Las solicitudes para abrir la carta, un plato o el creador te llevan a esas pantallas dentro de la app.

El pedido y el pago son siempre simulados: la aplicación no envía órdenes al restaurante ni cobra. Los platos y precios de `data/carta.json` son datos locales de referencia, no se actualizan desde un sistema de China Wok y no deben tomarse como disponibilidad ni precios vigentes.

## Abrir en Visual Studio Code

En Windows, haz doble clic en `Iniciar-Belen.cmd` dentro de la carpeta `ChinaWokAI`. El archivo inicia Streamlit con el Python del entorno del proyecto, que contiene las dependencias de Gemini y ChromaDB.

También puedes abrir la carpeta `ChinaWokAI` en VS Code desde **Archivo → Abrir carpeta** y ejecutar esto en **Terminal → Nueva terminal**.

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Si estás instalando el proyecto por primera vez, crea el entorno con Python 3.11 o posterior e instala las dependencias.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Abre la URL local que imprime Streamlit. En VS Code puedes seleccionar el intérprete de `.venv` con **Python: Select Interpreter**.

## Configurar la IA

1. Instala `requirements.txt` en el entorno que ejecutará la app.
2. Copia `.streamlit/secrets.example.toml` a `.streamlit/secrets.toml` y agrega tu clave de Gemini o Groq. Basta con configurar uno. No compartas ni subas el archivo con claves al repositorio.
3. Reinicia Streamlit y pulsa **Chatear con Belén**. Pregunta «¿Qué lleva el pollo tipakay?» y verifica el proveedor mostrado en el chat o en el CSV de métricas. Gemini es el proveedor principal y Groq se usa como respaldo si está configurado.

LangChain busca fichas en ChromaDB y envía al modelo la consulta, el perfil temporal, un resumen y los últimos ocho mensajes. Gemini o Groq redacta el mensaje en español y selecciona una opción vinculada con las fichas. El prompt exige marcadores para precios, ingredientes y demás datos verificados. El código valida esos marcadores y los sustituye con valores de la carta. El cálculo de porciones y totales se hace en Python. El índice usa palabras normalizadas. Puedes configurar un modelo de embeddings compatible en `GEMINI_EMBEDDINGS_MODEL`.

Gemini se configura como proveedor principal y Groq como respaldo. El modelo de Groq predeterminado es `openai/gpt-oss-20b`, el reemplazo recomendado para Llama 3.1 8B en los planes de desarrollo. [Aviso de Groq](https://console.groq.com/docs/deprecations)

Sin una clave, se pueden recorrer las pantallas, pero no se generan respuestas conversacionales. Las validaciones de entrada, el aviso de alérgenos y la derivación de reclamos son mensajes del sistema. **Nueva conversación** borra el perfil, el historial y las métricas de la sesión. El proveedor de IA recibe la consulta y el contexto necesario para responder; evita enviar datos personales.

## Uso del chatbot

1. En Inicio, pulsa **Chatear con Belén** y pregunta por la carta, los ingredientes o una recomendación.
2. Para una recomendación, escribe «¿Qué me recomiendas?» y responde cuántas personas son y cuál es el presupuesto. El cálculo usa los datos locales de referencia.
3. Escribe «sin mariscos» y comprueba que Belén mantiene el grupo y presupuesto. Si el presupuesto no alcanza para cubrir al grupo, comprueba que ofrece una alternativa parcial y una combinación completa con la diferencia, sin afirmar que la parcial alcanza para todos.
4. Escribe «¿Puedo comer esto si soy alérgico a la soya?». Belén debe derivar al local para confirmar ingredientes y contaminación cruzada.
5. Escribe «muéstrame la carta» o «quiero ver pollo tipakay» para abrir la pantalla interna correspondiente. Las respuestas usan el catálogo local de muestra; la app no abre páginas externas.
6. El menú y el creador permiten armar un pedido de prueba; su confirmación es local y no se envía al restaurante ni inicia un pago.

## Voz y avatar

El botón de ondas junto al campo de texto abre el **modo voz**. Puedes silenciar el micrófono, activar los subtítulos o elegir **Ver chat** para seguir escribiendo con la llamada abierta. Al finalizar, los turnos hablados siguen disponibles en el mismo hilo.

Belén usa Gemini Live para escuchar y responder automáticamente con audio neuronal, admitir interrupciones y conservar la conversación mientras navegas por la app. El navegador recibe un token efímero. Configura `GEMINI_API_KEY` como secreto de Streamlit o variable de entorno del servidor. Si Live no está disponible, la app vuelve al dictado y a la síntesis de voz del navegador. El modo voz requiere permiso de micrófono y un contexto seguro (localhost o HTTPS).

Belén puede calcular varias recomendaciones desde el catálogo local, abrir las pantallas de carta, creador y pedido, y agregar platos seleccionados o personalizados al pedido de muestra. El resumen y el subtotal se comparten con la llamada para conservar el contexto entre pantallas. La confirmación del pedido y cualquier pago siguen siendo responsabilidad de la persona usuaria; la app no envía órdenes ni cobra.

El relieve está en `static/belen-relieve.js` y la integración de voz en `static/belen-avatar.js`. La malla curvada reproduce las ilustraciones de frente y permite movimientos de profundidad y boca. Three.js 0.183.2 se sirve desde `static/vendor/` con su licencia MIT. En dispositivos sin WebGL se muestra la ilustración. [Documentación de Three.js](https://threejs.org/manual/pages/installation.html) · [Síntesis de voz de respaldo del navegador](https://developer.chrome.com/blog/web-apps-that-talk-introduction-to-the-speech-synthesis-api)

El relieve está en `static/belen-relieve.js` y la integración de voz en `static/belen-avatar.js`. La malla curvada reproduce las ilustraciones de frente y permite movimientos de profundidad y boca. Three.js 0.183.2 se sirve desde `static/vendor/` con su licencia MIT. En dispositivos sin WebGL se muestra la ilustración. [Documentación de Three.js](https://threejs.org/manual/pages/installation.html) · [Síntesis de voz en Chrome](https://developer.chrome.com/blog/web-apps-that-talk-introduction-to-the-speech-synthesis-api)

El CSV contiene turno, tipo de respuesta, proveedor y latencia.

## Pruebas del proyecto

Desde la carpeta del proyecto, ejecuta las pruebas automatizadas. Usan ChromaDB con los datos locales y simulan respuestas para verificar memoria, recuperación, validación de precios y manejo de errores.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Para comprobar la conexión con el proveedor real, configura una clave y ejecuta también la prueba en vivo. Envía una consulta de ejemplo y registra el proveedor y la latencia.

```powershell
$env:BELEN_PRUEBA_EN_VIVO = '1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
Remove-Item Env:BELEN_PRUEBA_EN_VIVO
```

Verificación en vivo: Gemini respondió correctamente a «¿Qué lleva el pollo tipakay?» mediante la interfaz de Streamlit.

## Archivos principales

| Archivo | Contenido |
|---|---|
| `app.py` | Interfaz, navegación, avatar, sesión y métricas |
| `belen.py` | Carta, perfil, validaciones y recomendaciones |
| `ia.py` | Recuperación en Chroma y selección del proveedor |
| `pedido_demo.py` | Pedido y confirmación simulados en sesión; no cobra ni envía órdenes |
| `data/carta.json` | Base local de platos, precios de referencia y preguntas frecuentes |
| `static/` | Ilustraciones de referencia y estilos |

Para publicar en Streamlit Community Cloud, usa un repositorio con la carpeta del proyecto, selecciona `app.py` como punto de entrada y configura los secretos en el panel del despliegue. [Guía de despliegue](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app)

## Recursos visuales de la interfaz

La herramienta integrada de generación de imágenes produjo los recursos de la versión del restaurante. Se usaron las ilustraciones entregadas como referencia de Belén y se optimizaron los archivos para la web.

| Archivo | Instrucción de generación |
|---|---|
| `static/belen-prototipo-cuerpo.png` | Recorte transparente de cuerpo completo de la Belén ilustrada, conservando su rostro, lentes, cabello, blazer negro con ribetes rojos, pantalón con dragón bordado y zapatillas blancas. Pose de bienvenida con una mano en la cadera y la otra hacia el globo. |
| `static/belen-prototipo-poses.png` | Cuadrícula transparente de cuatro poses coherentes con la ilustración original. Saludo, mano junto al oído, mano en la barbilla y respuesta con la palma abierta. |
| `static/restaurante-prototipo.jpg` | Fondo vertical nocturno de restaurante chifa, con faroles rojos, madera oscura, luz ámbar y piso de baldosas. |
| `static/ingredientes-prototipo.png` | Captura del usuario que sirve de referencia para las miniaturas de ingredientes. |

Los tres recursos se generaron con la herramienta integrada de generación de imágenes. Se redujo su tamaño para la web. Las fotos son ilustrativas.

<details>
<summary>Archivos e instrucciones de generación</summary>

- `static/belen-gestos.png`. Create one very wide 3-panel sprite sheet asset for a polished mobile chifa restaurant web app. Use attached Belén drawing as character identity reference only. Reinterpret her as high-end stylized 3D animated character: dark long softly wavy hair with side part, thick black rectangular glasses, warm expressive eyes, dark navy tailored blazer with fine vermilion red mandarin trim and dark charcoal tee. Same face, same outfit, same proportions, same camera in all three images. Three separate centered upper-body portraits at the exact horizontal centers of three equal-width columns, same top and bottom alignment, ample transparent padding around silhouettes, no overlapping and no panels drawn. Left: smiling with one subtle hello gesture, hands visible near chest. Center: thoughtful, slight head tilt, hand near chin. Right: pleased, gesturing gently with open palm as though presenting a suggestion. Cinematic soft studio lighting, beautifully sculpted subtle materials, friendly young adult professional, natural stylized proportions, excellent glasses. All three rendered against genuinely transparent alpha with no drop shadow, no background, no letters or graphics. Composition bust portraits framed from top of hair through chest, all heads fully visible and large with consistent scale.
- `static/carta-fotos.jpg`. One square 3 by 3 contact sheet of nine separate premium editorial food photographs for an attractive Peruvian chifa restaurant ordering app. Exactly three equal columns and three equal rows, each cell edge-to-edge photo, no margins, no visible separators, no labels, no lettering. Each subject is centered in its own cell with breathing room, viewed slightly elevated (about 45 degrees) in dark ceramic bowls or plates. Across every cell consistent warm parchment studio tabletop, natural directional soft light, saturated but realistic glossy restaurant food. Top row left to right: chicken chaufa rice with visible diced chicken, egg and scallion; stir fried noodles with strips of chicken, tomato and red onion; Peruvian lomo saltado beef with thick fries, red onion and tomato. Middle row: shiny amber sweet tipakay chicken with bell pepper and pineapple; seafood chaufa fried rice with visible shrimp and squid; golden tofu cubes with broccoli and carrot and white rice. Bottom row: two separate small dishes of fried rice and glazed chicken as a duo; three sharing dishes of chicken chaufa, noodles and glazed chicken; one appetizing medium black bowl of mixed fried rice and colorful vegetables representing a custom wok bowl. Do not repeat the same dish appearance. Commercial restaurant menu photography. No people, hands, text, graphics, dividers, or watermarks.
- `static/chaufa-portada.png`. Transparent cutout hero asset for a modern Peru chifa mobile restaurant app. One abundant round matte black ceramic bowl filled with authentic Peruvian chicken arroz chaufa, wok-fried rice, diced glazed chicken, diced cooked egg, finely cut scallions, bright red pepper and a little fresh cilantro. Tight commercial food photography, viewed at elevated 38-degree three quarter angle, bowl fills nearly all canvas, intact round silhouette, offset gently to the right, small margin all around. Individual rice grains look real, subtle wok glaze with warm directional light, high appetite appeal. Add a tiny bit of airy steam directly over the food only if naturally visible. Genuine transparent alpha around entire bowl, no table or background, no ground shadow, no chopsticks, no people, no text, no logo. This image will overlap the right edge of a red hero card in a mobile UI and should be instantly recognizable at small sizes.

</details>
