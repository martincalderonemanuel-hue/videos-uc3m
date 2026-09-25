"""Sesión HTTP falsa para probar los clientes sin internet ni claves."""


class RespuestaFalsa:
    def __init__(self, status_code=200, datos=None, texto=""):
        self.status_code = status_code
        self._datos = datos
        self.text = texto or (str(datos) if datos is not None else "")

    def json(self):
        if self._datos is None:
            raise ValueError("sin JSON")
        return self._datos


class SesionFalsa:
    """
    Devuelve respuestas preparadas según un trozo de la URL.
    `rutas` = {"trozo_de_url": RespuestaFalsa o lista de RespuestaFalsa (se consumen en orden)}.
    Guarda todas las llamadas en `llamadas` para poder comprobarlas.
    """

    def __init__(self, rutas):
        self.rutas = rutas
        self.llamadas = []

    def _responder(self, metodo, url, **kwargs):
        self.llamadas.append({"metodo": metodo, "url": url, **kwargs})
        for trozo, respuesta in self.rutas.items():
            if trozo in url:
                if isinstance(respuesta, list):
                    return respuesta.pop(0)
                return respuesta
        raise AssertionError(f"URL no esperada en el test: {url}")

    def get(self, url, **kwargs):
        return self._responder("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self._responder("POST", url, **kwargs)
