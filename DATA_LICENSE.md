# Licencia de los datos

Los diccionarios publicados en este repositorio (`*.db.gz`) contienen definiciones y ejemplos extraídos de **Wiktionary**, obra colectiva de sus colaboradores, distribuida bajo la licencia **Creative Commons Atribución-CompartirIgual 4.0 Internacional (CC BY-SA 4.0)**:
https://creativecommons.org/licenses/by-sa/4.0/deed.es

- Fuente: Wiktionary — https://www.wiktionary.org/
- Extracción: wiktextract / kaikki.org — Tatu Ylonen, «Wiktextract: Wiktionary as Machine-Readable Structured Data», LREC 2022.
- Cambios realizados: se conservaron solo las palabras del idioma de cada edición, hasta 3 acepciones por palabra con un ejemplo, y la relación entre formas flexionadas y su palabra base; los textos largos se recortaron.

Los paquetes se distribuyen bajo la misma licencia CC BY-SA 4.0. La app que los usa muestra la atribución «Fuente: Wiktionary (CC BY-SA 4.0)» junto a cada resultado.

El código del script (`build_dictionary.py`) y de la tarea (`.github/workflows/build.yml`) puede usarse libremente.
