"""Errores propios del proyecto, con mensajes pensados para que se entiendan."""


class ErrorAPI(Exception):
    """Un servicio externo respondió con error."""


class CuotaAgotada(ErrorAPI):
    """YouTube ya no admite más búsquedas hoy."""


def mensaje_de_error(respuesta):
    """Saca el mensaje de error de una respuesta HTTP, sea cual sea su formato."""
    try:
        datos = respuesta.json()
        error = datos.get("error", datos)
        if isinstance(error, dict):
            return error.get("message") or str(error)
        return str(error)
    except ValueError:
        return (respuesta.text or "")[:300]
