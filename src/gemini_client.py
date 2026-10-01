"""
Cliente de Gemini (capa gratuita de Google AI Studio).

Escribe dos frases por vídeo: por qué verlo y para quién es.
Se mandan varios vídeos por petición porque la capa gratuita limita peticiones, no vídeos.
Si Gemini falla, el vídeo se publica igual, solo que sin explicación.
"""
import json
import re
import time

import config
from src.errores import mensaje_de_error

BASE = "https://generativelanguage.googleapis.com/v1beta"
_URL = re.compile(r"https?://\S+")


def elegir_modelo(sesion, clave, preferido):
    """Usa el modelo preferido si existe; si no, el Flash-Lite estable más reciente."""
    respuesta = sesion.get(f"{BASE}/models", params={"key": clave, "pageSize": 200}, timeout=30)
    if respuesta.status_code != 200:
        return preferido or None
    nombres = [
        m["name"].split("/", 1)[-1]
        for m in respuesta.json().get("models", [])
        if "generateContent" in m.get("supportedGenerationMethods", [])
    ]
    if preferido and preferido in nombres:
        return preferido
    lite = [n for n in nombres if "flash-lite" in n]
    estables = [n for n in lite if "preview" not in n and "exp" not in n]
    candidatos = sorted(estables or lite, reverse=True)
    return candidatos[0] if candidatos else None


def _fichas(videos):
    return [{
        "id": v["id"],
        "asignatura": v["asignatura"],
        "tema": v["tema"],
        "titulo": v["titulo"],
        "canal": v["canal"],
        "descripcion": (v.get("descripcion") or "")[:500],
        "fragmento_transcripcion": (v.get("transcripcion") or "")[:1500],
    } for v in videos]


def _prompt(videos):
    return (
        "Eres un tutor de ingeniería. Para cada vídeo, escribe en español:\n"
        "- por_que: una frase (máx. 25 palabras) sobre qué aporta el vídeo para estudiar ese tema.\n"
        "- para_quien: una frase corta (máx. 12 palabras), p. ej. 'Para entender la teoría desde cero'.\n"
        "No inventes contenido que no se deduzca de los datos. No incluyas enlaces.\n"
        "Responde SOLO con una lista JSON: [{\"id\": ..., \"por_que\": ..., \"para_quien\": ...}]\n\n"
        + json.dumps(_fichas(videos), ensure_ascii=False)
    )


def _limpiar(texto):
    return _URL.sub("", str(texto or "")).strip()[:300]


def _por_lotes(sesion, clave, modelo, videos, hacer_prompt, dormir):
    """Envía los vídeos en lotes y devuelve los elementos JSON cuyo id es válido."""
    ids_validos = {v["id"] for v in videos}
    tam = config.GEMINI_VIDEOS_POR_PETICION
    for i in range(0, len(videos), tam):
        if i > 0:
            dormir(config.GEMINI_PAUSA_SEGUNDOS)
        respuesta = sesion.post(
            f"{BASE}/models/{modelo}:generateContent",
            params={"key": clave},
            json={
                "contents": [{"parts": [{"text": hacer_prompt(videos[i:i + tam])}]}],
                "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
            },
            timeout=60,
        )
        if respuesta.status_code != 200:
            print(f"  Aviso: Gemini respondió {respuesta.status_code}: {mensaje_de_error(respuesta)}")
            continue
        try:
            texto = respuesta.json()["candidates"][0]["content"]["parts"][0]["text"]
            for item in json.loads(texto):
                if isinstance(item, dict) and item.get("id") in ids_validos:
                    yield item
        except (KeyError, IndexError, TypeError, ValueError) as e:
            print(f"  Aviso: no se pudo leer la respuesta de Gemini ({e})")


def explicar(sesion, clave, modelo, videos, dormir=time.sleep):
    """Devuelve {id: {"por_que": ..., "para_quien": ...}} para los vídeos que pueda."""
    return {
        item["id"]: {"por_que": _limpiar(item.get("por_que")), "para_quien": _limpiar(item.get("para_quien"))}
        for item in _por_lotes(sesion, clave, modelo, videos, _prompt, dormir)
    }
