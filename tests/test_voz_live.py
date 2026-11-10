import unittest
from types import SimpleNamespace
from unittest.mock import patch

from google.genai import types

from voz_live import (
    ErrorLiveAPI,
    MODELO_LIVE,
    VOZ_LIVE,
    crear_configuracion_live,
    crear_configuracion_websocket,
    crear_token_live,
)


class PruebasVozLive(unittest.TestCase):
    def test_configuracion_de_sesion_es_aceptada_por_el_sdk(self):
        config = crear_configuracion_live()
        tipos = types.LiveConnectConfig.model_validate(config)

        self.assertEqual(config["response_modalities"], ["AUDIO"])
        self.assertEqual(
            config["speech_config"]["voice_config"]["prebuilt_voice_config"]["voice_name"],
            VOZ_LIVE,
        )
        nombres = {declaracion.name for declaracion in tipos.tools[0].function_declarations}
        self.assertEqual(
            nombres,
            {
                "navigate_screen",
                "select_custom_options",
                "recommend_menu",
                "add_menu_dish",
                "add_customized_dish",
                "update_order_quantity",
            },
        )

    def test_configuracion_del_navegador_usa_campos_json_camel_case(self):
        config = crear_configuracion_websocket()

        self.assertEqual(config["generationConfig"]["responseModalities"], ["AUDIO"])
        self.assertIn("speechConfig", config["generationConfig"])
        self.assertIn("systemInstruction", config)
        self.assertIn("inputAudioTranscription", config)
        self.assertIn("outputAudioTranscription", config)
        self.assertIn("functionDeclarations", config["tools"][0])

    def test_token_rechaza_clave_ausente_sin_llamar_a_google(self):
        with self.assertRaises(ErrorLiveAPI):
            crear_token_live("")

    @patch("google.genai.Client")
    def test_token_efimero_usa_modelo_y_restricciones_de_live(self, crear_cliente):
        cliente = crear_cliente.return_value
        cliente.auth_tokens.create.return_value = SimpleNamespace(name="auth_tokens/temporal")

        token = crear_token_live("clave-de-prueba")

        self.assertEqual(token, "auth_tokens/temporal")
        crear_cliente.assert_called_once_with(
            api_key="clave-de-prueba",
            http_options=types.HttpOptions(api_version="v1alpha"),
        )
        config = cliente.auth_tokens.create.call_args.kwargs["config"]
        self.assertEqual(config["uses"], 1)
        self.assertEqual(
            config["live_connect_constraints"]["model"],
            MODELO_LIVE,
        )


if __name__ == "__main__":
    unittest.main()
