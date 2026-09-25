"""
Modo simulado: imita YouTube, Jev y Gemini sin internet ni claves.

Sirve para probar el sistema completo (tests y `python main.py --simulado`)
y para ver cómo quedará la web antes de configurar nada.
Los datos son inventados pero deterministas: la misma búsqueda da siempre lo mismo.
"""
import base64
import hashlib
import json


class _Respuesta:
    def __init__(self, status_code, datos):
        self.status_code = status_code
        self._datos = datos
        self.text = json.dumps(datos, ensure_ascii=False)

    def json(self):
        return self._datos


def _hash(texto, n=8):
    return int(hashlib.sha1(texto.encode("utf-8")).hexdigest()[:n], 16)


def _id_video(texto):
    crudo = hashlib.sha1(texto.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(crudo).decode()[:11]


CANALES = ["Profe de Ingeniería", "UniTutor", "Engineering Explained ES", "Clases UPM",
           "MIT OpenCourseWare", "Academia Técnica", "Ing. Paso a Paso", "Mechanics Lab"]


class SesionSimulada:
    def __init__(self, cuota_busquedas=None, jev_roto=False, borrados=None, oembed_falla=False):
        self.cuota_busquedas = cuota_busquedas
        self.jev_roto = jev_roto
        self.borrados = set(borrados or [])
        self.oembed_falla = oembed_falla
        self.busquedas = 0
        self._consulta_de = {}

    # --- transcripciones simuladas -----------------------------------------
    def obtener_transcripcion(self, video_id):
        if _hash(video_id) % 3 == 0:
            raise RuntimeError("sin subtítulos")
        return f"En esta clase vemos {self._consulta_de.get(video_id, 'el tema')} con ejemplos resueltos. " * 40

    # --- HTTP ----------------------------------------------------------------
    def get(self, url, params=None, **_):
        params = params or {}
        if url.endswith("/search"):
            return self._buscar(params)
        if url.endswith("/videos"):
            return self._videos(params)
        if url.endswith("/models"):
            return _Respuesta(200, {"models": [
                {"name": "models/gemini-simulado-flash-lite", "supportedGenerationMethods": ["generateContent"]}
            ]})
        if "oembed" in url:
            return _Respuesta(404 if self.oembed_falla else 200, {"title": "ok"})
        return _Respuesta(404, {"error": {"message": f"URL simulada desconocida: {url}"}})

    def post(self, url, params=None, json=None, **_):
        if "ai-gateway" in url:
            return self._jev(json or {})
        if ":generateContent" in url:
            return self._gemini(json or {})
        return _Respuesta(404, {"error": {"message": f"URL simulada desconocida: {url}"}})

    # --- YouTube ---------------------------------------------------------------
    def _buscar(self, params):
        if self.cuota_busquedas is not None and self.busquedas >= self.cuota_busquedas:
            return _Respuesta(403, {"error": {"code": 403, "message": "quota",
                                              "errors": [{"reason": "quotaExceeded"}]}})
        self.busquedas += 1
        q = params.get("q", "")
        items = []
        for i in range(8):
            vid = _id_video(f"{q}|{i}")
            self._consulta_de[vid] = q
            items.append({"id": {"kind": "youtube#video", "videoId": vid}})
        return _Respuesta(200, {"items": items})

    def _videos(self, params):
        items = []
        for vid in params.get("id", "").split(","):
            if not vid or vid in self.borrados:
                continue
            h = _hash(vid)
            q = self._consulta_de.get(vid, "Ingeniería")
            minutos = 3 + h % 55
            vistas = 2000 + h % 200000
            items.append({
                "id": vid,
                "snippet": {
                    "title": f"{q[:1].upper()}{q[1:]} · clase {1 + h % 12}",
                    "description": f"Vídeo simulado sobre {q}.",
                    "channelTitle": CANALES[h % len(CANALES)],
                },
                "contentDetails": {"duration": f"PT{minutos}M{h % 60}S"},
                "status": {"uploadStatus": "processed", "privacyStatus": "public",
                           "embeddable": True, "madeForKids": h % 9 == 0},
                "statistics": {"viewCount": str(vistas), "likeCount": str(vistas * (h % 40) // 1000)},
            })
        return _Respuesta(200, {"items": items})

    # --- Jev -------------------------------------------------------------------
    def _jev(self, cuerpo):
        if self.jev_roto:
            return _Respuesta(503, {"error": {"message": "Servicio no disponible (simulado)"}})
        titulo = str(cuerpo.get("state", {}).get("titulo", ""))
        h = _hash(titulo)
        niveles = ["universitario", "universitario", "universitario", "bachillerato", "divulgativo", "posgrado"]
        formatos = ["teoria", "problemas_resueltos", "practica", "resumen"]
        return _Respuesta(200, {"answers": {
            "cubre_tema": {"type": "boolean", "probability": 0.5 + (h % 50) / 100},
            "nivel": {"type": "choice", "choice": niveles[h % len(niveles)]},
            "rigor": {"type": "score", "score": (h % 21) / 10},
            "formato": {"type": "choice", "choice": formatos[(h // 7) % len(formatos)]},
            "promocional": {"type": "boolean", "probability": (h % 10) / 20},
        }, "usage": {"inputTokens": 900, "outputTokens": 20}})

    # --- Gemini ----------------------------------------------------------------
    def _gemini(self, cuerpo):
        texto = cuerpo["contents"][0]["parts"][0]["text"]
        fichas = json.loads(texto.split("\n\n", 1)[1])
        salida = [{
            "id": f["id"],
            "por_que": f"Explica «{f['tema']}» con ejemplos claros y un problema resuelto al final.",
            "para_quien": "Para entender la teoría antes de hacer ejercicios",
        } for f in fichas]
        return _Respuesta(200, {"candidates": [{"content": {"parts": [
            {"text": json.dumps(salida, ensure_ascii=False)}]}}]})
