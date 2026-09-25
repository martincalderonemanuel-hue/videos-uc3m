"""
Puntuación: aquí se decide qué vídeos valen la pena.

Jev solo responde preguntas (probabilidades y categorías).
Este módulo aplica los umbrales y calcula la nota final.
Lógica pura: sin internet, fácil de probar.
"""
import config

RIGOR_MAXIMO = 2.0  # la pregunta de rigor tiene 3 escalones: 0, 1, 2


def _entero(texto):
    try:
        return int(texto)
    except (TypeError, ValueError):
        return 0


def popularidad(video):
    """Proporción likes/visitas normalizada entre 0 y 1."""
    stats = video.get("statistics", {})
    vistas = _entero(stats.get("viewCount"))
    likes = _entero(stats.get("likeCount"))
    if vistas <= 0 or likes <= 0:
        return 0
    return min((likes / vistas) / config.RATIO_LIKES_EXCELENTE, 1.0)


def puntuar(video, respuestas):
    """
    `respuestas` es la salida normalizada de Jev:
    cubre_tema (0-1), nivel (texto), rigor (0-2), formato (texto), promocional (0-1).
    Devuelve {"descartado": motivo o None, "nota": 0-1}.
    """
    if respuestas["cubre_tema"] < config.UMBRAL_CUBRE_TEMA:
        return {"descartado": "no cubre el tema", "nota": 0}
    if respuestas["nivel"] not in config.NIVELES_ACEPTADOS:
        return {"descartado": "nivel no universitario", "nota": 0}
    if respuestas["promocional"] > config.UMBRAL_PROMOCIONAL:
        return {"descartado": "es promocional", "nota": 0}

    nota = (
        config.PESO_RIGOR * (respuestas["rigor"] / RIGOR_MAXIMO)
        + config.PESO_CUBRE_TEMA * respuestas["cubre_tema"]
        + config.PESO_POPULARIDAD * popularidad(video)
    )
    if video.get("status", {}).get("madeForKids"):
        nota -= config.PENALIZACION_PARA_NINOS
    return {"descartado": None, "nota": round(max(0.0, min(nota, 1.0)), 4)}
