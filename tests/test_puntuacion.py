"""Tests de puntuacion.py: la decisión final es del código, no de Jev."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config
from src.puntuacion import popularidad, puntuar


@pytest.fixture(autouse=True)
def fijar_umbral(monkeypatch):
    """Las pruebas usan un umbral fijo de 5/10 para no depender del valor elegido en config.py."""
    monkeypatch.setattr(config, "NOTA_MINIMA_PUBLICAR", 0.5)


def jev(**cambios):
    """Respuesta de Jev ya normalizada, con valores 'buenos' por defecto."""
    base = {
        "cubre_tema": 0.9,
        "nivel": "universitario",
        "rigor": 2.0,          # escala 0..2 (3 escalones)
        "formato": "teoría",
        "promocional": 0.05,
    }
    base.update(cambios)
    return base


def video(likes="1858", vistas="97628", ninos=False):
    return {
        "statistics": {"likeCount": likes, "viewCount": vistas},
        "status": {"madeForKids": ninos},
    }


# --- descartes --------------------------------------------------------------

def test_no_cubre_tema_se_descarta():
    r = puntuar(video(), jev(cubre_tema=0.65, rigor=2.0))
    assert r["descartado"] == "no cubre el tema"


def test_nivel_bachillerato_se_descarta():
    assert puntuar(video(), jev(nivel="bachillerato"))["descartado"] == "nivel no universitario"


def test_posgrado_se_acepta():
    assert puntuar(video(), jev(nivel="posgrado"))["descartado"] is None


def test_promocional_se_descarta():
    assert puntuar(video(), jev(promocional=0.8))["descartado"] == "es promocional"


# --- nota -------------------------------------------------------------------

def test_nota_entre_0_y_1():
    r = puntuar(video(), jev())
    assert 0 <= r["nota"] <= 1


def test_mas_rigor_mas_nota():
    baja = puntuar(video(), jev(rigor=0.5))["nota"]
    alta = puntuar(video(), jev(rigor=2.0))["nota"]
    assert alta > baja


def test_para_ninos_resta_puntos_pero_no_descarta():
    normal = puntuar(video(ninos=False), jev())
    ninos = puntuar(video(ninos=True), jev())
    assert ninos["descartado"] is None
    assert ninos["nota"] == pytest.approx(normal["nota"] - 0.15)


def test_nota_baja_se_descarta():
    # vídeo que pasa los filtros pero es flojo: sin rigor, cubre el tema justo, sin likes
    r = puntuar(video(likes="0"), jev(rigor=0, cubre_tema=0.75))
    assert r["descartado"] == "nota baja"


def test_umbral_configurable(monkeypatch):
    monkeypatch.setattr(config, "NOTA_MINIMA_PUBLICAR", 0.9)
    assert puntuar(video(), jev())["descartado"] == "nota baja"  # 8,97 < 9


def test_nota_justo_en_el_minimo_se_acepta():
    # 0.5*(1/2) + 0.3*(5/6) + 0 = 0.5 exacto
    r = puntuar(video(likes="0"), jev(rigor=1.0, cubre_tema=5 / 6))
    assert r["descartado"] is None


def test_nota_nunca_negativa():
    r = puntuar(video(likes="0", ninos=True), jev(rigor=0, cubre_tema=0.7))
    assert r["nota"] >= 0


# --- popularidad ------------------------------------------------------------

def test_popularidad_con_numeros_en_texto():
    # la API devuelve los números como texto: "1858"
    assert popularidad(video(likes="1500", vistas="100000")) == pytest.approx(0.5)


def test_popularidad_tiene_techo():
    assert popularidad(video(likes="9000", vistas="10000")) == 1.0


def test_popularidad_sin_likes_visibles():
    v = {"statistics": {"viewCount": "500"}, "status": {}}
    assert popularidad(v) == 0


def test_popularidad_sin_visitas_no_divide_por_cero():
    assert popularidad(video(likes="0", vistas="0")) == 0
