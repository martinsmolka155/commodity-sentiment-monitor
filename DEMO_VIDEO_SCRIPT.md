# Demo Video — Scénář (~3 min)

## Příprava

- `.env` vyplněné, MP4 v `fixtures/sample_stream.mp4`
- Zvětšit font terminálu, schovat API klíče z historie

## Natáčení

### 0:00–0:30 — Spuštění

```bash
uv run python -m app.main
```

Komentář: *"Commodity Sentiment Monitor — pipeline zpracovává audio, identifikuje komodity a scoruje dopad na ceny."*

### 0:30–1:30 — Dashboard se plní

Nech běžet, ukazuj signály jak přibývají. Komentuj co vidíš:

- *"Gold bullish, confidence 60% — zmíněn JP Morgan $6000 target"*
- *"Silver bearish — COMEX inventories klesají pod 100M oz"*
- *"Tady žádný signál — mluvili o akciích, ne komoditách"*

### 1:30–2:00 — Eval report

Otevři `eval_report.md`:

- *"10 testovacích případů, 100% accuracy, confusion matrix čistá"*

### 2:00–2:30 — Architektura

Ukaž `README.md` — Mermaid diagram. Zmíň tři vrstvy: Ingestion → STT → Scoring.

### 2:30–3:00 — Závěr

*"Celý projekt stál $0.32 na API, běží přes docker compose up, podporuje live i file mód."*

## Checklist

- [ ] Žádné API klíče na obrazovce
- [ ] Dashboard čitelný (velký font)
- [ ] Video pod 5 minut
