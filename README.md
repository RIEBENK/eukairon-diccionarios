# Diccionarios de Eukairon

Paquetes de diccionario por idioma para la app Eukairon. Se generan acá, en GitHub, apretando un botón, y quedan publicados en **Releases**, desde donde la app los descarga.

Los datos son de [Wiktionary](https://www.wiktionary.org/) (licencia CC BY-SA 4.0), procesados con [wiktextract / kaikki.org](https://kaikki.org/). Ver `DATA_LICENSE.md`.

---

## Instructivo de instalación (se hace una sola vez)

No hace falta instalar nada en la computadora: todo se hace desde la página de GitHub.

### 1. Crear la cuenta
1. Entrá a <https://github.com> y tocá **Sign up**.
2. Poné tu mail, una contraseña y un nombre de usuario. **El nombre de usuario va a quedar en la dirección de descarga que usa la app**: elegí uno que no vayas a cambiar.
3. Confirmá el mail. GitHub puede pedirte activar la verificación en dos pasos (con una app del celular); seguí sus pasos.

### 2. Crear el repositorio
1. Arriba a la derecha tocá **+** → **New repository**.
2. **Repository name**: `eukairon-diccionarios`.
3. Marcá **Public**.
4. Tildá **Add a README file**.
5. Tocá **Create repository**.

### 3. Subir los archivos
1. Dentro del repositorio tocá **Add file** → **Upload files**.
2. Arrastrá estos tres archivos: `build_dictionary.py`, `README.md` y `DATA_LICENSE.md` (el README reemplaza al que creó GitHub; está bien).
3. Abajo tocá **Commit changes**.

### 4. Crear la tarea
La carpeta `.github` suele estar oculta en la computadora, por eso esta parte se crea a mano:
1. Tocá **Add file** → **Create new file**.
2. En el nombre escribí exactamente: `.github/workflows/build.yml` (al escribir las barras, GitHub crea las carpetas solo).
3. Abrí el archivo `build.yml` que te pasaron con el Bloc de notas, copiá **todo** el contenido y pegalo en el recuadro grande.
4. Tocá **Commit changes** (arriba a la derecha) y confirmá.

### 5. Darle permiso para publicar
1. En el repositorio, tocá **Settings** (arriba, el engranaje).
2. En el menú de la izquierda: **Actions** → **General**.
3. Bajá hasta **Workflow permissions**, elegí **Read and write permissions** y tocá **Save**.

Listo: la instalación terminó.

---

## Generar diccionarios (cada vez que quieras)

1. Abrí la pestaña **Actions**. La primera vez puede pedirte confirmar que querés usar Actions: aceptá.
2. A la izquierda elegí **Generar diccionarios**.
3. A la derecha tocá **Run workflow**. Aparece un campo **Idiomas a generar**:
   - Para probar: dejá `es`.
   - Para todos: `es en pt de fr el it nl ja id tr pl`
   - Para rehacer solo uno: por ejemplo `en`.
4. Tocá el botón verde **Run workflow**.
5. Esperá. El español tarda unos minutos; el inglés, bastante más (puede pasar una hora). Podés cerrar la página: sigue solo.
6. Cuando termina:
   - **Tilde verde**: salió bien. Al abrir la ejecución vas a ver una tabla con la cantidad de palabras y el tamaño de cada diccionario.
   - **Cruz roja**: algo falló. Abrí la ejecución, tocá el paso en rojo, copiá el texto y pasáselo a quien mantiene el script. Los diccionarios publicados antes siguen funcionando.

### Dónde quedan los archivos
En la página principal del repositorio, a la derecha, **Releases** → **Diccionarios de Eukairon**. Hay un archivo por idioma (`es.db.gz`, `en.db.gz`, …) y un `index.json` con la versión y el tamaño de cada uno. Cuando generás un idioma de nuevo, su archivo se reemplaza y los demás quedan como estaban.

La app descarga desde:

```
https://github.com/<tu-usuario>/eukairon-diccionarios/releases/download/diccionarios/index.json
https://github.com/<tu-usuario>/eukairon-diccionarios/releases/download/diccionarios/es.db.gz
```

---

## ¿Cada cuánto actualizar?

No hace falta seguido: un diccionario cambia muy poco. Una o dos veces por año alcanza, o cuando se mejore el script. La tarea nunca corre sola, solo cuando apretás **Run workflow**.

## Idiomas disponibles

`es` español · `en` inglés · `pt` portugués · `de` alemán · `fr` francés · `el` griego · `it` italiano · `nl` neerlandés · `ja` japonés · `id` indonesio · `tr` turco · `pl` polaco.

El hindi no tiene edición propia de Wiktionary procesada, así que no hay paquete (la app muestra «no disponible en este idioma»).

---

## Detalles técnicos (para quien mantenga el script)

- El script lee la edición de Wiktionary del idioma (`kaikki.org/<idioma>wiktionary/raw-wiktextract-data.jsonl.gz`; el inglés en `kaikki.org/dictionary/…`) de a poco, sin descomprimirla a disco, y se queda con las palabras de ese mismo idioma.
- Paquete SQLite:
  - `entries(id, norm, word)`: una fila por palabra; `norm` = palabra sin espacios en los extremos y en minúsculas neutras (Python `str.lower()` = Kotlin `lowercase(Locale.ROOT)`), sin quitar tildes.
  - `senses(entry_id, ord, gloss, example)`: hasta 3 acepciones por palabra; `example` puede ser nulo.
  - `forms(norm, entry_id)`: forma flexionada → palabra base (`corrió` → `correr`, `casas` → `casa`).
  - `meta(key, value)`: versión, idioma, fuente y licencia.
- Búsqueda en la app: `entries.norm = ?`; si no hay, `forms.norm = ?` → `entries`.
- Prueba local con datos propios: `python build_dictionary.py --langs es --source-file prueba.jsonl.gz --out dist`.
