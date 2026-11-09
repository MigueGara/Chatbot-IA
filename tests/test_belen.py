import json
import os
import unittest
from pathlib import Path
from types import SimpleNamespace

from belen import destino_navegacion, nuevo_perfil, recomendar, responder
from ia import Inteligencia, crear_indice


class ModeloDePrueba:
    def __init__(self, mensajes):
        self.mensajes = iter(mensajes)
        self.solicitudes = []

    def invoke(self, mensajes):
        self.solicitudes.append(json.loads(mensajes[-1][1]))
        salida = next(self.mensajes)
        if isinstance(salida, Exception):
            raise salida
        opcion, texto = salida
        return SimpleNamespace(text=json.dumps({"opcion": opcion, "mensaje": texto}))


class PruebasBelen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.indice = crear_indice({"gemini_key": "", "embedding_model": ""})

    def motor(self, mensajes, respaldo=()):
        ia = Inteligencia.__new__(Inteligencia)
        ia.indice = self.indice
        principal = ModeloDePrueba(mensajes)
        ia.proveedores = [("Gemini", principal)]
        if respaldo:
            ia.proveedores.append(("Groq", ModeloDePrueba(respaldo)))
        return ia, principal

    def test_saludo_y_recomendacion_en_varios_turnos(self):
        motor, modelo = self.motor([
            ("responder", "¡Hola! Cuéntame qué tienes ganas de comer."),
            ("responder", "Claro, ¿para cuántas personas te gustaría pedir?"),
            ("responder", "Perfecto, son [[GRUPO]]. ¿Cuánto quieren gastar en total?"),
            (
                "responder",
                "Puedo ofrecerte estas opciones:\n\n"
                "- [[OPCIONUNO]]\n\n- [[OPCIONDOS]]\n\n- [[OPCIONTRES]]",
            ),
        ])
        perfil, historial = nuevo_perfil(), []
        for texto in ("Hola beleeen", "¿Qué me recomiendas?", "5", "120"):
            respuesta = responder(texto, perfil, historial, inteligencia=motor)
            self.assertEqual(respuesta.proveedor, "Gemini")
            historial.extend([("user", texto), ("assistant", respuesta.texto)])
        self.assertEqual((perfil["personas"], perfil["presupuesto"]), (5, 12000))
        self.assertIn("S/ 110.80", respuesta.texto)
        self.assertEqual(modelo.solicitudes[-1]["historial"][-2][1], "5")
        self.assertIn("familiar", modelo.solicitudes[-1]["fichas"])

    def test_belen_se_presenta_con_un_error_de_escritura(self):
        motor, modelo = self.motor([
            ("responder", "¡Sí! Soy [[IDENTIDAD]]. ¿Te gustaría ver la carta?"),
            ("opcion_inexistente", "Hola."),
        ])
        perfil = nuevo_perfil()
        perfil["recomendando"] = True

        generada = responder("erees belen?", perfil, inteligencia=motor)
        respaldo = responder("¿Quién eres?", perfil, inteligencia=motor)

        self.assertEqual(generada.proveedor, "Gemini")
        self.assertEqual(list(modelo.solicitudes[0]["opciones"]), ["responder"])
        self.assertEqual(respaldo.proveedor, "Sistema")
        for respuesta in (generada, respaldo, responder("¿Cómo te llamas?", perfil)):
            self.assertEqual(respuesta.tipo, "saludo")
            self.assertIn("Belén, la asistente virtual de China Wok", respuesta.texto)
        self.assertTrue(perfil["recomendando"])

    def test_recomendacion_ofrece_varias_combinaciones_y_respeta_el_presupuesto(self):
        perfil = nuevo_perfil()
        perfil.update(personas=5, presupuesto=12000, recomendando=True)

        plan = recomendar(perfil)

        self.assertEqual(plan.tipo, "recomendacion")
        self.assertEqual(len(plan.datos), 3)
        self.assertIn("S/ 110.80", plan.datos["OPCIONUNO"])
        self.assertIn("OPCIONTRES", plan.datos)

    def test_si_no_alcanza_ofrece_alternativa_parcial_y_explica_el_limite(self):
        perfil = nuevo_perfil()
        perfil.update(personas=5, presupuesto=5000, recomendando=True)

        plan = recomendar(perfil)

        self.assertEqual(plan.tipo, "recomendacion")
        self.assertIn("Ninguna combinación completa entra", plan.instruccion)
        self.assertTrue(any("supera el presupuesto" in opcion for opcion in plan.datos.values()))
        self.assertTrue(any("faltaría completar para 5" in opcion for opcion in plan.datos.values()))

    def test_no_recomienda_ingredientes_excluidos_como_alternativa(self):
        perfil = nuevo_perfil()
        perfil.update(personas=1, presupuesto=5000, recomendando=True)
        perfil["exclusiones"] = ["mariscos", "pescado", "gluten", "soya", "maní", "huevo", "cebolla", "pollo", "carne"]

        plan = recomendar(perfil)

        self.assertEqual(plan.tipo, "sin_resultado")
        self.assertIn("No recomiendes un ingrediente excluido", plan.instruccion)

    def test_redaccion_generada_usa_ingredientes_de_chroma(self):
        motor, modelo = self.motor([
            ("responder", "Si te apetece este plato, [[PLATO]] lleva [[INGREDIENTES]] según la carta de muestra."),
        ])
        respuesta = responder("¿Qué lleva el pollo tipakay?", nuevo_perfil(), inteligencia=motor)
        self.assertIn("Si te apetece este plato", respuesta.texto)
        self.assertIn("piña y salsa tipakay", respuesta.texto)
        self.assertIn("tipakay", modelo.solicitudes[0]["fichas"])

    def test_comparacion_desde_la_ficha_recupera_ambos_platos(self):
        motor, modelo = self.motor([
            ("responder", "Puedes elegir entre estas dos opciones.\n\n[[PRIMERO]]\n\n[[SEGUNDO]]"),
        ])
        respuesta = responder(
            "Compara Dúo de chaufa y pollo tipakay con Arroz chaufa de pollo.",
            nuevo_perfil(), inteligencia=motor, contexto_interfaz={"plato_id": "duo"},
        )
        self.assertEqual(respuesta.tipo, "comparacion")
        self.assertEqual(respuesta.platos, ("duo", "chaufa-pollo"))
        self.assertTrue({"duo", "chaufa-pollo"} <= modelo.solicitudes[0]["fichas"].keys())
        self.assertIn("S/ 45.90", respuesta.texto)
        self.assertIn("S/ 24.90", respuesta.texto)

    def test_belen_recibe_las_elecciones_del_creador(self):
        contexto = {"etapa": "Salsa", "opciones": ["Sillao", "Agridulce"], "seleccion": {"Base": "Arroz blanco"}}
        motor, modelo = self.motor([
            ("responder", "Si te provoca un sabor salado, el sillao puede complementar tu arroz blanco."),
        ])
        respuesta = responder(
            "Ayúdame a elegir salsa para mi plato.", nuevo_perfil(),
            inteligencia=motor, contexto_interfaz=contexto,
        )
        self.assertEqual(respuesta.tipo, "personalizacion")
        self.assertEqual(modelo.solicitudes[0]["pantalla_de_origen"], contexto)

    def test_preguntas_cotidianas_sobre_la_oferta_y_ceviche(self):
        motor, modelo = self.motor([
            ("responder", "En el catálogo local encontrarás [[CARTA]]."),
            ("responder", "El ceviche no aparece en la carta de muestra. Puedes revisar el [[ALTERNATIVA]]."),
        ])
        perfil = nuevo_perfil()
        oferta = responder("que cosas venden aqui?", perfil, inteligencia=motor)
        ceviche = responder("aqui venden ceviche?", perfil, inteligencia=motor)
        self.assertIn("arroz chaufa de pollo", oferta.texto)
        self.assertIn("oferta", modelo.solicitudes[0]["fichas"])
        self.assertIn("no aparece en la carta de muestra", ceviche.texto)
        self.assertEqual(ceviche.platos, ("chaufa-mariscos",))
        self.assertFalse(ceviche.fuente)

    def test_navegacion_solo_dirige_a_pantallas_y_platos_locales(self):
        self.assertEqual(destino_navegacion("¿Qué venden aquí?"), ("Menú", None))
        self.assertEqual(destino_navegacion("Quiero personalizar mi plato"), ("Crear", None))
        self.assertEqual(destino_navegacion("Quiero personalizarlo"), ("Crear", None))
        self.assertEqual(destino_navegacion("Muéstrame el pollo tipakay"), ("Menú", "tipakay"))
        self.assertEqual(destino_navegacion("Mi pedido"), ("Pedido", None))
        self.assertEqual(destino_navegacion("Quiero ver mi pedido"), ("Pedido", None))
        self.assertIsNone(destino_navegacion("¿Cuánto cuesta el pollo tipakay?"))

    def test_proveedor_de_respaldo_tras_salida_con_precio_inventado(self):
        motor, _ = self.motor(
            [("responder", "[[PLATO]] cuesta S/ 999 y también [[PRECIO]].")],
            [("responder", "En la carta de muestra, [[PLATO]] cuesta [[PRECIO]].")],
        )
        respuesta = responder("¿Cuánto cuesta el lomo?", nuevo_perfil(), inteligencia=motor)
        self.assertEqual(respuesta.proveedor, "Groq")
        self.assertIn("S/ 27.90", respuesta.texto)
        self.assertNotIn("999", respuesta.texto)

    def test_error_de_conexion_no_avanza_la_conversacion(self):
        motor, _ = self.motor([TimeoutError(), ("responder", "¿Cuál es el presupuesto para [[GRUPO]]?")])
        perfil = nuevo_perfil()
        perfil["recomendando"] = True
        respuesta = responder("5", perfil, inteligencia=motor)
        self.assertEqual(respuesta.tipo, "error_ia")
        self.assertIsNone(perfil["personas"])
        respuesta = responder("5", perfil, inteligencia=motor)
        self.assertIn("5 personas", respuesta.texto)
        self.assertEqual(perfil["personas"], 5)

    def test_sin_proveedor_y_derivacion_por_alergias(self):
        perfil = nuevo_perfil()
        self.assertEqual(responder("¿Qué me recomiendas?", perfil).tipo, "error_ia")
        respuesta = responder("Soy alérgico a la soya", perfil)
        self.assertEqual(respuesta.proveedor, "Sistema")
        self.assertEqual(respuesta.tipo, "derivacion")
        self.assertFalse(respuesta.fuente)


class PruebaFlujoPersonalizacion(unittest.TestCase):
    def test_la_llamada_activa_mantiene_la_pantalla_de_voz_sin_campo_de_chat(self):
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=60).run()
        app.session_state.vista = "Belén"
        app.session_state.llamada_activa = True
        app.session_state.modo_chat = "voz"
        app.run()

        self.assertFalse(app.exception, [e.message for e in app.exception])
        self.assertTrue(app.session_state.llamada_activa)
        self.assertEqual(len(app.chat_input), 0)

    def test_alternar_entre_chat_y_voz_conserva_el_hilo_y_la_llamada(self):
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=60).run()
        mensajes = [("user", "¿Qué hay para compartir?", ""), ("assistant", "Puedes elegir un dúo.", "Gemini Live")]
        app.session_state.vista = "Belén"
        app.session_state.llamada_activa = True
        app.session_state.modo_chat = "voz"
        app.session_state.historial = mensajes.copy()
        app.run()

        app.button(key="alternar_vista_voz").click().run()
        self.assertFalse(app.exception, [e.message for e in app.exception])
        self.assertEqual(len(app.chat_input), 1)
        self.assertEqual(app.session_state.historial, mensajes)
        self.assertTrue(app.session_state.llamada_activa)

        app.button(key="alternar_vista_voz").click().run()
        self.assertEqual(len(app.chat_input), 0)
        self.assertEqual(app.session_state.historial, mensajes)
        self.assertTrue(app.session_state.llamada_activa)

    def test_la_voz_abre_el_creador_y_aplica_la_eleccion_a_la_siguiente_etapa(self):
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=60).run()
        app.session_state.vista = "Belén"
        app.session_state.llamada_activa = True
        app.session_state.modo_chat = "voz"
        app.session_state.consulta_en_curso = {
            "pregunta": "Quiero personalizar mi plato",
            "contexto": {},
        }
        app.run()

        self.assertFalse(app.exception, [e.message for e in app.exception])
        self.assertEqual((app.session_state.vista, app.session_state.paso), ("Crear", 0))
        self.assertIn("Arroz chaufa", app.session_state.historial[-1][1])
        self.assertIn("Tallarines", app.session_state.historial[-1][1])

        app.session_state.consulta_en_curso = {"pregunta": "arroz chaufa", "contexto": {}}
        app.run()

        self.assertFalse(app.exception, [e.message for e in app.exception])
        self.assertEqual(app.session_state.combinacion["Base"], "Arroz chaufa")
        self.assertEqual(app.session_state.paso, 1)
        self.assertIn("Pollo", app.session_state.historial[-1][1])
        self.assertTrue(app.session_state.llamada_activa)

        app.button(key="abrir_chat_llamada").click().run()
        self.assertFalse(app.exception, [e.message for e in app.exception])
        self.assertEqual(len(app.chat_input), 1)
        self.assertTrue(app.session_state.llamada_activa)
        self.assertEqual(app.session_state.origen_chat[0], "Crear")
        self.assertEqual(app.session_state.paso, 1)


class PruebaEnVivo(unittest.TestCase):
    @unittest.skipUnless(os.getenv("BELEN_PRUEBA_EN_VIVO") == "1", "Requiere conexión y clave de la API.")
    def test_chat_genera_una_respuesta_con_un_proveedor_real(self):
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=65).run()
        app.session_state.vista = "Belén"
        app.run()
        app.chat_input[0].set_value("¿Qué lleva el pollo tipakay?").run()
        self.assertFalse(app.exception)
        evidencia = app.session_state.metricas[-1]
        respuesta = app.session_state.historial[-1][1]
        self.assertIn(evidencia["proveedor"], ("Gemini", "Groq"), respuesta)
        self.assertIn("salsa tipakay", respuesta)
        print(f'\nPrueba en vivo con {evidencia["proveedor"]} · {evidencia["latencia_ms"]} ms')


if __name__ == "__main__":
    unittest.main()
