"""Tests de los clientes de APIs, con respuestas guardadas (sin red)."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import gemini_client, jev_client, youtube_client
from src.errores import CuotaAgotada, ErrorAPI
from src.transcripciones import Transcriptor
from tests.falsos import RespuestaFalsa, SesionFalsa

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def fixture(nombre):
    with open(os.path.join(FIXTURES, nombre), encoding="utf-8") as f:
        return json.load(f)


# === YouTube =================================================================

def test_buscar_devuelve_ids():
    s = SesionFalsa({"/search": RespuestaFalsa(200, fixture("youtube_search.json"))})
    ids = youtube_client.buscar(s, "CLAVE", "biela manivela", "es", 15)
    assert ids == ["Dyee1JVYsd0", "6QLbw1xS8sg", "YmfW0qCQDAo"]
    params = s.llamadas[0]["params"]
    assert params["q"] == "biela manivela"
    assert params["relevanceLanguage"] == "es"
    assert params["type"] == "video"


def test_cuota_agotada_se_detecta():
    error = {"error": {"code": 403, "errors": [{"reason": "quotaExceeded"}], "message": "quota"}}
    s = SesionFalsa({"/search": RespuestaFalsa(403, error)})
    with pytest.raises(CuotaAgotada):
        youtube_client.buscar(s, "CLAVE", "x", "es", 15)


def test_cuota_de_busquedas_429_se_detecta():
    # formato real visto el 25/09/2026 con el cupo propio de búsquedas
    error = {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED",
                       "message": "Quota exceeded for quota metric 'Search Queries' and limit "
                                  "'Search Queries per day' of service 'youtube.googleapis.com'"}}
    s = SesionFalsa({"/search": RespuestaFalsa(429, error)})
    with pytest.raises(CuotaAgotada):
        youtube_client.buscar(s, "CLAVE", "x", "es", 15)


def test_otro_error_de_youtube_da_mensaje_claro():
    error = {"error": {"code": 400, "errors": [{"reason": "keyInvalid"}], "message": "API key not valid"}}
    s = SesionFalsa({"/search": RespuestaFalsa(400, error)})
    with pytest.raises(ErrorAPI, match="API key not valid"):
        youtube_client.buscar(s, "CLAVE", "x", "es", 15)


def test_detalles_en_lotes_de_50():
    respuesta = fixture("youtube_videos.json")
    s = SesionFalsa({"/videos": [RespuestaFalsa(200, respuesta), RespuestaFalsa(200, {"items": []})]})
    ids = [f"id{i:09d}" for i in range(60)]
    youtube_client.detalles(s, "CLAVE", ids)
    assert len(s.llamadas) == 2
    assert len(s.llamadas[0]["params"]["id"].split(",")) == 50
    assert len(s.llamadas[1]["params"]["id"].split(",")) == 10


def test_detalles_devuelve_diccionario_por_id():
    s = SesionFalsa({"/videos": RespuestaFalsa(200, fixture("youtube_videos.json"))})
    d = youtube_client.detalles(s, "CLAVE", ["Dyee1JVYsd0", "6QLbw1xS8sg"])
    assert set(d) == {"Dyee1JVYsd0", "6QLbw1xS8sg", "YmfW0qCQDAo"}


# === Jev =====================================================================

RESPUESTA_JEV = {
    "model": "typesafe-ai/jev",
    "answers": {
        "cubre_tema": {"type": "boolean", "probability": 0.93},
        "nivel": {"type": "choice", "choice": "universitario",
                  "probabilities": {"divulgativo": 0.02, "bachillerato": 0.08, "universitario": 0.85, "posgrado": 0.05}},
        "rigor": {"type": "score", "score": 1.7, "probabilities": {"0": 0.05, "1": 0.2, "2": 0.75}},
        "formato": {"type": "choice", "choice": "practica", "probabilities": {}},
        "promocional": {"type": "boolean", "probability": 0.04},
    },
    "usage": {"inputTokens": 900, "outputTokens": 20},
}


def test_preguntas_tienen_los_tipos_correctos():
    p = jev_client.construir_preguntas("Cinemática de Mecanismos Planos", "Mecánica de máquinas")
    assert p["cubre_tema"]["type"] == "boolean"
    assert "Cinemática de Mecanismos Planos" in p["cubre_tema"]["instructions"]
    assert set(p["nivel"]["criteria"]) == {"divulgativo", "bachillerato", "universitario", "posgrado"}
    assert p["rigor"]["type"] == "score" and len(p["rigor"]["criteria"]) == 3


def test_estado_se_recorta():
    video = fixture("youtube_videos.json")["items"][1]
    estado = jev_client.construir_estado(video, "palabra " * 5000, "Tema", "Asignatura")
    assert len(json.dumps(estado, ensure_ascii=False)) <= 6500


def test_evaluar_normaliza_la_respuesta():
    s = SesionFalsa({"ai-gateway": RespuestaFalsa(200, RESPUESTA_JEV)})
    r = jev_client.evaluar(s, "CLAVE", {"x": 1}, {"q": {}})
    assert r == {"cubre_tema": 0.93, "nivel": "universitario", "rigor": 1.7,
                 "formato": "practica", "promocional": 0.04}
    llamada = s.llamadas[0]
    assert llamada["headers"]["Authorization"] == "Bearer CLAVE"
    assert llamada["json"]["model"] == "typesafe-ai/jev"
    # Zero Data Retention solo existe en planes de pago de Vercel: no se pide
    assert "zeroDataRetention" not in str(llamada["json"])


def test_evaluar_acepta_formato_nativo_de_typesafe():
    nativo = {"answers": {
        "cubre_tema": {"noul": 0.9},
        "nivel": {"choice": "posgrado", "probabilities": {}},
        "rigor": {"score": 2.0},
        "formato": {"choice": "teoria"},
        "promocional": {"noul": 0.1},
    }}
    s = SesionFalsa({"ai-gateway": RespuestaFalsa(200, nativo)})
    r = jev_client.evaluar(s, "CLAVE", {}, {})
    assert r["cubre_tema"] == 0.9 and r["nivel"] == "posgrado"


def test_evaluar_error_da_mensaje_claro():
    s = SesionFalsa({"ai-gateway": RespuestaFalsa(401, {"error": {"message": "Invalid API key"}})})
    with pytest.raises(ErrorAPI, match="Jev"):
        jev_client.evaluar(s, "CLAVE", {}, {})


def test_evaluar_respuesta_incompleta_da_error():
    s = SesionFalsa({"ai-gateway": RespuestaFalsa(200, {"answers": {}})})
    with pytest.raises(ErrorAPI):
        jev_client.evaluar(s, "CLAVE", {}, {})


# === Gemini ==================================================================

MODELOS = {"models": [
    {"name": "models/gemini-3.1-flash-lite", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/gemini-3.5-flash-lite", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/gemini-3.6-flash-lite-preview", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/gemini-3.8-flash", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/text-embedding-9", "supportedGenerationMethods": ["embedContent"]},
]}


def test_elige_el_flash_lite_estable_mas_reciente():
    s = SesionFalsa({"/models": RespuestaFalsa(200, MODELOS)})
    assert gemini_client.elegir_modelo(s, "CLAVE", "") == "gemini-3.5-flash-lite"


def test_respeta_modelo_preferido():
    s = SesionFalsa({"/models": RespuestaFalsa(200, MODELOS)})
    assert gemini_client.elegir_modelo(s, "CLAVE", "gemini-3.1-flash-lite") == "gemini-3.1-flash-lite"


def _respuesta_gemini(lista):
    return {"candidates": [{"content": {"parts": [{"text": json.dumps(lista, ensure_ascii=False)}]}}]}


def _video_para_gemini(vid):
    return {"id": vid, "asignatura": "A", "tema": "T", "titulo": "t", "canal": "c",
            "descripcion": "d", "transcripcion": None}


def test_explicar_en_lotes_y_sin_urls():
    lote1 = [{"id": f"v{i}", "por_que": f"Explica bien https://malo.com el tema {i}.", "para_quien": "Para repasar."}
             for i in range(10)]
    lote2 = [{"id": "v10", "por_que": "Bueno.", "para_quien": "Para examen."},
             {"id": "intruso", "por_que": "x", "para_quien": "y"}]
    s = SesionFalsa({":generateContent": [RespuestaFalsa(200, _respuesta_gemini(lote1)),
                                          RespuestaFalsa(200, _respuesta_gemini(lote2))]})
    videos = [_video_para_gemini(f"v{i}") for i in range(11)]
    r = gemini_client.explicar(s, "CLAVE", "gemini-3.5-flash-lite", videos, dormir=lambda _: None)
    assert len(s.llamadas) == 2
    assert set(r) == {f"v{i}" for i in range(11)}   # el id inventado se ignora
    assert "http" not in r["v0"]["por_que"]


def test_explicar_si_falla_devuelve_lo_que_tenga():
    s = SesionFalsa({":generateContent": RespuestaFalsa(429, {"error": {"message": "quota"}})})
    r = gemini_client.explicar(s, "CLAVE", "m", [_video_para_gemini("v1")], dormir=lambda _: None)
    assert r == {}


# === Transcripciones =========================================================

def test_transcriptor_recorta_palabras():
    t = Transcriptor(obtener=lambda vid: "hola " * 3000)
    texto = t.obtener("abc", 100)
    assert len(texto.split()) == 100


def test_transcriptor_se_rinde_tras_fallos_seguidos():
    llamadas = []

    def falla(vid):
        llamadas.append(vid)
        raise RuntimeError("IP bloqueada")

    t = Transcriptor(obtener=falla, max_fallos_seguidos=3)
    for i in range(10):
        assert t.obtener(f"v{i}", 100) is None
    assert len(llamadas) == 3
