# Horror Fear Score

Pipeline de datos para medir un **score de miedo** a partir de reseñas de películas de terror en inglés, y más adelante alimentar una pieza narrativa (sitio / scrollytelling).

Proyecto hermano de [anatomy-of-fear](https://github.com/juanpduque/anatomy-of-fear) (pósters / visión). Aquí la unidad de análisis es el **texto de reseña**, no la imagen.

## Universo

Películas de terror en **inglés**, definidas con metadata de **TMDB** (`original_language == en`), no con IMDb (idioma incompleto en `title.akas`).

Filtros base (reutilizan listas de Anatomy of Fear):

- género horror (catálogo TMDB)
- `original_language == en`
- fuera de exclusiones: animación, música, non-English

## Pipeline

```
enrich (universo + imdb_id) → fetch (reseñas) → analyze (emociones) → score → export
```

| Etapa | Script | Salida típica |
|-------|--------|----------------|
| Universo EN | `pipeline/build_universe.py` | `data/processed/universe_en.csv` |
| Cobertura | `pipeline/inventory_coverage.py` | `data/gaps/coverage_*.csv` |
| Fear score | `pipeline/compute_fear_score.py` | `data/exports/fear_scores.csv` |
| Export sitio | `pipeline/export_site.py` | (fase 2) |

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # ajusta rutas locales
```

Rutas externas esperadas (disco / máquina local):

- **AOF:** catálogo TMDB + `imdb_ids.csv` + exclusiones
- **IMDb scraper (legacy):** reseñas y emociones ya calculadas (opcional, para reuso)

## Principios

- Preferir APIs / datasets oficiales frente a HTML frágil.
- Gap CSVs como lista de trabajo durable.
- Join canónico: `imdb_id` (`tt…`) ↔ `id` TMDB.
- El sitio y la historia van en fase 2; este repo primero consolida datos y el score.
