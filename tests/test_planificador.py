"""Tests de planificador.py: reparto del cupo nocturno por jerarquía."""
import datetime as dt
import glob
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config
from src.planificador import consultas_de_tema, marcar_hecha, planificar, proxima_busqueda

RAIZ = os.path.join(os.path.dirname(__file__), "..")
HOY = dt.date(2026, 9, 26)


def temarios_reales():
    out = []
    for ruta in glob.glob(os.path.join(RAIZ, "temarios", "*.json")):
        with open(ruta, encoding="utf-8") as f:
            out.append(json.load(f))
    return out


def temario(nombre, prioridad, n_temas, activo=True):
    return {
        "asignatura": nombre,
        "prioridad": prioridad,
        "temas": [
            {
                "id": f"{nombre[:2].upper()}-{i}",
                "activo": activo,
                "titulo": f"Tema {i}",
                "subtemas": [f"sub {i}a"],
                "palabras_clave": [f"es {i}"],
                "palabras_clave_en": [f"en {i}"],
            }
            for i in range(1, n_temas + 1)
        ],
    }


# --- consultas de un tema ---------------------------------------------------

def test_primeras_consultas_son_palabra_clave_es_y_en():
    t = temarios_reales()
    mm = next(x for x in t if x["prioridad"] == 1)
    tema = mm["temas"][1]
    consultas = consultas_de_tema(tema, mm["asignatura"])
    assert consultas[0] == (tema["palabras_clave"][0], "es")
    assert consultas[1] == (tema["palabras_clave_en"][0], "en")


def test_consultas_incluyen_subtemas_y_ejercicios():
    tema = temario("Prueba", 1, 1)["temas"][0]
    textos = [c for c, _ in consultas_de_tema(tema, "Prueba")]
    assert "sub 1a Prueba" in textos
    assert "es 1 ejercicios resueltos" in textos
    assert "en 1 solved problems" in textos


def test_consultas_sin_duplicados():
    for t in temarios_reales():
        for tema in t["temas"]:
            c = consultas_de_tema(tema, t["asignatura"])
            assert len(c) == len(set(c))


# --- reparto ----------------------------------------------------------------

def test_primera_noche_usa_todo_el_cupo_y_respeta_pesos():
    plan = planificar(temarios_reales(), {}, HOY, 90)
    assert len(plan) == 90
    por_prioridad = {}
    for p in plan:
        por_prioridad[p["prioridad"]] = por_prioridad.get(p["prioridad"], 0) + 1
    assert por_prioridad[1] > por_prioridad[2] > por_prioridad[3] > por_prioridad[4] > por_prioridad[5]
    assert por_prioridad[1] == 28  # 27 por peso + 1 de redondeo, que va a la más difícil


def test_temas_desactivados_no_se_planifican():
    plan = planificar(temarios_reales(), {}, HOY, 90)
    assert all(p["tema_id"] != "MM-01" for p in plan)


def test_primero_se_cubren_todos_los_temas():
    # recorrido en anchura: la 1.ª consulta de cada tema antes que la 2.ª de ninguno
    t = [temario("Aaa", 1, 4)]
    plan = planificar(t, {}, HOY, 4)
    assert [p["tema_id"] for p in plan] == ["AA-1", "AA-2", "AA-3", "AA-4"]
    assert all(p["indice"] == 0 for p in plan)


def test_cupo_sobrante_pasa_a_las_demas_por_prioridad():
    t = [temario("Aaa", 1, 10), temario("Bbb", 2, 10), temario("Ccc", 5, 10, activo=False)]
    plan = planificar(t, {}, HOY, 20)
    assert len(plan) == 20
    assert all(p["asignatura"] != "Ccc" for p in plan)


def test_menos_pendiente_que_cupo():
    t = [temario("Aaa", 1, 1)]
    total = len(consultas_de_tema(t[0]["temas"][0], "Aaa"))
    assert len(planificar(t, {}, HOY, 90)) == total


def test_solo_una_asignatura():
    plan = planificar(temarios_reales(), {}, HOY, 30, solo_asignatura="Termodinámica")
    assert len(plan) == 30
    assert {p["asignatura"] for p in plan} == {"Termodinámica"}


# --- estado entre noches ----------------------------------------------------

def test_continua_donde_se_quedo():
    t = [temario("Aaa", 1, 1)]
    plan = planificar(t, {"AA-1": {"siguiente": 2, "completado": None}}, HOY, 1)
    assert plan[0]["indice"] == 2


def test_marcar_hecha_avanza_y_completa():
    t = [temario("Aaa", 1, 1)]
    estado = {}
    for p in planificar(t, estado, HOY, 90):
        marcar_hecha(estado, p, HOY)
    assert estado["AA-1"]["completado"] == "2026-09-26"
    assert planificar(t, estado, HOY, 90) == []


def test_tema_completado_hace_tiempo_se_repite():
    t = [temario("Aaa", 1, 1)]
    total = len(consultas_de_tema(t[0]["temas"][0], "Aaa"))
    estado = {"AA-1": {"siguiente": total, "completado": "2026-08-01"}}
    plan = planificar(t, estado, HOY, 90)
    assert plan and plan[0]["indice"] == 0


# --- actualización 5: más búsquedas, prioridad a temas incompletos, aviso de pausa ---

def test_consultas_nuevas_van_al_final_sin_cambiar_las_antiguas():
    # las consultas ya hechas conservan su posición: el estado guardado sigue siendo válido
    tema = temario("Prueba", 1, 1)["temas"][0]
    textos = [c for c, _ in consultas_de_tema(tema, "Prueba")]
    assert textos[:6] == ["es 1", "en 1", "sub 1a Prueba", "es 1 ejercicios resueltos",
                          "en 1 solved problems", "es 1 clase"]
    assert "en 1 lecture" in textos
    assert "en 1 exam problems" in textos


def test_temario_real_tiene_al_menos_el_doble_de_busquedas():
    total = sum(len(consultas_de_tema(tema, t["asignatura"]))
                for t in temarios_reales() for tema in t["temas"] if tema.get("activo", True))
    assert total >= 1000  # antes eran 526: se agotaban en una semana


def test_tema_terminado_antes_de_ampliar_continua_con_las_nuevas():
    t = [temario("Aaa", 1, 1)]
    estado = {"AA-1": {"siguiente": 5, "completado": "2026-10-01"}}  # terminó con 5 consultas
    plan = planificar(t, estado, HOY, 90)
    assert plan and plan[0]["indice"] == 5


def test_temas_incompletos_van_primero():
    t = [temario("Aaa", 1, 4)]
    plan = planificar(t, {}, HOY, 3, incompletos={"AA-3"})
    assert [p["tema_id"] for p in plan[:2]] == ["AA-3", "AA-3"]


def test_repetir_busquedas_a_los_7_dias():
    assert config.DIAS_PARA_REPETIR_BUSQUEDAS == 7


def test_proxima_busqueda_es_el_tema_que_antes_vuelve():
    t = [temario("Aaa", 1, 2)]
    estado = {"AA-1": {"siguiente": 99, "completado": "2026-10-01"},
              "AA-2": {"siguiente": 99, "completado": "2026-09-28"}}
    assert proxima_busqueda(t, estado) == dt.date(2026, 9, 28) + dt.timedelta(days=config.DIAS_PARA_REPETIR_BUSQUEDAS)


def test_proxima_busqueda_sin_temas_completados():
    assert proxima_busqueda([temario("Aaa", 1, 1)], {}) is None
