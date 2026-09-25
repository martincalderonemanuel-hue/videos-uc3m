"""
Verificador: filtros gratuitos y control de que un vídeo existe de verdad.

Todo lo de aquí es lógica pura (sin internet), salvo `existe_en_oembed`,
que hace la segunda comprobación justo antes de publicar.
"""
import re

import config

_PATRON_DURACION = re.compile(
    r"^P(?:(?P<d>\d+)D)?(?:T(?:(?P<h>\d+)H)?(?:(?P<m>\d+)M)?(?:(?P<s>\d+)S)?)?$"
)
_PATRON_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")


def duracion_a_minutos(texto):
    """Convierte 'PT17M11S' (formato ISO 8601 de YouTube) en minutos (17.18)."""
    if not texto:
        return 0
    m = _PATRON_DURACION.match(texto)
    if not m:
        return 0
    partes = {k: int(v) if v else 0 for k, v in m.groupdict().items()}
    return partes["d"] * 1440 + partes["h"] * 60 + partes["m"] + partes["s"] / 60


def url_video(video_id):
    """Construye el enlace SOLO a partir de un ID con formato válido de YouTube."""
    if not _PATRON_ID.match(video_id or ""):
        raise ValueError(f"ID de vídeo no válido: {video_id!r}")
    return f"https://www.youtube.com/watch?v={video_id}"


def _bloqueado_en_region(detalles, region):
    restriccion = detalles.get("regionRestriction") or {}
    if region in restriccion.get("blocked", []):
        return True
    permitidos = restriccion.get("allowed")
    return permitidos is not None and region not in permitidos


def motivo_descarte(video):
    """
    Devuelve el motivo por el que el vídeo se descarta, o None si pasa.
    `video` es un elemento de la respuesta de videos.list.
    """
    estado = video.get("status")
    detalles = video.get("contentDetails")
    if not estado or not detalles or "snippet" not in video:
        return "datos incompletos"
    if estado.get("privacyStatus") != "public":
        return "no es público"
    if estado.get("uploadStatus") != "processed":
        return "no está procesado"
    if _bloqueado_en_region(detalles, config.REGION):
        return "bloqueado en España"
    minutos = duracion_a_minutos(detalles.get("duration"))
    if not (config.DURACION_MIN_MINUTOS <= minutos <= config.DURACION_MAX_MINUTOS):
        return "duración fuera de rango"
    return None


def existe_en_oembed(video_id, sesion):
    """Segunda comprobación: el endpoint público oEmbed responde 200 si el vídeo existe."""
    respuesta = sesion.get(
        "https://www.youtube.com/oembed",
        params={"url": url_video(video_id), "format": "json"},
        timeout=15,
    )
    return respuesta.status_code == 200
