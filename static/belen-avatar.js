const llamadas = new Map();
const preferenciaVoz = "chinawok-belen-voz";
const estados = {
  lista: "Te escucho. Cuéntame qué te provoca.",
  pensando: "Estoy consultando la carta y recordando lo que me contaste.",
  saludo: "¡Qué gusto saludarte!",
  carta: "Tengo información de la carta para ti.",
  comparacion: "Comparemos las dos opciones.",
  recomendacion: "Encontré una combinación para ti.",
  disponibilidad: "Esto es lo que pude confirmar en la carta.",
  oferta: "Te muestro qué puedes encontrar.",
  personalizacion: "Veamos qué encaja con tu plato.",
  aclaracion: "Cuéntame un poco más y afinamos la búsqueda.",
  precaucion: "Este detalle conviene confirmarlo con el local.",
  error: "Puedes volver a enviarme tu pregunta.",
};

function ruta(estatico) {
  return new URL(`app/static/${estatico}`, document.baseURI).href;
}

function textoParaVoz(texto) {
  return texto.replace(/S\/\s*(\d+)(?:\.(\d\d))?/g, (_, soles, centimos) => (
    `${soles} soles${centimos && centimos !== "00" ? ` con ${Number(centimos)} céntimos` : ""}`
  )).replace(/[*_`#]/g, "").replace(/\s*·\s*|\s+—\s+/g, ". ").replace(/×/g, "por")
    .replace(/^\s*-\s*/gm, "").trim();
}

function montarEscena(contenedor, leerEstado) {
  let destruir = () => {};
  let cancelado = false;
  const canvas = contenedor.querySelector("canvas");
  Promise.all([
    import(ruta("vendor/three.module.min.js")),
    import(ruta("belen-relieve.js")),
  ]).then(([THREE, {montarRelieve}]) => {
    if (!cancelado) destruir = montarRelieve(THREE, canvas, contenedor, leerEstado);
  }).catch(() => { contenedor.dataset.webgl = "respaldo"; });
  return () => { cancelado = true; destruir(); };
}

function crearInstancia(parentElement) {
  const raiz = parentElement.querySelector(".estudio");
  const estado = raiz.querySelector(".estado");
  const mensaje = raiz.querySelector(".mensaje");
  const subtitulo = raiz.querySelector(".subtitulo-voz");
  const botonIniciar = raiz.querySelector('[data-accion="iniciar"]');
  const botonHablar = raiz.querySelector('[data-accion="hablar"]');
  const botonEscuchar = raiz.querySelector('[data-accion="escuchar"]');
  const botonColgar = raiz.querySelector('[data-accion="colgar"]');
  const botonSilenciar = raiz.querySelector('[data-accion="silenciar"]');
  const botonSubtitulos = raiz.querySelector('[data-accion="subtitulos"]');
  const voz = raiz.querySelector("[data-voz]");
  const Reconocer = window.SpeechRecognition || window.webkitSpeechRecognition;
  const sintetizador = window.speechSynthesis;
  const ContextoAudio = window.AudioContext || window.webkitAudioContext;
  const eventos = new AbortController();
  const opciones = {signal: eventos.signal};
  let datos = {};
  let emite;
  let leyendo = false;
  let escuchando = false;
  let alUltimoAcento = -10;
  let sesionAnterior;
  let turnoAnterior;
  let locucion;
  let reconocimiento;
  let auto = false;
  let abriendo = false;
  let finalizando = false;
  let silenciado = false;
  let subtitulosVisibles = false;
  let textoSubtitulo = "";
  let esperandoRespuesta = false;
  let errorMicrofono = false;
  let temporizadorEscucha;
  let liveSocket;
  let liveTokenAnterior;
  let liveSetupCompleto = false;
  let liveFallido = false;
  let flujoMicrofono;
  let contextoAudio;
  let solicitudMicrofono;
  let temporizadorSaludMicrofono;
  let siguienteAudio = 0;
  let fuentesAudio = new Set();
  let ultimoToolResponse;
  let transcripcionSalida = "";
  let ultimoContextoApp;
  let preferenciaGuardada = null;
  try {
    preferenciaGuardada = sessionStorage.getItem(preferenciaVoz);
    auto = preferenciaGuardada === "1";
  } catch {}
  voz.checked = auto;
  voz.disabled = !sintetizador;
  voz.hidden = true;

  function mostrarEstado() {
    const invitacion = datos.modo === "solicitud" && datos.gesto === "lista"
      ? "Cuéntame, ¿cómo te gustaría tu plato? Puedes decirlo por voz." : estados[datos.gesto] || estados.lista;
    const respuesta = datos.gesto !== "pensando" && datos.respuesta ? datos.respuesta : invitacion;
    const enLlamada = datos.modo === "llamada";
    const hablandoLive = fuentesAudio.size > 0;
    const fase = finalizando ? "finalizando" : leyendo || hablandoLive ? "hablando" :
      errorMicrofono ? "sin-microfono" : silenciado ? "silenciado" :
      datos.gesto === "pensando" ? "pensando" : datos.live_token && !liveSetupCompleto ? "conectando" : "escuchando";
    const estadosLlamada = {
      finalizando: "Cerrando la llamada…", hablando: "Belén está hablando",
      "sin-microfono": "Micrófono sin acceso", silenciado: "Micrófono silenciado",
      pensando: "Belén está pensando", conectando: "Conectando con Belén…", escuchando: "Te escucho",
    };
    estado.textContent = enLlamada ? estadosLlamada[fase] :
      escuchando ? "Te estoy escuchando…" : leyendo ? datos.respuesta : respuesta;
    raiz.dataset.fase = fase;
    subtitulo.textContent = datos.live_token ? textoSubtitulo : datos.respuesta || "";
    subtitulo.hidden = !enLlamada || !subtitulosVisibles || !subtitulo.textContent;
    raiz.dataset.gesto = escuchando ? "escuchando" : (datos.gesto || "lista");
    botonEscuchar.disabled = !sintetizador || !datos.respuesta || datos.gesto === "pensando" || escuchando;
    botonEscuchar.hidden = Boolean(datos.live_token);
    botonIniciar.hidden = datos.modo !== "prellamada";
    botonIniciar.disabled = abriendo || datos.gesto === "pensando";
    botonHablar.hidden = datos.modo !== "llamada" || (!datos.live_token && !Reconocer) || !errorMicrofono;
    botonHablar.disabled = datos.gesto === "pensando";
    botonColgar.hidden = datos.modo !== "llamada";
    botonColgar.disabled = finalizando;
    botonSilenciar.hidden = !enLlamada;
    botonSilenciar.disabled = finalizando;
    botonSilenciar.setAttribute("aria-pressed", String(silenciado));
    botonSilenciar.setAttribute("aria-label", silenciado ? "Activar micrófono" : "Silenciar micrófono");
    botonSilenciar.title = botonSilenciar.getAttribute("aria-label");
    botonSubtitulos.hidden = !enLlamada;
    botonSubtitulos.setAttribute("aria-pressed", String(subtitulosVisibles));
    botonSubtitulos.setAttribute("aria-label", subtitulosVisibles ? "Ocultar subtítulos" : "Mostrar subtítulos");
    botonSubtitulos.title = botonSubtitulos.getAttribute("aria-label");
    botonEscuchar.textContent = leyendo ? "Detener voz" : "Escuchar";
    botonHablar.textContent = "Reintentar micrófono";
    raiz.dataset.microfono = !Reconocer ? "no-disponible" :
      errorMicrofono ? "error" : escuchando ? "escuchando" : "automatico";
    if (datos.live_token && datos.live_connected) {
      raiz.dataset.proveedorVoz = "gemini-live";
    } else {
      raiz.dataset.proveedorVoz = "respaldo";
    }
  }

  function emitir(tipo, valores = {}) {
    emite(tipo, {id: `${Date.now()}-${Math.random()}`, ...valores});
  }

  function detenerAudioLive() {
    fuentesAudio.forEach(fuente => {
      try { fuente.stop(); } catch {}
    });
    fuentesAudio.clear();
    siguienteAudio = contextoAudio ? contextoAudio.currentTime : 0;
    mostrarEstado();
  }

  function detenerMicrofonoLive() {
    window.clearInterval(temporizadorSaludMicrofono);
    temporizadorSaludMicrofono = undefined;
    if (contextoAudio?.processor) {
      contextoAudio.processor.disconnect();
      contextoAudio.input?.disconnect();
      contextoAudio.mute?.disconnect();
      contextoAudio.processor = undefined;
    }
    flujoMicrofono?.getTracks().forEach(pista => pista.stop());
    flujoMicrofono = undefined;
  }

  function pistaMicrofonoActiva() {
    return flujoMicrofono?.getAudioTracks().some(pista => pista.readyState === "live") || false;
  }

  function reproducirAudioLive(base64) {
    if (!contextoAudio) return;
    const bytes = Uint8Array.from(atob(base64), caracter => caracter.charCodeAt(0));
    const cantidadMuestras = Math.floor(bytes.byteLength / 2);
    if (!cantidadMuestras) return;
    const vista = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    const buffer = contextoAudio.createBuffer(1, cantidadMuestras, 24000);
    const canal = buffer.getChannelData(0);
    for (let i = 0; i < cantidadMuestras; i += 1) {
      canal[i] = vista.getInt16(i * 2, true) / 32768;
    }
    const fuente = contextoAudio.createBufferSource();
    fuente.buffer = buffer;
    fuente.connect(contextoAudio.destination);
    fuente.onended = () => {
      fuentesAudio.delete(fuente);
      if (!fuentesAudio.size) mostrarEstado();
    };
    const inicio = Math.max(contextoAudio.currentTime, siguienteAudio);
    fuente.start(inicio);
    siguienteAudio = inicio + buffer.duration;
    fuentesAudio.add(fuente);
    if (fuentesAudio.size === 1) mostrarEstado();
  }

  function enviarAudioLive(muestras, frecuencia) {
    if (silenciado || !liveSetupCompleto || liveSocket?.readyState !== WebSocket.OPEN) return;
    const factor = frecuencia / 16000;
    const longitud = Math.floor(muestras.length / factor);
    if (!longitud) return;
    const buffer = new ArrayBuffer(longitud * 2);
    const vista = new DataView(buffer);
    for (let i = 0; i < longitud; i += 1) {
      const posicion = i * factor;
      const inicio = Math.floor(posicion);
      const fraccion = posicion - inicio;
      const muestra = muestras[inicio] * (1 - fraccion) + (muestras[Math.min(inicio + 1, muestras.length - 1)] || 0) * fraccion;
      const pcm = Math.max(-1, Math.min(1, muestra));
      vista.setInt16(i * 2, pcm < 0 ? pcm * 32768 : pcm * 32767, true);
    }
    let binario = "";
    const bytes = new Uint8Array(buffer);
    for (let inicio = 0; inicio < bytes.length; inicio += 8192) {
      binario += String.fromCharCode(...bytes.subarray(inicio, Math.min(inicio + 8192, bytes.length)));
    }
    liveSocket.send(JSON.stringify({
      realtimeInput: {audio: {data: btoa(binario), mimeType: "audio/pcm;rate=16000"}},
    }));
  }

  function adjuntarMicrofonoLive() {
    if (!contextoAudio || !flujoMicrofono || contextoAudio.processor) return;
    const entrada = contextoAudio.createMediaStreamSource(flujoMicrofono);
    const procesador = contextoAudio.createScriptProcessor(4096, 1, 1);
    const silencio = contextoAudio.createGain();
    silencio.gain.value = 0;
    procesador.onaudioprocess = evento => {
      enviarAudioLive(evento.inputBuffer.getChannelData(0), contextoAudio.sampleRate);
    };
    entrada.connect(procesador);
    procesador.connect(silencio);
    silencio.connect(contextoAudio.destination);
    contextoAudio.processor = procesador;
    contextoAudio.input = entrada;
    contextoAudio.mute = silencio;
  }

  async function mantenerMicrofonoLive() {
    if (!liveSetupCompleto || liveFallido || finalizando || datos.modo !== "llamada") return;
    if (solicitudMicrofono) return solicitudMicrofono;

    solicitudMicrofono = (async () => {
      try {
        if (!pistaMicrofonoActiva()) {
          if (flujoMicrofono || contextoAudio?.processor) detenerMicrofonoLive();
          const flujo = await navigator.mediaDevices.getUserMedia({
            audio: {echoCancellation: true, noiseSuppression: true, autoGainControl: true},
          });
          if (finalizando || datos.modo !== "llamada") {
            flujo.getTracks().forEach(pista => pista.stop());
            return;
          }
          flujoMicrofono = flujo;
        }
        flujoMicrofono.getAudioTracks().forEach(pista => { pista.enabled = !silenciado; });
        if (!ContextoAudio) throw new Error("AudioContext no está disponible en este navegador.");
        if (!contextoAudio || contextoAudio.state === "closed") {
          contextoAudio = new ContextoAudio();
        }
        if (contextoAudio.state !== "running") await contextoAudio.resume();
        if (finalizando || datos.modo !== "llamada") return;
        adjuntarMicrofonoLive();
        vigilarMicrofonoLive();
        errorMicrofono = false;
        mensaje.textContent = "";
        mostrarEstado();
      } catch (error) {
        detenerMicrofonoLive();
        errorMicrofono = true;
        const motivo = error?.name === "NotAllowedError" ? "permiso denegado" :
          error?.name === "NotFoundError" ? "no se encontró un micrófono" :
          "no se pudo activar";
        mensaje.textContent = `El micrófono ${motivo}. Pulsa «Reintentar micrófono» para volver a hablar.`;
        mostrarEstado();
      } finally {
        solicitudMicrofono = undefined;
      }
    })();
    return solicitudMicrofono;
  }

  function vigilarMicrofonoLive() {
    window.clearInterval(temporizadorSaludMicrofono);
    temporizadorSaludMicrofono = window.setInterval(() => {
      if (!liveSetupCompleto || liveFallido || finalizando || errorMicrofono) return;
      if (!pistaMicrofonoActiva() || !contextoAudio?.processor || contextoAudio.state === "closed") {
        mantenerMicrofonoLive();
      } else if (contextoAudio.state === "suspended") {
        contextoAudio.resume().catch(() => {
          errorMicrofono = true;
          mensaje.textContent = "El micrófono se pausó. Pulsa «Reintentar micrófono» para continuar.";
          mostrarEstado();
        });
      }
    }, 1200);
  }

  function procesarMensajeLive(mensaje) {
    if (mensaje.setupComplete) {
      liveSetupCompleto = true;
      emitir("live_status", {estado: "conectada"});
      enviarContextoApp();
      if (!datos.app_context?.conversacion_iniciada) {
        liveSocket.send(JSON.stringify({
          realtimeInput: {text: "Saluda brevemente en español y pregunta qué le gustaría comer hoy."},
        }));
      }
      vigilarMicrofonoLive();
      mantenerMicrofonoLive();
      mostrarEstado();
      return;
    }
    if (mensaje.serverContent) {
      const contenido = mensaje.serverContent;
      if (contenido.interrupted) detenerAudioLive();
      if (contenido.outputTranscription?.text) {
        transcripcionSalida += contenido.outputTranscription.text;
        textoSubtitulo = transcripcionSalida.trim();
        if (subtitulosVisibles) mostrarEstado();
      }
      if (contenido.inputTranscription?.text) {
        emitir("live_transcript", {role: "user", text: contenido.inputTranscription.text});
      }
      for (const parte of contenido.modelTurn?.parts || []) {
        if (parte.inlineData?.mimeType?.startsWith("audio/pcm") && parte.inlineData.data) {
          reproducirAudioLive(parte.inlineData.data);
        }
      }
      if (contenido.turnComplete) {
        const texto = transcripcionSalida.trim();
        if (texto) emitir("live_transcript", {role: "assistant", text: texto});
        transcripcionSalida = "";
      }
    }
    if (mensaje.toolCall?.functionCalls?.length) {
      emitir("live_tool_calls", {calls: mensaje.toolCall.functionCalls});
    }
  }

  function conectarGeminiLive() {
    if (!datos.live_token || liveTokenAnterior === datos.live_token || liveFallido) return;
    liveTokenAnterior = datos.live_token;
    const url = new URL(
      "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContentConstrained"
    );
    url.searchParams.set("access_token", datos.live_token);
    liveSocket = new WebSocket(url);
    liveSocket.onopen = () => {
      const config = {
        setup: {
          model: `models/${datos.live_model}`,
          ...datos.live_config,
        },
      };
      liveSocket.send(JSON.stringify(config));
    };
    liveSocket.onmessage = async evento => {
      try {
        const contenido = typeof evento.data === "string" ? evento.data : await evento.data.text();
        const mensaje = JSON.parse(contenido);
        if (mensaje.error) {
          console.error("Gemini Live devolvió un error:", mensaje.error);
          activarRespaldoLive("Gemini Live no pudo procesar la respuesta de voz.");
          return;
        }
        procesarMensajeLive(mensaje);
      } catch (error) {
        console.error("No se pudo procesar un evento de Gemini Live:", error);
        const detalle = error instanceof Error
          ? `${error.name}: ${error.message}`.slice(0, 180)
          : "Error desconocido";
        activarRespaldoLive(`Gemini Live no pudo procesar la respuesta de voz (${detalle}).`);
      }
    };
    liveSocket.onerror = () => activarRespaldoLive("Gemini Live no está disponible; continuaré con la voz de respaldo.");
    liveSocket.onclose = () => {
      if (!finalizando && !liveFallido && datos.modo === "llamada") {
        activarRespaldoLive("La conexión de voz con Gemini Live se interrumpió; continuaré con la voz de respaldo.");
      }
    };
  }

  function activarRespaldoLive(mensajeError) {
    if (liveFallido || finalizando) return;
    liveFallido = true;
    liveSetupCompleto = false;
    if (liveSocket && liveSocket.readyState < WebSocket.CLOSING) liveSocket.close();
    detenerAudioLive();
    detenerMicrofonoLive();
    contextoAudio?.close();
    contextoAudio = undefined;
    emitir("live_error", {message: mensajeError});
  }

  function responderToolLive(respuesta) {
    if (!respuesta?.id || respuesta.id === ultimoToolResponse || !liveSetupCompleto) return false;
    ultimoToolResponse = respuesta.id;
    liveSocket.send(JSON.stringify({
      toolResponse: {functionResponses: respuesta.function_responses},
    }));
    return true;
  }

  function enviarContextoApp() {
    if (!liveSetupCompleto || !datos.app_context) return;
    const contexto = JSON.stringify(datos.app_context);
    if (contexto === ultimoContextoApp) return;
    ultimoContextoApp = contexto;
    liveSocket.send(JSON.stringify({
      clientContent: {
        turns: [{role: "user", parts: [{text: `Contexto actual de la app (dato de interfaz, no una pregunta): ${contexto}`}]}],
        turnComplete: false,
      },
    }));
  }

  async function prepararMicrofonoLlamada() {
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error("microphone unavailable");
      const flujo = await navigator.mediaDevices.getUserMedia({
        audio: {echoCancellation: true, noiseSuppression: true, autoGainControl: true},
      });
      if (finalizando) {
        flujo.getTracks().forEach(pista => pista.stop());
        return;
      }
      flujoMicrofono = flujo;
      if (!ContextoAudio) throw new Error("AudioContext unavailable");
      contextoAudio = new ContextoAudio();
      await contextoAudio.resume();
      if (finalizando) return;
      esperandoRespuesta = false;
      emitir("llamada_iniciada", {token_required: true});
    } catch {
      if (finalizando) return;
      flujoMicrofono?.getTracks().forEach(pista => pista.stop());
      flujoMicrofono = undefined;
      contextoAudio?.close();
      contextoAudio = undefined;
      errorMicrofono = true;
      mensaje.textContent = "No se pudo acceder al micrófono. Puedes reintentarlo durante la llamada.";
      emitir("llamada_iniciada", {token_required: true});
    }
  }

  function detenerEscucha() {
    window.clearTimeout(temporizadorEscucha);
    if (reconocimiento) {
      reconocimiento.onend = reconocimiento.onerror = reconocimiento.onresult = null;
      if (escuchando) reconocimiento.abort();
    }
    reconocimiento = undefined;
    escuchando = false;
  }

  function iniciarEscuchaAutomatica() {
    if (datos.modo !== "llamada" || !Reconocer || silenciado || finalizando || esperandoRespuesta ||
        leyendo || escuchando || errorMicrofono || datos.gesto === "pensando") return;
    reconocimiento = new Reconocer();
    reconocimiento.lang = "es-PE";
    reconocimiento.continuous = false;
    reconocimiento.interimResults = false;
    reconocimiento.onstart = () => {
      errorMicrofono = false;
      escuchando = true;
      mensaje.textContent = "";
      mostrarEstado();
    };
    reconocimiento.onresult = evento => {
      const texto = Array.from(evento.results)
        .filter(resultado => resultado.isFinal)
        .map(resultado => resultado[0].transcript)
        .join(" ").trim().slice(0, 500);
      if (!texto || esperandoRespuesta) return;
      esperandoRespuesta = true;
      reconocimiento.stop();
      emite("dictado", {id: `${Date.now()}-${Math.random()}`, texto});
    };
    reconocimiento.onerror = evento => {
      if (evento.error === "no-speech" || evento.error === "aborted") return;
      errorMicrofono = true;
      mensaje.textContent = evento.error === "not-allowed" || evento.error === "service-not-allowed"
        ? "Permite el micrófono en el navegador para que Belén pueda escucharte."
        : "No se pudo iniciar el micrófono. Reintenta o usa el chat escrito.";
      mostrarEstado();
    };
    reconocimiento.onend = () => {
      escuchando = false;
      reconocimiento = undefined;
      mostrarEstado();
      if (datos.modo === "llamada" && !esperandoRespuesta && !finalizando && !leyendo && !errorMicrofono) {
        temporizadorEscucha = window.setTimeout(iniciarEscuchaAutomatica, 350);
      }
    };
    try {
      reconocimiento.start();
    } catch {
      errorMicrofono = true;
      mensaje.textContent = "No se pudo iniciar el micrófono. Reintenta o usa el chat escrito.";
      mostrarEstado();
    }
  }

  function detenerVoz() {
    if (locucion) {
      locucion.onend = locucion.onerror = locucion.onstart = locucion.onboundary = null;
      sintetizador.cancel();
    }
    locucion = undefined;
    leyendo = false;
  }

  function leer() {
    if (!sintetizador || !datos.respuesta) {
      iniciarEscuchaAutomatica();
      return;
    }
    detenerEscucha();
    detenerVoz();
    const frase = textoParaVoz(datos.respuesta);
    const habla = new SpeechSynthesisUtterance(frase);
    habla.lang = "es-PE";
    habla.rate = .98;
    const voces = sintetizador.getVoices().filter(item => item.lang.toLowerCase().startsWith("es"));
    const locales = voces.filter(item => item.localService);
    const disponibles = locales.length ? locales : voces;
    habla.voice = disponibles.find(item => item.lang.toLowerCase() === "es-pe") ||
      disponibles.find(item => item.lang.toLowerCase() === "es-mx") || disponibles[0] || null;
    habla.onstart = () => { leyendo = true; mensaje.textContent = ""; mostrarEstado(); };
    habla.onboundary = () => { alUltimoAcento = performance.now() / 1000; };
    habla.onend = () => {
      leyendo = false;
      locucion = undefined;
      mostrarEstado();
      iniciarEscuchaAutomatica();
    };
    habla.onerror = () => {
      leyendo = false;
      locucion = undefined;
      mensaje.textContent = "No pude reproducir la voz. Te escucharé de nuevo.";
      mostrarEstado();
      iniciarEscuchaAutomatica();
    };
    locucion = habla;
    sintetizador.speak(habla);
  }

  function finalizarDesdeControl() {
    if (finalizando) return;
    finalizando = true;
    const transcripcion = transcripcionSalida.trim();
    detenerEscucha();
    detenerVoz();
    if (liveSocket && liveSocket.readyState < WebSocket.CLOSING) liveSocket.close();
    liveSetupCompleto = false;
    detenerAudioLive();
    detenerMicrofonoLive();
    if (contextoAudio && contextoAudio.state !== "closed") contextoAudio.close().catch(() => {});
    contextoAudio = undefined;
    transcripcionSalida = "";
    mostrarEstado();
    emitir("llamada_finalizada", {transcripcion});
  }

  function iniciarLlamadaDesdeControl() {
    if (!datos.live_token && !abriendo) {
      abriendo = true;
      finalizando = false;
      silenciado = false;
      textoSubtitulo = "";
      errorMicrofono = false;
      mensaje.textContent = "";
      mostrarEstado();
      prepararMicrofonoLlamada();
      return;
    }
  }

  botonIniciar.addEventListener("click", iniciarLlamadaDesdeControl, opciones);
  botonHablar.addEventListener("click", () => {
    errorMicrofono = false;
    mensaje.textContent = "";
    if (datos.live_token) {
      if (liveSetupCompleto) mantenerMicrofonoLive();
      else mensaje.textContent = "Estoy conectando la llamada. Enseguida podrás reintentar el micrófono.";
    } else {
      iniciarEscuchaAutomatica();
    }
  }, opciones);
  botonColgar.addEventListener("click", finalizarDesdeControl, opciones);
  botonSilenciar.addEventListener("click", () => {
    silenciado = !silenciado;
    flujoMicrofono?.getAudioTracks().forEach(pista => { pista.enabled = !silenciado; });
    if (silenciado) {
      detenerEscucha();
    } else if (datos.live_token && liveSetupCompleto) {
      mantenerMicrofonoLive();
    } else if (!datos.live_token) {
      iniciarEscuchaAutomatica();
    }
    mostrarEstado();
  }, opciones);
  botonSubtitulos.addEventListener("click", () => {
    subtitulosVisibles = !subtitulosVisibles;
    mostrarEstado();
  }, opciones);
  botonEscuchar.addEventListener("click", () => {
    if (leyendo || locucion) { detenerVoz(); mostrarEstado(); } else { leer(); }
  }, opciones);
  voz.addEventListener("change", () => {
    auto = voz.checked;
    preferenciaGuardada = auto ? "1" : "0";
    try { sessionStorage.setItem(preferenciaVoz, preferenciaGuardada); } catch {}
    if (auto && datos.respuesta) leer();
    if (!auto) { detenerVoz(); mostrarEstado(); }
  }, opciones);

  const desmontarEscena = montarEscena(raiz.querySelector(".escena"), () => ({
    gesto: datos.gesto, hablando: leyendo || fuentesAudio.size > 0,
    escucha: !silenciado && (escuchando || liveSetupCompleto), acento: alUltimoAcento, modo: datos.modo,
  }));
  return {
    montarEn(parentElement) {
      const nuevaRaiz = parentElement.querySelector(".estudio");
      if (nuevaRaiz && nuevaRaiz !== raiz) nuevaRaiz.replaceWith(raiz);
    },
    actualizar(nuevosDatos, enviar) {
      emite = enviar;
      const primerRender = sesionAnterior === undefined;
      const nuevoTurno = sesionAnterior === nuevosDatos.sesion && turnoAnterior !== nuevosDatos.turno;
      const inicioLlamada = datos.modo === "prellamada" && nuevosDatos.modo === "llamada";
      if (nuevosDatos.gesto === "pensando" || sesionAnterior !== nuevosDatos.sesion) {
        detenerEscucha();
        detenerVoz();
      }
      if (inicioLlamada) {
        abriendo = false;
        esperandoRespuesta = false;
        detenerEscucha();
      }
      if (nuevoTurno) esperandoRespuesta = false;
      sesionAnterior = nuevosDatos.sesion;
      turnoAnterior = nuevosDatos.turno;
      datos = nuevosDatos;
      if (datos.modo !== "llamada" && liveSocket) {
        liveFallido = true;
        if (liveSocket.readyState < WebSocket.CLOSING) liveSocket.close();
        liveSocket = undefined;
        liveSetupCompleto = false;
        detenerAudioLive();
        detenerMicrofonoLive();
        contextoAudio?.close();
        contextoAudio = undefined;
      }
      if (datos.modo === "llamada") {
        auto = true;
      } else if (preferenciaGuardada === null) {
        auto = Boolean(datos.voz_automatica);
        voz.checked = auto;
      }
      raiz.dataset.modo = datos.modo;
      raiz.dataset.compacto = String(Boolean(datos.compacto));
      if (datos.modo === "portada" || datos.modo === "banda") raiz.setAttribute("aria-hidden", "true");
      if (datos.modo === "llamada" && !datos.live_token && !Reconocer) {
        mensaje.textContent = "Este navegador no permite la asistencia por voz. Abre el chat escrito para continuar.";
      }
      mostrarEstado();
      if (datos.live_token) {
        liveFallido = false;
        conectarGeminiLive();
        if (responderToolLive(datos.live_tool_response)) {
          ultimoContextoApp = JSON.stringify(datos.app_context);
        } else {
          enviarContextoApp();
        }
      } else if (datos.modo === "llamada") {
        if (liveSocket || contextoAudio) {
          liveFallido = true;
          if (liveSocket && liveSocket.readyState < WebSocket.CLOSING) liveSocket.close();
          liveSocket = undefined;
          liveSetupCompleto = false;
          detenerAudioLive();
          detenerMicrofonoLive();
          contextoAudio?.close();
          contextoAudio = undefined;
        }
        liveFallido = false;
        liveTokenAnterior = undefined;
        if (!esperandoRespuesta && !errorMicrofono) iniciarEscuchaAutomatica();
      }
      if (!datos.live_token && (nuevoTurno || primerRender || inicioLlamada) && auto &&
          datos.respuesta && datos.gesto !== "pensando") {
        leer();
      } else if (!datos.live_token && datos.modo === "llamada" &&
                 !esperandoRespuesta && datos.gesto !== "pensando") {
        iniciarEscuchaAutomatica();
      }
    },
    destruir() {
      finalizando = true;
      eventos.abort();
      detenerEscucha();
      detenerVoz();
      if (liveSocket && liveSocket.readyState < WebSocket.CLOSING) liveSocket.close();
      detenerAudioLive();
      detenerMicrofonoLive();
      contextoAudio?.close();
      desmontarEscena();
    },
  };
}

export default function ({parentElement, data, setTriggerValue}) {
  if (!["prellamada", "llamada"].includes(data.modo)) {
    const instancia = crearInstancia(parentElement);
    instancia.actualizar(data, setTriggerValue);
    return () => instancia.destruir();
  }

  // Streamlit desmonta el componente al actualizar sus datos. Reusa la sesión
  // de audio cuando la nueva vista vuelve a montar la misma llamada.
  const sesion = data.sesion;
  const anterior = llamadas.get(sesion);
  window.clearTimeout(anterior?.cierre);
  const llamada = {instancia: anterior?.instancia ?? crearInstancia(parentElement)};
  llamadas.set(sesion, llamada);
  llamada.instancia.montarEn(parentElement);
  llamada.instancia.actualizar(data, setTriggerValue);
  return () => {
    if (llamadas.get(sesion) !== llamada) return;
    llamada.cierre = window.setTimeout(() => {
      llamada.instancia.destruir();
      llamadas.delete(sesion);
    }, data.modo === "llamada" ? 1200 : 250);
  };
}
