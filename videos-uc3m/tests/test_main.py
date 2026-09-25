"""Test de extremo a extremo: una noche completa en modo simulado (sin internet)."""
import datetime as dt
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config
import main
from src.simulacion import SesionSimulada
from tests.falsos import RespuestaFalsa

RAIZ = os.path.join(os.path.dirname(__file__), "..")
HOY = dt.date(2026, 9, 26)  # sábado
CLAVES = {"youtube": "x", "jev": "x", "gemini": "x"}


def preparar(tmp_path):
    shutil.copytree(os.path.join(RAIZ, "temarios"), tmp_path / "temarios")
    return {"temarios": str(tmp_path / "temarios"), "datos": str(tmp_path / "datos"), "docs": str(tmp_path / "docs")}


def leer(ruta):
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def noche(rutas, sesion=None, hoy=HOY, **opciones):
    return main.ejecutar(opciones, rutas, sesion or SesionSimulada(), CLAVES, hoy, dormir=lambda _: None)


def test_noche_completa(tmp_path):
    rutas = preparar(tmp_path)
    informe = noche(rutas)
    assert informe["busquedas"] == 90
    assert informe["evaluados"] > 0
    assert informe["errores"] == []
    publicados = leer(os.path.join(rutas["datos"], "publicados.json"))
    assert publicados
    for videos in publicados.values():
        assert len(videos) <= 3
        notas = [v["nota"] for v in videos]
        assert notas == sorted(notas, reverse=True)
    html = open(os.path.join(rutas["docs"], "index.html"), encoding="utf-8").read()
    assert "Novedades de esta noche" in html
    assert os.path.exists(os.path.join(rutas["docs"], ".nojekyll"))


def test_segunda_noche_continua_y_no_repite(tmp_path):
    rutas = preparar(tmp_path)
    noche(rutas)
    estado1 = leer(os.path.join(rutas["datos"], "estado.json"))
    noche(rutas, hoy=HOY + dt.timedelta(days=1))
    estado2 = leer(os.path.join(rutas["datos"], "estado.json"))
    assert sum(e["siguiente"] for e in estado2.values()) > sum(e["siguiente"] for e in estado1.values())


def test_cuota_agotada_no_rompe_la_noche(tmp_path):
    rutas = preparar(tmp_path)
    sesion = SesionSimulada(cuota_busquedas=10)
    informe = noche(rutas, sesion)
    assert informe["busquedas"] == 10
    assert any("cuota" in e.lower() for e in informe["avisos"])
    assert os.path.exists(os.path.join(rutas["docs"], "index.html"))


def test_jev_caido_se_informa_y_se_reintenta_otro_dia(tmp_path):
    rutas = preparar(tmp_path)
    sesion = SesionSimulada(jev_roto=True)
    informe = noche(rutas, sesion)
    assert any("Jev" in e for e in informe["errores"])
    pendientes = leer(os.path.join(rutas["datos"], "pendientes.json"))
    assert len(pendientes) > 0
    # al día siguiente Jev funciona: los pendientes antiguos se evalúan antes que los nuevos
    antiguos = [(p["tema_id"], p["video_id"]) for p in pendientes]
    informe2 = noche(rutas, SesionSimulada(), hoy=HOY + dt.timedelta(days=1))
    assert informe2["errores"] == []
    quedan = {(p["tema_id"], p["video_id"]) for p in leer(os.path.join(rutas["datos"], "pendientes.json"))}
    primeros = set(antiguos[:config.MAX_VIDEOS_JEV_POR_NOCHE])  # lo que cabe en el tope de una noche
    assert not (primeros & quedan)  # ninguno sigue pendiente: tuvieron prioridad sobre los nuevos


def test_sin_gemini_publica_igual(tmp_path):
    rutas = preparar(tmp_path)
    claves = dict(CLAVES, gemini="")
    main.ejecutar({}, rutas, SesionSimulada(), claves, HOY, dormir=lambda _: None)
    publicados = leer(os.path.join(rutas["datos"], "publicados.json"))
    assert publicados
    assert all(v["por_que"] == "" for vs in publicados.values() for v in vs)


def test_reverificacion_quita_videos_borrados(tmp_path):
    rutas = preparar(tmp_path)
    noche(rutas)
    publicados = leer(os.path.join(rutas["datos"], "publicados.json"))
    un_id = next(iter(publicados.values()))[0]["id"]
    sesion = SesionSimulada(borrados={un_id})
    informe = noche(rutas, sesion, hoy=HOY + dt.timedelta(days=2), reverificar=True)  # lunes
    publicados2 = leer(os.path.join(rutas["datos"], "publicados.json"))
    assert all(v["id"] != un_id for vs in publicados2.values() for v in vs)
    assert informe["retirados"] >= 1


def test_oembed_falla_no_se_publica(tmp_path):
    rutas = preparar(tmp_path)
    sesion = SesionSimulada(oembed_falla=True)
    noche(rutas, sesion)
    publicados = leer(os.path.join(rutas["datos"], "publicados.json"))
    assert publicados == {} or all(len(v) == 0 for v in publicados.values())


def test_solo_una_asignatura(tmp_path):
    rutas = preparar(tmp_path)
    noche(rutas, asignatura="Termodinámica")
    estado = leer(os.path.join(rutas["datos"], "estado.json"))
    assert estado and all(k.startswith("TD-") for k in estado)


def test_faltan_claves_da_error_claro(tmp_path):
    rutas = preparar(tmp_path)
    try:
        main.ejecutar({}, rutas, SesionSimulada(), {"youtube": "", "jev": "x", "gemini": ""}, HOY)
    except SystemExit as e:
        assert "YOUTUBE_API_KEY" in str(e)
    else:
        raise AssertionError("debería haber fallado")
