import unittest
from unittest.mock import patch

from pedido_demo import agregar_personalizado, cantidad_pedido, resumen_pedido, total_pedido


class PruebasPedido(unittest.TestCase):
    def test_conserva_varios_platos_personalizados_y_su_resumen(self):
        with patch("pedido_demo.st.session_state", {}):
            self.assertTrue(agregar_personalizado({
                "Base": "Arroz chaufa",
                "Proteína": "Pollo",
                "Verduras": ["Brócoli"],
                "Salsa": "Sillao",
            }))
            self.assertTrue(agregar_personalizado({
                "Base": "Tallarines",
                "Proteína": "Tofu",
                "Verduras": ["Zanahoria"],
                "Salsa": "Teriyaki",
            }))

            lineas = resumen_pedido()
            self.assertEqual(len(lineas), 2)
            self.assertEqual(cantidad_pedido(), 2)
            self.assertEqual(total_pedido(), 2 * 2690)
            self.assertIn("Arroz chaufa", lineas[0]["detalle"])
            self.assertIn("Tallarines", lineas[1]["detalle"])


if __name__ == "__main__":
    unittest.main()
