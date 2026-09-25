"""Tests de web.py: la página que ves cada mañana."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.web import generar_html

TEMARIOS = [
    {"asignatura": "Mecánica de máquinas", "prioridad": 1,
     "temas": [{"id": "MM-02", "titulo": "Cinemática del Sólido Rígido"},
               {"id": "MM-01", "titulo": "Repaso", "activo": False}]},
    {"asignatura": "Termodinámica", "prioridad": 3,
     "temas": [{"id": "TD-06", "titulo": "Ciclo Rankine"}]},
]


def ficha(vid="6QLbw1xS8sg", titulo="Análisis cinemático", nota=0.82, **extra):
    base = {"id": vid, "titulo": titulo, "canal": "CAD & CAE", "duracion_min": 17.2,
            "formato": "practica", "nota": nota, "por_que": "Resuelve un mecanismo paso a paso.",
            "para_quien": "Para practicar", "fecha": "2026-09-26", "sin_transcripcion": False}
    base.update(extra)
    return base


INFORME = {"fecha": "2026-09-26 02:41", "busquedas": 90, "evaluados": 412, "publicados_nuevos": 1, "errores": []}


def test_muestra_video_con_enlace_construido_desde_id():
    html = generar_html({"MM-02": [ficha()]}, TEMARIOS, INFORME, {"6QLbw1xS8sg"})
    assert 'href="https://www.youtube.com/watch?v=6QLbw1xS8sg"' in html
    assert "Análisis cinemático" in html


def test_escapa_textos_de_youtube():
    malo = ficha(titulo='<script>alert("x")</script>', por_que="<b>hola</b>")
    html = generar_html({"MM-02": [malo]}, TEMARIOS, INFORME, set())
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html
    assert "<b>hola</b>" not in html


def test_asignaturas_en_orden_de_dificultad():
    html = generar_html({}, TEMARIOS, INFORME, set())
    assert html.index("Mecánica de máquinas") < html.index("Termodinámica")


def test_tema_desactivado_no_aparece():
    html = generar_html({}, TEMARIOS, INFORME, set())
    assert "Repaso" not in html


def test_seccion_de_novedades():
    html = generar_html({"MM-02": [ficha()]}, TEMARIOS, INFORME, {"6QLbw1xS8sg"})
    assert "Novedades de esta noche" in html
    assert '<span class="chip nuevo">Nuevo</span>' in html


def test_novedades_es_lista_compacta_con_tema():
    html = generar_html({"MM-02": [ficha()]}, TEMARIOS, INFORME, {"6QLbw1xS8sg"})
    inicio = html.index("Novedades de esta noche")
    fin = html.index("Por asignatura")
    bloque = html[inicio:fin]
    assert "Cinemática del Sólido Rígido" in bloque
    assert "<article" not in bloque


def test_sin_novedades_lo_dice():
    html = generar_html({"MM-02": [ficha()]}, TEMARIOS, INFORME, set())
    assert "Esta noche no ha entrado ningún vídeo nuevo" in html


def test_boton_de_pregunta_para_claude():
    html = generar_html({"MM-02": [ficha()]}, TEMARIOS, INFORME, set())
    assert "Copiar pregunta" in html


def test_errores_del_informe_se_muestran():
    inf = dict(INFORME, errores=["Jev (401): Invalid API key"])
    html = generar_html({}, TEMARIOS, inf, set())
    assert "Invalid API key" in html


def test_video_sin_explicacion_no_rompe():
    html = generar_html({"MM-02": [ficha(por_que="", para_quien="")]}, TEMARIOS, INFORME, set())
    assert "Análisis cinemático" in html


def test_ids_no_validos_no_se_publican():
    html = generar_html({"MM-02": [ficha(vid="javascript:x")]}, TEMARIOS, INFORME, set())
    assert "javascript:x" not in html
