"""Tests de verificador.py: duración, filtros gratuitos y control de existencia."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.verificador import duracion_a_minutos, motivo_descarte, url_video

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def cargar_videos():
    with open(os.path.join(FIXTURES, "youtube_videos.json"), encoding="utf-8") as f:
        return {v["id"]: v for v in json.load(f)["items"]}


# --- duración ISO 8601 -----------------------------------------------------

@pytest.mark.parametrize("texto, minutos", [
    ("PT17M11S", 17 + 11 / 60),
    ("PT45S", 0.75),
    ("PT1H", 60),
    ("PT1H30M", 90),
    ("PT2H3M4S", 123 + 4 / 60),
    ("P1DT1H", 24 * 60 + 60),
])
def test_duracion_a_minutos(texto, minutos):
    assert duracion_a_minutos(texto) == pytest.approx(minutos)


@pytest.mark.parametrize("texto", ["", "P0D", "basura", None])
def test_duracion_invalida_da_cero(texto):
    assert duracion_a_minutos(texto) == 0


# --- filtros gratuitos ------------------------------------------------------

def test_video_bueno_pasa():
    assert motivo_descarte(cargar_videos()["6QLbw1xS8sg"]) is None


def test_video_corto_se_descarta():
    assert motivo_descarte(cargar_videos()["Dyee1JVYsd0"]) == "duración fuera de rango"


def test_video_privado_se_descarta():
    v = cargar_videos()["6QLbw1xS8sg"]
    v["status"]["privacyStatus"] = "private"
    assert motivo_descarte(v) == "no es público"


def test_video_sin_procesar_se_descarta():
    v = cargar_videos()["6QLbw1xS8sg"]
    v["status"]["uploadStatus"] = "uploaded"
    assert motivo_descarte(v) == "no está procesado"


def test_video_bloqueado_en_espana_se_descarta():
    v = cargar_videos()["6QLbw1xS8sg"]
    v["contentDetails"]["regionRestriction"] = {"blocked": ["ES", "FR"]}
    assert motivo_descarte(v) == "bloqueado en España"


def test_video_con_lista_blanca_sin_espana_se_descarta():
    v = cargar_videos()["6QLbw1xS8sg"]
    v["contentDetails"]["regionRestriction"] = {"allowed": ["US"]}
    assert motivo_descarte(v) == "bloqueado en España"


def test_video_sin_datos_basicos_se_descarta():
    assert motivo_descarte({"id": "abc"}) == "datos incompletos"


def test_url_se_construye_desde_el_id():
    assert url_video("6QLbw1xS8sg") == "https://www.youtube.com/watch?v=6QLbw1xS8sg"


def test_url_rechaza_ids_raros():
    with pytest.raises(ValueError):
        url_video("abc<script>")
