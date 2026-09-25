# Buscador nocturno de vídeos por temario

Cada noche, a las 02:30 (hora de Madrid), este programa busca en YouTube vídeos para los
temas de tus 5 asignaturas, comprueba que existen, los filtra con Jev, pide a Gemini que
explique los mejores y publica una web con los 3 mejores vídeos de cada tema.

No necesitas programar. Solo tienes que seguir la **instalación** una vez (unos 30–45 minutos de clics).

---

## 1. Instalación (solo una vez)

### Paso 1 · Consigue las 3 claves

Guárdalas en un sitio seguro (gestor de contraseñas o un archivo privado). **Nunca las pegues
en un chat, una captura ni un archivo del proyecto.**

| Clave | Dónde se consigue | Nombre que le darás en GitHub |
| --- | --- | --- |
| YouTube | Google Cloud Console → Credenciales (ya la tienes; te recomiendo **regenerarla**, porque salió en una captura) | `YOUTUBE_API_KEY` |
| Jev (Vercel) | vercel.com → tu cuenta → **AI Gateway** → **API Keys** → Create key | `AI_GATEWAY_API_KEY` |
| Gemini | aistudio.google.com con tu **Gmail personal** → **Get API key** → Create API key | `GEMINI_API_KEY` |

- La de Gemini es opcional: sin ella, los vídeos se publican igual pero sin las dos frases de explicación.
- **No compres créditos en Vercel**: según varias fuentes, al hacerlo dejas de recibir los 5 $ gratis cada mes.

### Paso 2 · Crea el repositorio en GitHub

1. Entra en github.com → botón **+** (arriba a la derecha) → **New repository**.
2. Nombre: `videos-uc3m`. Marca **Public** (GitHub Pages gratis solo funciona con repositorios públicos;
   las claves no se verán porque irán en Secrets).
3. Pulsa **Create repository**.

### Paso 3 · Sube los archivos

1. Descomprime el `.zip` en tu ordenador.
2. En la página del repositorio recién creado, pulsa **uploading an existing file**.
3. Arrastra **todo el contenido** de la carpeta `videos-uc3m` (no la carpeta en sí, sino lo que hay dentro).
4. Abajo, pulsa **Commit changes**.
5. Comprueba que aparece la carpeta `.github`. Si no aparece (a veces el navegador no sube carpetas que
   empiezan por punto): **Add file → Create new file**, escribe como nombre
   `.github/workflows/nocturno.yml`, pega el contenido de ese archivo y pulsa **Commit changes**.

### Paso 4 · Guarda las claves en Secrets

1. En el repositorio: **Settings** → **Secrets and variables** → **Actions** → **New repository secret**.
2. Crea tres secretos con estos nombres exactos y pega en cada uno su clave:
   `YOUTUBE_API_KEY`, `AI_GATEWAY_API_KEY`, `GEMINI_API_KEY`.

### Paso 5 · Da permiso para guardar resultados

**Settings** → **Actions** → **General** → al final, en **Workflow permissions**, marca
**Read and write permissions** → **Save**.

### Paso 6 · Activa la web

**Settings** → **Pages** → en **Source** elige **Deploy from a branch** → Branch: **main** y carpeta
**/docs** → **Save**. En un par de minutos aparecerá arriba la dirección de tu web
(algo como `https://tuusuario.github.io/videos-uc3m/`). Guárdala en favoritos del móvil.

### Paso 7 · Primera ejecución a mano

1. Pestaña **Actions** → si pregunta, pulsa **I understand my workflows, go ahead and enable them**.
2. A la izquierda, **Buscador nocturno** → botón **Run workflow** → **Run workflow**.
3. Tarda entre 10 y 30 minutos. Cuando salga el círculo verde, abre tu web.
4. Si sale una cruz roja, entra en la ejecución, copia el texto del error y pásamelo.

A partir de aquí se ejecuta solo cada noche. No importa que tu portátil esté apagado.

---

## 2. Uso diario

- Abre tu web: arriba verás **Novedades de esta noche** y debajo todas las asignaturas.
- Cada vídeo tiene un botón **Copiar pregunta para Claude**: lo pulsas, abres Claude, pegas y
  completas tu duda. La pregunta ya incluye el vídeo, el tema y la asignatura.
- Al final de la página está el **informe** de la última noche (búsquedas, vídeos evaluados, errores).

### Lanzarlo a mano o solo para una asignatura

**Actions** → **Buscador nocturno** → **Run workflow** → escribe el nombre exacto de la asignatura
(por ejemplo `Termodinámica`) → **Run workflow**. Ojo: gasta búsquedas del cupo diario de YouTube.

---

## 3. Cómo cambiar cosas (sin programar)

Todos los ajustes están en `config.py`. Para editarlo: ábrelo en GitHub → icono del lápiz → cambia el
número → **Commit changes**.

| Quiero… | Qué cambiar en `config.py` |
| --- | --- |
| Más o menos peso para una asignatura | `PESOS_POR_PRIORIDAD` (deben sumar 1) |
| Más vídeos por tema en la web | `VIDEOS_POR_TEMA` |
| Ser más exigente con que el vídeo trate el tema | Subir `UMBRAL_CUBRE_TEMA` (p. ej. 0.8) |
| Aceptar vídeos más cortos o más largos | `DURACION_MIN_MINUTOS` / `DURACION_MAX_MINUTOS` |

**La hora** se cambia en `.github/workflows/nocturno.yml`, en la línea `cron: "30 2 * * *"`
(minuto y hora: `"0 3 * * *"` serían las 03:00).

**Activar un tema desactivado** (por ejemplo el tema 1 de Mecánica de máquinas): en
`temarios/mecanica_maquinas.json`, cambia `"activo": false` por `"activo": true`.

---

## 4. Qué hace cada parte

| Archivo | Qué hace |
| --- | --- |
| `temarios/*.json` | Los temas de cada asignatura y las palabras con las que se busca en YouTube |
| `config.py` | Todos los ajustes |
| `main.py` | El director: ejecuta las etapas en orden |
| `src/planificador.py` | Reparte las ~90 búsquedas de la noche entre asignaturas según tu orden de dificultad |
| `src/youtube_client.py` | Busca vídeos y pide sus datos a YouTube |
| `src/verificador.py` | Filtros gratis (duración, público, no bloqueado en España) y control de enlaces |
| `src/jev_client.py` | Pregunta a Jev: ¿trata el tema?, ¿qué nivel?, ¿cuánto rigor?, ¿qué formato?, ¿es publicidad? |
| `src/puntuacion.py` | Decide con las respuestas de Jev y calcula la nota |
| `src/gemini_client.py` | Escribe «por qué verlo» y «para quién» de los vídeos que entran en el top |
| `src/web.py` | Genera la web |
| `datos/` | La memoria entre noches (se crea sola): qué se ha buscado, qué se ha evaluado, qué se publica |
| `tests/` | 80 comprobaciones automáticas que se ejecutan cada noche antes de empezar |

### Cómo se evita publicar enlaces fantasma

1. Los enlaces **nunca los escribe una IA**: se construyen con el ID que devuelve la API oficial de YouTube.
2. **Control 1**: se piden los datos de cada vídeo a YouTube; si está borrado, privado o bloqueado en España, se descarta.
3. **Control 2**: justo antes de publicarlo, se comprueba otra vez que el vídeo responde.
4. **Cada lunes** se revisan todos los vídeos ya publicados y se retiran los que hayan desaparecido.

### Costes

| Servicio | Coste |
| --- | --- |
| GitHub Actions y Pages | Gratis (repositorio público) |
| YouTube Data API | Gratis (~100 búsquedas al día) |
| Jev vía Vercel | ~3 $/mes, dentro de los 5 $ gratis mensuales |
| Gemini Flash-Lite | Gratis (capa gratuita de AI Studio) |

---

## 5. Si algo falla

- Si una noche falla, GitHub te enviará un correo y la web mostrará el error al final.
- Copia el mensaje de error (sin ninguna clave) y pásamelo en el chat.
- Errores típicos:
  - `Faltan claves` → revisa el paso 4 (nombres exactos de los secretos).
  - `Jev (401)` → la clave de Vercel no es válida o ha caducado.
  - `YouTube: cuota diaria agotada` → no es un error; ya se ha gastado el cupo del día y seguirá mañana.
  - `Sin transcripción` en muchos vídeos → normal: YouTube bloquea a menudo a los servidores de GitHub.
    Los vídeos se evalúan igual, con título y descripción.

### Probarlo sin claves (opcional, necesita Python)

```
pip install -r requirements.txt
python main.py --simulado
```

Genera una web de ejemplo con datos inventados en `salida_simulada/docs/index.html`.
