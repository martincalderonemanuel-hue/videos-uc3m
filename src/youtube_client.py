"""
Cliente de la API de YouTube.

- buscar(): 100 unidades de cuota por llamada (caro). Solo devuelve IDs.
- detalles(): 1 unidad por cada 50 vídeos (barato). Aquí se verifica que existen.
"""
from src.errores import CuotaAgotada, ErrorAPI, mensaje_de_error

BASE = "https://www.googleapis.com/youtube/v3"


def _comprobar(respuesta):
    if respuesta.status_code == 200:
        return respuesta.json()
    try:
        motivos = [e.get("reason") for e in respuesta.json()["error"].get("errors", [])]
    except (ValueError, KeyError, AttributeError):
        motivos = []
    mensaje = mensaje_de_error(respuesta)
    if (
        respuesta.status_code == 429
        or "quotaExceeded" in motivos
        or "dailyLimitExceeded" in motivos
        or "quota exceeded" in mensaje.lower()
    ):
        raise CuotaAgotada("YouTube: cuota diaria agotada")
    raise ErrorAPI(f"YouTube ({respuesta.status_code}): {mensaje}")


def buscar(sesion, clave, consulta, idioma, max_resultados):
    """Devuelve la lista de IDs de vídeo para una búsqueda."""
    datos = _comprobar(sesion.get(
        f"{BASE}/search",
        params={
            "part": "id",
            "type": "video",
            "q": consulta,
            "maxResults": max_resultados,
            "relevanceLanguage": idioma,
            "regionCode": "ES",
            "safeSearch": "moderate",
            "key": clave,
        },
        timeout=30,
    ))
    return [
        item["id"]["videoId"]
        for item in datos.get("items", [])
        if item.get("id", {}).get("kind") == "youtube#video"
    ]


def detalles(sesion, clave, ids):
    """Devuelve {id: datos del vídeo}. Los vídeos borrados o privados simplemente no aparecen."""
    resultado = {}
    ids = list(dict.fromkeys(ids))  # sin repetidos, manteniendo el orden
    for inicio in range(0, len(ids), 50):
        lote = ids[inicio:inicio + 50]
        datos = _comprobar(sesion.get(
            f"{BASE}/videos",
            params={
                "part": "snippet,contentDetails,status,statistics",
                "id": ",".join(lote),
                "key": clave,
            },
            timeout=30,
        ))
        for item in datos.get("items", []):
            resultado[item["id"]] = item
    return resultado
