"""
Configuración del buscador de vídeos.

Todo lo que quieras ajustar sin tocar el código está aquí.
Las claves NO van aquí: se leen de variables de entorno (Secrets de GitHub).
"""

# ---------------------------------------------------------------------------
# Reparto del cupo diario entre asignaturas (por prioridad del temario JSON)
# 1 = la más difícil. Los pesos deben sumar 1.
# ---------------------------------------------------------------------------
PESOS_POR_PRIORIDAD = {
    1: 0.30,  # Mecánica de máquinas
    2: 0.25,  # Electrónica analógica
    3: 0.20,  # Termodinámica
    4: 0.15,  # Electrónica digital
    5: 0.10,  # Mecánica de estructuras
}

# ---------------------------------------------------------------------------
# Límites por noche
# ---------------------------------------------------------------------------
MAX_BUSQUEDAS_POR_NOCHE = 90        # YouTube permite ~100/día; dejamos margen
RESULTADOS_POR_BUSQUEDA = 15
MAX_VIDEOS_JEV_POR_NOCHE = 1200     # ~2.000 tokens/vídeo x 1.200 x 30 noches ≈ 3 $/mes (< 5 $ gratis de Vercel)
MAX_CARACTERES_ESTADO_JEV = 6000    # recorte del texto que se manda a Jev
MAX_PALABRAS_TRANSCRIPCION = 1500

# ---------------------------------------------------------------------------
# Filtros gratuitos (antes de gastar nada en Jev)
# ---------------------------------------------------------------------------
DURACION_MIN_MINUTOS = 5
DURACION_MAX_MINUTOS = 90
REGION = "ES"

# ---------------------------------------------------------------------------
# Umbrales sobre las respuestas de Jev (Jev responde, el código decide)
# ---------------------------------------------------------------------------
UMBRAL_CUBRE_TEMA = 0.70
UMBRAL_PROMOCIONAL = 0.60
NIVELES_ACEPTADOS = ("universitario", "posgrado")

# ---------------------------------------------------------------------------
# Nota final = pesos de cada ingrediente (0 a 1)
# ---------------------------------------------------------------------------
PESO_RIGOR = 0.5
PESO_CUBRE_TEMA = 0.3
PESO_POPULARIDAD = 0.2
PENALIZACION_PARA_NINOS = 0.15
RATIO_LIKES_EXCELENTE = 0.03        # 3 % de likes/visitas ya cuenta como popularidad máxima

# ---------------------------------------------------------------------------
# Publicación
# ---------------------------------------------------------------------------
VIDEOS_POR_TEMA = 3                 # los mejores N de cada tema que aparecen en la web
DIAS_PARA_REPETIR_BUSQUEDAS = 30    # cuando un tema agota sus búsquedas, se repite pasado este tiempo
DIA_REVERIFICACION = 0              # 0 = lunes: se comprueba que los vídeos publicados siguen existiendo

# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------
JEV_MODELO = "typesafe-ai/jev"
JEV_URL = "https://ai-gateway.vercel.sh/v1/evaluate"
JEV_PAUSA_SEGUNDOS = 0.3            # pausa entre vídeos para no saturar a Jev (~6 min para 1.200 vídeos)
GEMINI_MODELO_PREFERIDO = ""        # vacío = se elige solo el Flash-Lite disponible más reciente
GEMINI_VIDEOS_POR_PETICION = 10
GEMINI_PAUSA_SEGUNDOS = 7           # la capa gratuita admite pocas peticiones por minuto
