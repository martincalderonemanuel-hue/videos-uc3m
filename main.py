"""
Buscador nocturno de vídeos por temario.

Uso:
    python main.py                      # ejecución real (necesita las claves)
    python main.py --simulado           # prueba completa sin internet ni claves
    python main.py --asignatura "Termodinámica"
    python main.py --reverificar        # comprueba que los vídeos publicados siguen existiendo

Claves (variables de entorno / Secrets de GitHub):
    YOUTUBE_API_KEY, AI_GATEWAY_API_KEY, GEMINI_API_KEY (esta última opcional)
"""
import argparse
import datetime as dt
import glob
import json
import os
import sys
import time

import config
from src import gemini_client, jev_client, youtube_client
from src.errores import CuotaAgotada, ErrorAPI, JevNoDisponible
from src.planificador import marcar_hecha, planificar
from src.puntuacion import puntuar
from src.transcripciones import Transcriptor
from src.verificador import duracion_a_minutos, existe_en_oembed, motivo_descarte
from src.web import generar_html

RAIZ = os.path.dirname(os.path.abspath(__file__))
MAX_FALLOS_JEV_SEGUIDOS = 3


# --- ficheros -------------------------------------------------------------------

def _leer(ruta, por_defecto):
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return por_defecto


def _guardar(ruta, datos):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    temporal = ruta + ".tmp"
    with open(temporal, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1)
    os.replace(temporal, ruta)  # así nunca queda un archivo a medio escribir


def cargar_temarios(carpeta):
    temarios = []
    for ruta in sorted(glob.glob(os.path.join(carpeta, "*.json"))):
        with open(ruta, encoding="utf-8") as f:
            temarios.append(json.load(f))
    return temarios


# --- etapas -----------------------------------------------------------------------

def _reverificar(publicados, sesion, clave, informe):
    """Quita de la web los vídeos que ya no existen o han dejado de ser públicos."""
    ids = [v["id"] for vs in publicados.values() for v in vs]
    if not ids:
        return
    try:
        actuales = youtube_client.detalles(sesion, clave, ids)
    except ErrorAPI as e:
        informe["avisos"].append(f"Reverificación no completada: {e}")
        return
    for tema_id, videos in publicados.items():
        vivos = [v for v in videos if v["id"] in actuales and motivo_descarte(actuales[v["id"]]) is None]
        informe["retirados"] += len(videos) - len(vivos)
        publicados[tema_id] = vivos


def _buscar(plan, estado, evaluados, candidatos, sesion, clave, hoy, informe):
    ya = {(c["tema_id"], c["video_id"]) for c in candidatos}
    for b in plan:
        try:
            ids = youtube_client.buscar(sesion, clave, b["consulta"], b["idioma"], config.RESULTADOS_POR_BUSQUEDA)
        except CuotaAgotada:
            informe["avisos"].append("YouTube: cuota diaria agotada; se continuará la próxima noche.")
            break
        except ErrorAPI as e:
            informe["errores"].append(str(e))
            break
        informe["busquedas"] += 1
        marcar_hecha(estado, b, hoy)
        for vid in ids:
            clave_cache = f"{b['tema_id']}|{vid}"
            if clave_cache in evaluados or (b["tema_id"], vid) in ya:
                continue
            ya.add((b["tema_id"], vid))
            candidatos.append({"video_id": vid, "tema_id": b["tema_id"],
                               "tema_titulo": b["tema_titulo"], "asignatura": b["asignatura"]})


def _ficha(video, candidato, respuestas, nota, transcripcion, hoy):
    snippet = video["snippet"]
    return {
        "id": video["id"],
        "titulo": snippet.get("title", ""),
        "canal": snippet.get("channelTitle", ""),
        "duracion_min": round(duracion_a_minutos(video["contentDetails"].get("duration")), 1),
        "formato": respuestas["formato"],
        "nota": nota,
        "por_que": "",
        "para_quien": "",
        "fecha": hoy.isoformat(),
        "sin_transcripcion": transcripcion is None,
        # solo para Gemini, no se guardan:
        "_tema_id": candidato["tema_id"],
        "_asignatura": candidato["asignatura"],
        "_tema_titulo": candidato["tema_titulo"],
        "_descripcion": snippet.get("description", ""),
        "_transcripcion": transcripcion,
    }


def _evaluar(validos, sesion, clave, transcriptor, evaluados, hoy, informe, dormir):
    aceptados, sin_evaluar = [], []
    fallos_seguidos, ultimo_error, transitorio = 0, None, True
    for i, (c, video) in enumerate(validos):
        if i >= config.MAX_VIDEOS_JEV_POR_NOCHE or fallos_seguidos >= MAX_FALLOS_JEV_SEGUIDOS:
            sin_evaluar.append(c)
            continue
        if i > 0:
            dormir(config.JEV_PAUSA_SEGUNDOS)  # no saturar a Jev
        texto = transcriptor.obtener(c["video_id"], config.MAX_PALABRAS_TRANSCRIPCION)
        estado = jev_client.construir_estado(video, texto, c["tema_titulo"], c["asignatura"])
        preguntas = jev_client.construir_preguntas(c["tema_titulo"], c["asignatura"])
        try:
            respuestas = jev_client.evaluar(sesion, clave, estado, preguntas, dormir=dormir)
        except ErrorAPI as e:
            fallos_seguidos += 1
            ultimo_error = str(e)
            transitorio = isinstance(e, JevNoDisponible)
            sin_evaluar.append(c)
            continue
        fallos_seguidos = 0
        informe["evaluados"] += 1
        resultado = puntuar(video, respuestas)
        evaluados[f"{c['tema_id']}|{c['video_id']}"] = {
            "f": hoy.isoformat(), "n": resultado["nota"], "d": resultado["descartado"]}
        if not resultado["descartado"]:
            aceptados.append(_ficha(video, c, respuestas, resultado["nota"], texto, hoy))
    if fallos_seguidos >= MAX_FALLOS_JEV_SEGUIDOS:
        mensaje = f"{ultimo_error}. Se han guardado {len(sin_evaluar)} vídeos para reintentar mañana."
        # Jev saturado es temporal (aviso); una clave mala o sin permisos es un error de verdad
        informe["avisos" if transitorio else "errores"].append(mensaje)
    elif ultimo_error:
        informe["avisos"].append(f"Algún fallo puntual de Jev: {ultimo_error}")
    if len(validos) > config.MAX_VIDEOS_JEV_POR_NOCHE:
        informe["avisos"].append("Se alcanzó el tope de vídeos de Jev por noche; el resto queda para mañana.")
    return aceptados, sin_evaluar


def _actualizar_top(publicados, aceptados, sesion, informe):
    """Mete los aceptados en el top de cada tema. Los que entran se verifican por segunda vez."""
    entrantes = []
    por_tema = {}
    for f in aceptados:
        por_tema.setdefault(f["_tema_id"], []).append(f)
    for tema_id, nuevos in por_tema.items():
        actuales = publicados.get(tema_id, [])
        ids_actuales = {v["id"] for v in actuales}
        candidatos = actuales + [n for n in nuevos if n["id"] not in ids_actuales]
        candidatos.sort(key=lambda v: v["nota"], reverse=True)
        top = []
        for v in candidatos:
            if len(top) >= config.VIDEOS_POR_TEMA:
                break
            if v["id"] in ids_actuales:
                top.append(v)
                continue
            try:
                existe = existe_en_oembed(v["id"], sesion)
            except Exception:
                existe = False
            if existe:
                top.append(v)
                entrantes.append(v)
            else:
                informe["avisos"].append(f"Descartado en la verificación final: {v['id']}")
        publicados[tema_id] = top
    return entrantes


def _explicar(entrantes, sesion, clave, informe, dormir):
    if not entrantes:
        return
    if not clave:
        informe["avisos"].append("Sin clave de Gemini: los vídeos se publican sin explicación.")
        return
    modelo = gemini_client.elegir_modelo(sesion, clave, config.GEMINI_MODELO_PREFERIDO)
    if not modelo:
        informe["avisos"].append("No se encontró ningún modelo Flash-Lite de Gemini disponible.")
        return
    datos = [{
        "id": v["id"], "asignatura": v["_asignatura"], "tema": v["_tema_titulo"], "titulo": v["titulo"],
        "canal": v["canal"], "descripcion": v["_descripcion"], "transcripcion": v["_transcripcion"],
    } for v in entrantes]
    explicaciones = gemini_client.explicar(sesion, clave, modelo, datos, dormir=dormir)
    for v in entrantes:
        e = explicaciones.get(v["id"])
        if e:
            v["por_que"], v["para_quien"] = e["por_que"], e["para_quien"]
    faltan = len(entrantes) - len(explicaciones)
    if faltan > 0:
        informe["avisos"].append(f"Gemini no explicó {faltan} vídeos; se publican sin explicación.")


def _limpiar_privados(publicados):
    for videos in publicados.values():
        for v in videos:
            for k in [k for k in v if k.startswith("_")]:
                del v[k]


# --- orquestador ------------------------------------------------------------------

def ejecutar(opciones, rutas, sesion, claves, hoy, dormir=time.sleep, ahora=None):
    faltan = [n for n, k in (("YOUTUBE_API_KEY", "youtube"), ("AI_GATEWAY_API_KEY", "jev")) if not claves.get(k)]
    if faltan:
        raise SystemExit(f"Faltan claves: {', '.join(faltan)}. Añádelas en GitHub → Settings → Secrets.")

    datos = rutas["datos"]
    temarios = cargar_temarios(rutas["temarios"])
    estado = _leer(os.path.join(datos, "estado.json"), {})
    evaluados = _leer(os.path.join(datos, "evaluados.json"), {})
    publicados = _leer(os.path.join(datos, "publicados.json"), {})
    candidatos = _leer(os.path.join(datos, "pendientes.json"), [])

    informe = {"fecha": ahora or dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "busquedas": 0,
               "evaluados": 0, "publicados_nuevos": 0, "retirados": 0, "errores": [], "avisos": []}

    # 0. Reverificación semanal de lo ya publicado
    if opciones.get("reverificar") or hoy.weekday() == config.DIA_REVERIFICACION:
        _reverificar(publicados, sesion, claves["youtube"], informe)

    # 1. Búsquedas de esta noche
    plan = planificar(temarios, estado, hoy, config.MAX_BUSQUEDAS_POR_NOCHE,
                      solo_asignatura=opciones.get("asignatura") or None)
    _buscar(plan, estado, evaluados, candidatos, sesion, claves["youtube"], hoy, informe)

    # 2 y 3. Detalles de YouTube + filtros gratuitos (control 1 de existencia)
    validos, sin_evaluar = [], []
    try:
        detalles = youtube_client.detalles(sesion, claves["youtube"], [c["video_id"] for c in candidatos])
    except ErrorAPI as e:
        informe["errores"].append(str(e))
        detalles, sin_evaluar = {}, candidatos
    else:
        for c in candidatos:
            video = detalles.get(c["video_id"])
            motivo = "no existe o no es público" if video is None else motivo_descarte(video)
            if motivo:
                evaluados[f"{c['tema_id']}|{c['video_id']}"] = {"f": hoy.isoformat(), "n": None, "d": motivo}
            else:
                validos.append((c, video))

    # 4 y 5. Jev + puntuación
    obtener = getattr(sesion, "obtener_transcripcion", None)
    transcriptor = Transcriptor(obtener=obtener) if obtener else Transcriptor()
    aceptados, no_evaluados = _evaluar(validos, sesion, claves["jev"], transcriptor, evaluados, hoy, informe, dormir)
    sin_evaluar += no_evaluados

    # 6. Top por tema + verificación final (control 2)
    entrantes = _actualizar_top(publicados, aceptados, sesion, informe)
    informe["publicados_nuevos"] = len(entrantes)

    # 7. Explicaciones con Gemini
    _explicar(entrantes, sesion, claves.get("gemini"), informe, dormir)
    _limpiar_privados(publicados)

    # 8. Guardar y publicar la web
    _guardar(os.path.join(datos, "estado.json"), estado)
    _guardar(os.path.join(datos, "evaluados.json"), evaluados)
    _guardar(os.path.join(datos, "publicados.json"), publicados)
    _guardar(os.path.join(datos, "pendientes.json"), sin_evaluar[:3000])
    _guardar(os.path.join(datos, "informe.json"), informe)

    os.makedirs(rutas["docs"], exist_ok=True)
    html = generar_html(publicados, temarios, informe, {v["id"] for v in entrantes})
    with open(os.path.join(rutas["docs"], "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    open(os.path.join(rutas["docs"], ".nojekyll"), "w").close()
    return informe


def main():
    parser = argparse.ArgumentParser(description="Buscador nocturno de vídeos por temario")
    parser.add_argument("--simulado", action="store_true", help="prueba sin internet ni claves")
    parser.add_argument("--asignatura", default=os.environ.get("ASIGNATURA", ""))
    parser.add_argument("--reverificar", action="store_true",
                        default=os.environ.get("REVERIFICAR", "").lower() == "true")
    args = parser.parse_args()

    hoy = dt.date.today()
    opciones = {"asignatura": args.asignatura.strip(), "reverificar": args.reverificar}

    if args.simulado:
        from src.simulacion import SesionSimulada
        salida = os.path.join(RAIZ, "salida_simulada")
        rutas = {"temarios": os.path.join(RAIZ, "temarios"),
                 "datos": os.path.join(salida, "datos"), "docs": os.path.join(salida, "docs")}
        claves = {"youtube": "simulada", "jev": "simulada", "gemini": "simulada"}
        informe = ejecutar(opciones, rutas, SesionSimulada(), claves, hoy, dormir=lambda _: None)
        print(f"Simulación terminada. Abre {os.path.join(rutas['docs'], 'index.html')}")
    else:
        import requests
        rutas = {"temarios": os.path.join(RAIZ, "temarios"),
                 "datos": os.path.join(RAIZ, "datos"), "docs": os.path.join(RAIZ, "docs")}
        claves = {"youtube": os.environ.get("YOUTUBE_API_KEY", ""),
                  "jev": os.environ.get("AI_GATEWAY_API_KEY", ""),
                  "gemini": os.environ.get("GEMINI_API_KEY", "")}
        with requests.Session() as sesion:
            informe = ejecutar(opciones, rutas, sesion, claves, hoy)

    print(json.dumps(informe, ensure_ascii=False, indent=2))
    if informe["errores"]:
        print("\nHa habido errores: revisa el apartado 'errores' de arriba.")
        sys.exit(1)


if __name__ == "__main__":
    main()
