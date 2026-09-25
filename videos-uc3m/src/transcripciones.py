"""
Transcripciones de YouTube (librería no oficial `youtube-transcript-api`).

Puede fallar a menudo desde servidores en la nube: YouTube suele bloquear esas IP.
Por eso, tras varios fallos seguidos, deja de intentarlo esa noche y los vídeos
se evalúan solo con título y descripción.
"""


def _obtener_con_libreria(video_id):
    from youtube_transcript_api import YouTubeTranscriptApi

    idiomas = ["es", "en"]
    if hasattr(YouTubeTranscriptApi, "fetch") or not hasattr(YouTubeTranscriptApi, "get_transcript"):
        fragmentos = YouTubeTranscriptApi().fetch(video_id, languages=idiomas)  # versión 1.x
        return " ".join(getattr(f, "text", "") for f in fragmentos)
    fragmentos = YouTubeTranscriptApi.get_transcript(video_id, languages=idiomas)  # versión 0.x
    return " ".join(f.get("text", "") for f in fragmentos)


class Transcriptor:
    def __init__(self, obtener=_obtener_con_libreria, max_fallos_seguidos=5):
        self._obtener = obtener
        self._max_fallos = max_fallos_seguidos
        self.fallos_seguidos = 0
        self.conseguidas = 0

    @property
    def rendido(self):
        return self.fallos_seguidos >= self._max_fallos

    def obtener(self, video_id, max_palabras):
        """Devuelve el texto recortado, o None si no hay transcripción."""
        if self.rendido:
            return None
        try:
            texto = self._obtener(video_id)
        except Exception:  # la librería lanza muchos tipos de error distintos
            self.fallos_seguidos += 1
            return None
        self.fallos_seguidos = 0
        if not texto or not texto.strip():
            return None
        self.conseguidas += 1
        return " ".join(texto.split()[:max_palabras])
