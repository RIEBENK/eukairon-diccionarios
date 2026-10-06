#!/usr/bin/env python3
"""
Genera los paquetes de diccionario de Eukairon a partir de los datos de
Wiktionary procesados por kaikki.org (wiktextract).

Por cada idioma pedido:
  1. Descarga el archivo de la edición de Wiktionary de ese idioma y lo lee de a
     poco, sin descomprimirlo entero (el inglés pesa 2,8 GB comprimido).
  2. Se queda solo con las palabras de ese mismo idioma (definición en el
     mismo idioma que la palabra).
  3. Guarda hasta 3 acepciones por palabra (definición + un ejemplo, si hay) y
     a qué palabra base corresponde cada forma conjugada o flexionada.
  4. Escribe un SQLite chico, lo comprime (<idioma>.db.gz) y actualiza index.json.

Uso:
  python build_dictionary.py --langs "es en" --out dist
  python build_dictionary.py --langs es --source-file prueba.jsonl.gz --out dist

Normalización de búsqueda (la app tiene que usar exactamente la misma):
  quitar espacios de los extremos y pasar a minúsculas con reglas neutras
  (Python str.lower() == Kotlin lowercase(Locale.ROOT)). No se quitan tildes:
  «papa» y «papá» son palabras distintas.

Los datos son de Wiktionary, bajo licencia CC BY-SA 4.0. Ver DATA_LICENSE.md.
"""

import argparse
import datetime
import gzip
import hashlib
import io
import json
import os
import re
import sqlite3
import sys
import urllib.request

# Idiomas de la app que tienen edición propia de Wiktionary en kaikki.org.
# (El hindi no tiene: la app muestra «no disponible en este idioma».)
EDITIONS = {
    "en": "https://kaikki.org/dictionary/raw-wiktextract-data.jsonl.gz",
}
for code in ["es", "pt", "de", "fr", "el", "it", "nl", "ja", "id", "tr", "pl"]:
    EDITIONS[code] = f"https://kaikki.org/{code}wiktionary/raw-wiktextract-data.jsonl.gz"

FORMAT_VERSION = 1
MAX_SENSES = 3
MAX_GLOSS = 300
MAX_EXAMPLE = 250
USER_AGENT = "EukaironDictionaryBuilder/1.0 (+https://github.com)"


def norm(word: str) -> str:
    return word.strip().lower()


def clip(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut + "…"


def open_source(lang: str, source_file: str | None):
    """Devuelve un flujo de texto línea por línea, sin descomprimir a disco."""
    if source_file:
        raw = open(source_file, "rb")
    else:
        url = EDITIONS[lang]
        print(f"[{lang}] descargando {url}", flush=True)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        raw = urllib.request.urlopen(req, timeout=120)
    return io.TextIOWrapper(gzip.GzipFile(fileobj=raw), encoding="utf-8")


def sense_is_form_of(sense: dict) -> bool:
    tags = sense.get("tags") or []
    return bool(sense.get("form_of")) or "form-of" in tags or "alt-of" in tags


def pick_gloss(sense: dict) -> str | None:
    glosses = [g for g in (sense.get("glosses") or []) if isinstance(g, str) and g.strip()]
    if not glosses:
        return None
    # Con subacepciones, la última es la más específica.
    return glosses[-1]


def pick_example(sense: dict) -> str | None:
    for ex in sense.get("examples") or []:
        text = ex.get("text") if isinstance(ex, dict) else ex
        if isinstance(text, str) and text.strip():
            return text
    return None


def build(lang: str, out_dir: str, source_file: str | None) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    db_path = os.path.join(out_dir, f"{lang}.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    db = sqlite3.connect(db_path)
    db.executescript(
        """
        PRAGMA journal_mode = OFF;
        PRAGMA synchronous = OFF;
        CREATE TABLE raw_senses (norm TEXT, word TEXT, seq INTEGER, gloss TEXT, example TEXT);
        CREATE TABLE raw_forms (form_norm TEXT, lemma_norm TEXT);
        """
    )

    # Filtro rápido antes de interpretar el JSON: casi todas las líneas de una
    # edición son de otros idiomas.
    lang_marker = re.compile(r'"lang_code"\s*:\s*"' + re.escape(lang) + r'"')

    seq = 0
    lines = 0
    kept = 0
    batch_s, batch_f = [], []
    with open_source(lang, source_file) as stream:
        for line in stream:
            lines += 1
            if lines % 500_000 == 0:
                print(f"[{lang}] {lines:,} líneas leídas, {kept:,} palabras", flush=True)
            if not lang_marker.search(line):
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("lang_code") != lang:
                continue
            word = entry.get("word")
            if not isinstance(word, str) or not word.strip():
                continue
            n = norm(word)
            senses = entry.get("senses") or []
            had_definition = False
            for sense in senses:
                if sense_is_form_of(sense):
                    for target in sense.get("form_of") or sense.get("alt_of") or []:
                        lemma = target.get("word") if isinstance(target, dict) else None
                        if lemma and norm(lemma) != n:
                            batch_f.append((n, norm(lemma)))
                    continue
                gloss = pick_gloss(sense)
                if not gloss:
                    continue
                example = pick_example(sense)
                seq += 1
                batch_s.append((n, word.strip(), seq, clip(gloss, MAX_GLOSS),
                                clip(example, MAX_EXAMPLE) if example else None))
                had_definition = True
            # Formas listadas en la propia palabra base (plurales, conjugaciones).
            if had_definition:
                for f in entry.get("forms") or []:
                    form = f.get("form") if isinstance(f, dict) else None
                    if isinstance(form, str) and form.strip() and " " not in form.strip():
                        fn = norm(form)
                        if fn != n:
                            batch_f.append((fn, n))
                kept += 1
            if len(batch_s) >= 50_000:
                db.executemany("INSERT INTO raw_senses VALUES (?,?,?,?,?)", batch_s)
                batch_s.clear()
            if len(batch_f) >= 50_000:
                db.executemany("INSERT INTO raw_forms VALUES (?,?)", batch_f)
                batch_f.clear()
    if batch_s:
        db.executemany("INSERT INTO raw_senses VALUES (?,?,?,?,?)", batch_s)
    if batch_f:
        db.executemany("INSERT INTO raw_forms VALUES (?,?)", batch_f)
    print(f"[{lang}] lectura terminada: {lines:,} líneas, {kept:,} palabras", flush=True)

    # Tablas finales, compactas:
    #   entries: una fila por palabra (norm única).
    #   senses: hasta MAX_SENSES por palabra, en el orden de Wiktionary.
    #   forms: forma flexionada -> palabra base (solo si la base existe y la
    #          forma no es ya una palabra con definición propia).
    db.executescript(
        f"""
        CREATE TABLE entries (id INTEGER PRIMARY KEY, norm TEXT NOT NULL UNIQUE, word TEXT NOT NULL);
        INSERT INTO entries (norm, word)
            SELECT norm, word FROM (
                SELECT norm, word, ROW_NUMBER() OVER (PARTITION BY norm ORDER BY seq) AS rn
                FROM raw_senses
            ) WHERE rn = 1;

        CREATE TABLE senses (entry_id INTEGER NOT NULL, ord INTEGER NOT NULL, gloss TEXT NOT NULL, example TEXT);
        INSERT INTO senses (entry_id, ord, gloss, example)
            SELECT e.id, r.rn, r.gloss, r.example FROM (
                SELECT norm, gloss, example,
                       ROW_NUMBER() OVER (PARTITION BY norm ORDER BY seq) AS rn
                FROM (SELECT norm, gloss, MIN(seq) AS seq, MAX(example) AS example
                      FROM raw_senses GROUP BY norm, gloss)
            ) r JOIN entries e ON e.norm = r.norm
            WHERE r.rn <= {MAX_SENSES};
        CREATE INDEX idx_senses_entry ON senses(entry_id, ord);

        CREATE TABLE forms (norm TEXT NOT NULL, entry_id INTEGER NOT NULL, PRIMARY KEY (norm, entry_id)) WITHOUT ROWID;
        INSERT OR IGNORE INTO forms (norm, entry_id)
            SELECT f.form_norm, e.id FROM raw_forms f
            JOIN entries e ON e.norm = f.lemma_norm
            WHERE f.form_norm NOT IN (SELECT norm FROM entries);

        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT) WITHOUT ROWID;

        DROP TABLE raw_senses;
        DROP TABLE raw_forms;
        """
    )
    entries = db.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
    forms = db.execute("SELECT COUNT(*) FROM forms").fetchone()[0]
    with_example = db.execute(
        "SELECT COUNT(DISTINCT entry_id) FROM senses WHERE example IS NOT NULL"
    ).fetchone()[0]
    built = datetime.datetime.now(datetime.timezone.utc)
    version = int(built.strftime("%Y%m%d%H%M"))
    meta = {
        "format": str(FORMAT_VERSION),
        "lang": lang,
        "version": str(version),
        "built": built.isoformat(timespec="seconds"),
        "source": "Wiktionary (vía kaikki.org / wiktextract)",
        "license": "CC BY-SA 4.0",
        "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
        "entries": str(entries),
        "forms": str(forms),
    }
    db.executemany("INSERT INTO meta VALUES (?,?)", meta.items())
    db.commit()
    db.execute("VACUUM")
    db.close()

    gz_path = db_path + ".gz"
    with open(db_path, "rb") as src, gzip.open(gz_path, "wb", compresslevel=9) as dst:
        while chunk := src.read(1 << 20):
            dst.write(chunk)
    sha = hashlib.sha256()
    with open(gz_path, "rb") as f:
        while chunk := f.read(1 << 20):
            sha.update(chunk)
    db_bytes = os.path.getsize(db_path)
    gz_bytes = os.path.getsize(gz_path)
    os.remove(db_path)

    info = {
        "file": f"{lang}.db.gz",
        "version": version,
        "built": meta["built"],
        "bytes": gz_bytes,
        "db_bytes": db_bytes,
        "sha256": sha.hexdigest(),
        "entries": entries,
        "forms": forms,
        "entries_with_example": with_example,
    }
    print(
        f"[{lang}] listo: {entries:,} palabras ({with_example:,} con ejemplo), {forms:,} formas · "
        f"{gz_bytes / 1e6:.1f} MB de descarga, {db_bytes / 1e6:.1f} MB instalado",
        flush=True,
    )
    return info


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--langs", required=True, help='Idiomas separados por espacios, ej.: "es en fr"')
    ap.add_argument("--out", default="dist")
    ap.add_argument("--index-in", default=None, help="index.json publicado antes (para conservar los otros idiomas)")
    ap.add_argument("--source-file", default=None, help="Solo para pruebas: archivo .jsonl.gz local")
    args = ap.parse_args()

    langs = [l.strip().lower() for l in re.split(r"[\s,]+", args.langs) if l.strip()]
    unknown = [l for l in langs if l not in EDITIONS]
    if not langs or unknown:
        print(f"Idiomas no válidos: {unknown or '(ninguno)'}. Disponibles: {' '.join(sorted(EDITIONS))}")
        return 2
    if args.source_file and len(langs) != 1:
        print("--source-file sirve para un solo idioma")
        return 2

    index = {"format": FORMAT_VERSION, "languages": {}}
    if args.index_in and os.path.exists(args.index_in):
        try:
            with open(args.index_in, encoding="utf-8") as f:
                old = json.load(f)
            if old.get("format") == FORMAT_VERSION:
                index["languages"] = old.get("languages", {})
        except (OSError, json.JSONDecodeError):
            pass

    for lang in langs:
        index["languages"][lang] = build(lang, args.out, args.source_file)

    index["updated"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    index["source"] = "Wiktionary (vía kaikki.org / wiktextract)"
    index["license"] = "CC BY-SA 4.0"
    index["license_url"] = "https://creativecommons.org/licenses/by-sa/4.0/"
    with open(os.path.join(args.out, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2, sort_keys=True)
    print("index.json actualizado")
    return 0


if __name__ == "__main__":
    sys.exit(main())
