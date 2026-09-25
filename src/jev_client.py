"""
Cliente de Jev (TypeSafe AI) a través de Vercel AI Gateway.

Jev no escribe texto: recibe un "estado" (los datos del vídeo) y preguntas con
respuestas cerradas, y devuelve probabilidades. Este módulo está aislado del resto
porque la API es nueva y puede cambiar: si cambia, solo hay que tocar aquí.
"""
import config
from src.errores import ErrorAPI, mensaje_de_error

NIVELES = {
    "divulgativo": "Para público general, sin base técnica",
    "bachillerato": "Nivel de secundaria o bachillerato, asignaturas como Tecnología o Física de instituto",
    "universitario": "Nivel de grado en ingeniería: formalismo, notación técnica y problemas de examen universitario",
    "posgrado": "Nivel de máster o investigación",
}

FORMATOS = {
    "teoria": "Explicación teórica de conceptos",
    "problemas_resueltos": "Resolución paso a paso de ejercicios o problemas",
    "practica": "Simulación, software, laboratorio o montaje práctico",
    "resumen": "Repaso rápido o resumen de un tema",
}


def construir_preguntas(tema_titulo, asignatura):
    return {
        "cubre_tema": {
            "type": "boolean",
            "instructions": f"¿El vídeo explica el tema «{tema_titulo}» de la asignatura universitaria «{asignatura}»?",
            "criteria": {
                "true": "El contenido principal del vídeo trata este tema",
                "false": "El vídeo trata otro tema o solo lo menciona de pasada",
            },
        },
        "nivel": {
            "type": "choice",
            "instructions": "¿Qué nivel académico tiene el vídeo?",
            "criteria": NIVELES,
        },
        "rigor": {
            "type": "score",
            "instructions": "¿Cuánto rigor técnico tiene el vídeo?",
            "criteria": [
                "Sin fórmulas ni desarrollo matemático",
                "Muestra fórmulas pero sin desarrollarlas ni aplicarlas",
                "Desarrolla las fórmulas y resuelve ejemplos o problemas",
            ],
        },
        "formato": {
            "type": "choice",
            "instructions": "¿Qué formato tiene principalmente el vídeo?",
            "criteria": FORMATOS,
        },
        "promocional": {
            "type": "boolean",
            "instructions": "¿El vídeo es sobre todo publicidad de un curso, academia o producto?",
        },
    }


def construir_estado(video, transcripcion, tema_titulo, asignatura):
    """Datos del vídeo que ve Jev, recortados para no gastar de más."""
    snippet = video.get("snippet", {})
    estado = {
        "asignatura": asignatura,
        "tema": tema_titulo,
        "titulo": snippet.get("title", ""),
        "canal": snippet.get("channelTitle", ""),
        "descripcion": (snippet.get("description") or "")[:1500],
        "transcripcion": transcripcion or "(no disponible)",
    }
    # Recorte final: la transcripción es lo que más ocupa
    exceso = sum(len(str(v)) for v in estado.values()) - config.MAX_CARACTERES_ESTADO_JEV
    if exceso > 0:
        estado["transcripcion"] = estado["transcripcion"][: max(0, len(estado["transcripcion"]) - exceso)]
    return estado


def _probabilidad(respuesta):
    for campo in ("probability", "noul"):
        if campo in respuesta:
            return float(respuesta[campo])
    raise KeyError("probability")


def _eleccion(respuesta):
    if "choice" in respuesta:
        return respuesta["choice"]
    probs = respuesta.get("probabilities") or {}
    if probs:
        return max(probs, key=probs.get)
    raise KeyError("choice")


def evaluar(sesion, clave, estado, preguntas):
    """Llama a Jev y devuelve las respuestas en un diccionario simple."""
    respuesta = sesion.post(
        config.JEV_URL,
        headers={"Authorization": f"Bearer {clave}", "Content-Type": "application/json"},
        json={
            "model": config.JEV_MODELO,
            "state": estado,
            "questions": preguntas,
        },
        timeout=30,
    )
    if respuesta.status_code != 200:
        raise ErrorAPI(f"Jev ({respuesta.status_code}): {mensaje_de_error(respuesta)}")
    try:
        a = respuesta.json()["answers"]
        return {
            "cubre_tema": _probabilidad(a["cubre_tema"]),
            "nivel": _eleccion(a["nivel"]),
            "rigor": float(a["rigor"]["score"]),
            "formato": _eleccion(a["formato"]),
            "promocional": _probabilidad(a["promocional"]),
        }
    except (KeyError, TypeError, ValueError) as e:
        raise ErrorAPI(f"Jev devolvió una respuesta con un formato inesperado (falta {e})") from e
