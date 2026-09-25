"""
Genera la página web (docs/index.html) que se publica en GitHub Pages.

Todo el texto que viene de YouTube o de las IAs se escapa con html.escape,
y los enlaces se construyen solo a partir de IDs válidos (url_video).
"""
from html import escape

from src.verificador import url_video

ETIQUETAS_FORMATO = {
    "teoria": "Teoría",
    "problemas_resueltos": "Problemas resueltos",
    "practica": "Práctica / simulación",
    "resumen": "Resumen",
}

CSS = """
:root{--bg:#f7f6f2;--card:#fff;--txt:#1f1e1b;--sub:#6b6a64;--line:#e4e2da;--acc:#0f6e56;--acc-bg:#e1f5ee;--warn:#854f0b;--warn-bg:#faeeda}
@media (prefers-color-scheme:dark){:root{--bg:#1b1b19;--card:#252523;--txt:#ecebe6;--sub:#a3a29b;--line:#3a3935;--acc:#5dcaa5;--acc-bg:#0f3a2e;--warn:#efb35f;--warn-bg:#3d2a0c}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--txt);font:16px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:26px;margin:0 0 4px;font-weight:600}
h2{font-size:20px;margin:36px 0 12px;font-weight:600}
h3{font-size:16px;margin:22px 0 10px;font-weight:600;color:var(--sub)}
.sub{color:var(--sub);font-size:14px;margin:0}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden;display:flex;flex-direction:column}
.card img{width:100%;aspect-ratio:16/9;object-fit:cover;display:block;background:var(--line)}
.body{padding:12px 14px 14px;display:flex;flex-direction:column;gap:6px;flex:1}
.titulo{font-weight:600;color:var(--txt);text-decoration:none;line-height:1.35}
.titulo:hover{text-decoration:underline}
.meta{font-size:13px;color:var(--sub)}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chip{font-size:12px;padding:2px 8px;border-radius:99px;background:var(--acc-bg);color:var(--acc)}
.chip.aviso{background:var(--warn-bg);color:var(--warn)}
.chip.nuevo{background:var(--acc);color:var(--card)}
.nuevos{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 16px;margin-bottom:10px}
.nuevos ul{margin:8px 0 0;padding-left:18px}
.nuevos li{margin:4px 0;font-size:15px}
.nuevos a{color:var(--txt)}
.porque{font-size:14px;margin:4px 0 0}
.paraquien{font-size:13px;color:var(--sub);margin:0}
button{margin-top:auto;align-self:flex-start;font:inherit;font-size:13px;padding:6px 10px;border-radius:8px;border:1px solid var(--line);background:transparent;color:var(--txt);cursor:pointer}
button:hover{border-color:var(--acc);color:var(--acc)}
details{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:4px 16px 12px;margin-bottom:12px}
summary{cursor:pointer;font-weight:600;font-size:18px;padding:10px 0}
.vacio{color:var(--sub);font-size:14px;margin:0 0 8px}
.informe{margin-top:40px;font-size:13px;color:var(--sub);border-top:1px solid var(--line);padding-top:16px}
.error{color:var(--warn)}
"""

JS = """
document.querySelectorAll('button[data-q]').forEach(function(b){
  b.addEventListener('click',function(){
    var t=b.getAttribute('data-q');
    function ok(){var o=b.textContent;b.textContent='¡Copiada! Pégala en Claude';setTimeout(function(){b.textContent=o},2500)}
    if(navigator.clipboard){navigator.clipboard.writeText(t).then(ok,function(){prompt('Copia la pregunta:',t)})}
    else{prompt('Copia la pregunta:',t)}
  });
});
"""


def _minutos(m):
    total = int(round(m or 0))
    return f"{total // 60} h {total % 60} min" if total >= 60 else f"{total} min"


def _tarjeta(v, asignatura, tema_titulo, nuevo=False):
    try:
        url = url_video(v["id"])
    except ValueError:
        return ""
    miniatura = f"https://i.ytimg.com/vi/{v['id']}/mqdefault.jpg"
    formato = ETIQUETAS_FORMATO.get(v.get("formato"), "")
    nota = f"{(v.get('nota') or 0) * 10:.1f}".replace(".", ",")
    pregunta = (
        f"Tengo una duda sobre el vídeo «{v.get('titulo', '')}» ({url}), "
        f"del tema «{tema_titulo}» de {asignatura}: "
    )
    chips = ['<span class="chip nuevo">Nuevo</span>'] if nuevo else []
    chips.append(f'<span class="chip">Nota {nota}/10</span>')
    if formato:
        chips.append(f'<span class="chip">{escape(formato)}</span>')
    if v.get("sin_transcripcion"):
        chips.append('<span class="chip aviso" title="Evaluado solo con título y descripción">Sin transcripción</span>')
    por_que = f'<p class="porque">{escape(v["por_que"])}</p>' if v.get("por_que") else ""
    para_quien = f'<p class="paraquien">{escape(v["para_quien"])}</p>' if v.get("para_quien") else ""
    return f"""
<article class="card">
  <a href="{url}" target="_blank" rel="noopener"><img src="{miniatura}" alt="" loading="lazy" onerror="this.style.visibility='hidden'"></a>
  <div class="body">
    <a class="titulo" href="{url}" target="_blank" rel="noopener">{escape(v.get('titulo', ''))}</a>
    <div class="meta">{escape(v.get('canal', ''))} · {_minutos(v.get('duracion_min'))}</div>
    <div class="chips">{''.join(chips)}</div>
    {por_que}{para_quien}
    <button type="button" data-q="{escape(pregunta, quote=True)}">Copiar pregunta para Claude</button>
  </div>
</article>"""


def generar_html(publicados, temarios, informe, novedades):
    """publicados = {tema_id: [fichas]}; novedades = IDs que han entrado esta noche."""
    temarios = sorted(temarios, key=lambda t: t["prioridad"])

    # Novedades de esta noche: lista compacta agrupada por asignatura
    grupos_nuevos = []
    for t in temarios:
        filas = []
        for tema in t["temas"]:
            if not tema.get("activo", True):
                continue
            for v in publicados.get(tema["id"], []):
                if v["id"] not in novedades:
                    continue
                try:
                    url = url_video(v["id"])
                except ValueError:
                    continue
                filas.append(
                    f'<li><a href="{url}" target="_blank" rel="noopener">{escape(v.get("titulo", ""))}</a>'
                    f' <span class="sub">· {escape(tema["titulo"])}</span></li>'
                )
        if filas:
            grupos_nuevos.append(
                f'<div class="nuevos"><strong>{escape(t["asignatura"])}</strong> '
                f'<span class="sub">· {len(filas)} nuevos</span><ul>{"".join(filas)}</ul></div>'
            )
    bloque_nuevos = (
        "".join(grupos_nuevos) if grupos_nuevos
        else '<p class="vacio">Esta noche no ha entrado ningún vídeo nuevo en el top de ningún tema.</p>'
    )

    # Todas las asignaturas
    bloques = []
    for t in temarios:
        temas_html = []
        total = 0
        for tema in t["temas"]:
            if not tema.get("activo", True):
                continue
            videos = publicados.get(tema["id"], [])
            total += len(videos)
            contenido = (
                f'<div class="grid">{"".join(_tarjeta(v, t["asignatura"], tema["titulo"], v["id"] in novedades) for v in videos)}</div>'
                if videos else '<p class="vacio">Aún sin vídeos: se buscarán en próximas noches.</p>'
            )
            temas_html.append(f"<h3>{escape(tema['titulo'])}</h3>{contenido}")
        bloques.append(
            f"<details><summary>{escape(t['asignatura'])} <span class=\"sub\">· {total} vídeos</span></summary>"
            f"{''.join(temas_html)}</details>"
        )

    errores = "".join(f'<li class="error">{escape(e)}</li>' for e in informe.get("errores", []))
    informe_html = (
        f'<div class="informe">Última ejecución: {escape(str(informe.get("fecha", "—")))} · '
        f'{informe.get("busquedas", 0)} búsquedas · {informe.get("evaluados", 0)} vídeos evaluados · '
        f'{informe.get("publicados_nuevos", 0)} nuevos en el top'
        + (f"<ul>{errores}</ul>" if errores else "")
        + "</div>"
    )

    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Vídeos para estudiar</title>
<style>{CSS}</style>
</head>
<body>
<main>
  <h1>Vídeos para estudiar</h1>
  <p class="sub">Seleccionados cada noche por tema de tu temario · actualizado {escape(str(informe.get("fecha", "")))}</p>
  <h2>Novedades de esta noche</h2>
  {bloque_nuevos}
  <h2>Por asignatura</h2>
  {''.join(bloques)}
  {informe_html}
</main>
<script>{JS}</script>
</body>
</html>
"""
