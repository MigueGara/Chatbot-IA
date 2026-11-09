"""Componente WebGL y controles de voz de Belén."""

from pathlib import Path

import streamlit.components.v2 as components

STATIC = Path(__file__).parent / "static"
ICONOS = {
    "voz": '<path d="M3 10v4m4-7v10m5-14v18m5-14v10m4-7v4"/>',
    "microfono": '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11v1a7 7 0 0 0 14 0v-1m-7 8v3m-3 0h6"/>',
    "subtitulos": '<rect x="3" y="5" width="18" height="14" rx="3"/><path d="M10 10H8a2 2 0 0 0 0 4h2m7-4h-2a2 2 0 0 0 0 4h2"/>',
    "salir": '<path d="m6 6 12 12M18 6 6 18"/>',
}


def icono(nombre):
    return ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.85" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICONOS[nombre]}</svg>')


HTML = f"""
<section class="estudio" aria-label="Belén, asistente virtual">
  <div class="escena">
    <span class="retrato-respaldo" aria-hidden="true"></span>
    <canvas aria-label="Avatar tridimensional de Belén"></canvas>
  </div>
  <div class="panel">
    <span class="identidad">ASISTENTE IA</span>
    <h1>Belén</h1>
    <p class="estado" role="status" aria-live="polite"></p>
    <p class="subtitulo-voz" hidden></p>
    <div class="controles">
      <button type="button" data-accion="iniciar" aria-label="Iniciar modo voz" title="Iniciar modo voz">{icono("voz")}</button>
      <button type="button" data-accion="hablar" title="Reintentar el acceso al micrófono">Reintentar micrófono</button>
      <button type="button" data-accion="escuchar" title="Escuchar la última respuesta">Escuchar</button>
      <button type="button" data-accion="silenciar" aria-label="Silenciar micrófono" title="Silenciar micrófono" aria-pressed="false">{icono("microfono")}</button>
      <button type="button" data-accion="subtitulos" aria-label="Mostrar subtítulos" title="Mostrar subtítulos" aria-pressed="false">{icono("subtitulos")}</button>
      <button type="button" data-accion="colgar" aria-label="Finalizar llamada" title="Finalizar llamada">{icono("salir")}</button>
    </div>
    <label class="voz-auto"><input type="checkbox" data-voz> Voz automática</label>
    <p class="mensaje" role="status"></p>
  </div>
</section>
"""

_componente = components.component(
    "belen_3d",
    html=HTML,
    css=(STATIC / "belen-avatar.css").read_text(encoding="utf-8")
    + "\n" + (STATIC / "conversacion-avatar.css").read_text(encoding="utf-8"),
    js=(STATIC / "belen-avatar.js").read_text(encoding="utf-8"),
)


def mostrar_belen(
    *, gesto, sesion, turno=0, respuesta="", modo="voz", voz_automatica=False, compacto=False,
    live_token="", live_model="", live_config=None, live_tool_response=None, live_error="",
    live_connected=False, app_context=None,
    clave="belen_3d_en_chat",
):
    return _componente(
        key=clave,
        data={
            "gesto": gesto, "sesion": sesion, "turno": turno, "respuesta": respuesta,
            "modo": modo, "voz_automatica": voz_automatica, "compacto": compacto,
            "live_token": live_token, "live_model": live_model, "live_config": live_config or {},
            "live_tool_response": live_tool_response or {}, "live_error": live_error,
            "live_connected": live_connected, "app_context": app_context or {},
        },
        on_dictado_change=lambda: None,
        on_llamada_iniciada_change=lambda: None,
        on_llamada_finalizada_change=lambda: None,
        on_live_status_change=lambda: None,
        on_live_transcript_change=lambda: None,
        on_live_tool_calls_change=lambda: None,
        on_live_error_change=lambda: None,
    )
