"""
Planificador: decide qué búsquedas se hacen esta noche.

1. Cada tema tiene una lista fija de consultas, de la más general a la más específica.
2. El cupo de búsquedas se reparte entre asignaturas según PESOS_POR_PRIORIDAD.
3. Dentro de cada asignatura se avanza "en anchura": primero la 1.ª consulta de
   todos los temas, luego la 2.ª de todos, etc. Así se cubre el temario entero cuanto antes.
4. El cupo que una asignatura no puede gastar pasa a las demás, por orden de dificultad.
"""
import datetime as dt

import config


def consultas_de_tema(tema, asignatura):
    """Lista ordenada de (consulta, idioma) para un tema, sin duplicados."""
    es = tema.get("palabras_clave", [])
    en = tema.get("palabras_clave_en", [])
    lista = []
    # Pasada 1: la palabra clave principal en cada idioma
    lista += [(es[0], "es")] if es else []
    lista += [(en[0], "en")] if en else []
    # Pasada 2: el resto de palabras clave, alternando idiomas
    for i in range(1, max(len(es), len(en))):
        if i < len(es):
            lista.append((es[i], "es"))
        if i < len(en):
            lista.append((en[i], "en"))
    # Pasada 3: subtemas, con el nombre de la asignatura como contexto
    lista += [(f"{s} {asignatura}", "es") for s in tema.get("subtemas", [])]
    # Pasada 4: problemas resueltos
    lista += [(f"{es[0]} ejercicios resueltos", "es")] if es else []
    lista += [(f"{en[0]} solved problems", "en")] if en else []
    # Pasada 5 (actualización 5): variantes de clase, lecture y examen.
    # Van AL FINAL para que las consultas ya hechas no cambien de posición.
    for i in range(max(len(es), len(en))):
        if i < len(es):
            lista.append((f"{es[i]} clase", "es"))
        if i < len(en):
            lista.append((f"{en[i]} lecture", "en"))
    lista += [(f"{es[0]} examen resuelto", "es")] if es else []
    lista += [(f"{en[0]} exam problems", "en")] if en else []
    lista += [(f"{en[0]} tutorial", "en")] if en else []
    lista += [(f"{s} explicación", "es") for s in tema.get("subtemas", [])]

    vistas, unicas = set(), []
    for c in lista:
        if c not in vistas:
            vistas.add(c)
            unicas.append(c)
    return unicas


def _siguiente_indice(tema_id, total, estado, hoy):
    """Índice de la próxima consulta pendiente, o None si el tema está al día."""
    info = estado.get(tema_id, {})
    siguiente = info.get("siguiente", 0)
    if siguiente < total:
        return siguiente
    completado = info.get("completado")
    if completado:
        dias = (hoy - dt.date.fromisoformat(completado)).days
        if dias >= config.DIAS_PARA_REPETIR_BUSQUEDAS:
            return 0
    return None


def _pendientes(temario, estado, hoy, incompletos=frozenset()):
    """Consultas pendientes de una asignatura, ya en orden 'en anchura'.

    Los temas incompletos (con menos vídeos de los deseados) van delante de todo.
    """
    candidatas = []
    temas_activos = [t for t in temario["temas"] if t.get("activo", True)]
    for orden, tema in enumerate(temas_activos):
        consultas = consultas_de_tema(tema, temario["asignatura"])
        inicio = _siguiente_indice(tema["id"], len(consultas), estado, hoy)
        if inicio is None:
            continue
        for indice in range(inicio, len(consultas)):
            consulta, idioma = consultas[indice]
            candidatas.append({
                "asignatura": temario["asignatura"],
                "prioridad": temario["prioridad"],
                "tema_id": tema["id"],
                "tema_titulo": tema["titulo"],
                "consulta": consulta,
                "idioma": idioma,
                "indice": indice,
                "total": len(consultas),
                "_orden": (tema["id"] not in incompletos, indice - inicio, orden),
            })
    candidatas.sort(key=lambda c: c["_orden"])
    for c in candidatas:
        del c["_orden"]
    return candidatas


def _repartir(presupuesto, pendientes_por_asig, prioridades):
    """Cuántas búsquedas le tocan a cada asignatura."""
    orden = sorted(pendientes_por_asig, key=lambda a: prioridades[a])
    cuota = {
        a: int(presupuesto * config.PESOS_POR_PRIORIDAD.get(prioridades[a], 0))
        for a in orden
    }
    # El redondeo sobrante va a las más difíciles
    sobrante = presupuesto - sum(cuota.values())
    i = 0
    while sobrante > 0 and orden:
        cuota[orden[i % len(orden)]] += 1
        sobrante -= 1
        i += 1
    # Lo que una asignatura no puede gastar pasa a las demás
    asignado = {a: min(cuota[a], len(pendientes_por_asig[a])) for a in orden}
    libre = presupuesto - sum(asignado.values())
    while libre > 0:
        movido = False
        for a in orden:
            if libre > 0 and asignado[a] < len(pendientes_por_asig[a]):
                asignado[a] += 1
                libre -= 1
                movido = True
        if not movido:
            break
    return asignado


def planificar(temarios, estado, hoy, presupuesto, solo_asignatura=None, incompletos=None):
    """Devuelve la lista de búsquedas de esta noche, ordenada por prioridad.

    incompletos = IDs de temas que aún no tienen todos sus vídeos: se buscan primero.
    """
    incompletos = frozenset(incompletos or ())
    if solo_asignatura:
        temarios = [t for t in temarios if t["asignatura"] == solo_asignatura]
    pendientes = {t["asignatura"]: _pendientes(t, estado, hoy, incompletos) for t in temarios}
    pendientes = {a: p for a, p in pendientes.items() if p}
    if not pendientes:
        return []
    prioridades = {t["asignatura"]: t["prioridad"] for t in temarios}
    asignado = _repartir(presupuesto, pendientes, prioridades)
    plan = []
    for a in sorted(pendientes, key=lambda x: prioridades[x]):
        plan += pendientes[a][: asignado[a]]
    return plan


def marcar_hecha(estado, busqueda, hoy):
    """Actualiza el estado tras completar una búsqueda."""
    info = estado.setdefault(busqueda["tema_id"], {"siguiente": 0, "completado": None})
    info["siguiente"] = busqueda["indice"] + 1
    if info["siguiente"] >= busqueda["total"]:
        info["completado"] = hoy.isoformat()


def proxima_busqueda(temarios, estado):
    """Fecha en la que el primer tema terminado vuelve a buscarse (None si no hay ninguno)."""
    fechas = []
    for t in temarios:
        for tema in t["temas"]:
            completado = estado.get(tema["id"], {}).get("completado")
            if tema.get("activo", True) and completado:
                fechas.append(dt.date.fromisoformat(completado))
    if not fechas:
        return None
    return min(fechas) + dt.timedelta(days=config.DIAS_PARA_REPETIR_BUSQUEDAS)
