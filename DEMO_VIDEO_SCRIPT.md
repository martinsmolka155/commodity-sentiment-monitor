# Demo Video — Scénář (~4 min)

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

### 1:30–2:30 — Walk-through kódu

Otevři v editoru a ukaž klíčové soubory:

1. **`src/app/main.py`** — *"Hlavní orchestrace — tři async workery propojené frontami: ingestion, STT, LLM scorer."*
2. **`src/app/llm/prompts.py`** — *"System prompt definuje 8 komodit, kalibraci confidence, pravidla pro entity extraction."*
3. **`src/app/llm/scorer.py`** — *"Structured tool calling — model musí vrátit přesnou JSON strukturu, žádné parsování volného textu."*
4. **`src/app/eval/run.py`** — *"Eval harness — měří direction, behavior i commodity accuracy, generuje confusion matrix."*

### 2:30–3:15 — Eval report

Otevři `eval_report.md`:

- *"10 testovacích případů, 100% accuracy, confusion matrix čistá"*
- *"Tabulka extrahovaných entit — osoby, indikátory, organizace"*
- *"Error analysis popisuje 5 očekávaných failure modes v produkci"*

### 3:15–3:45 — Architektura

Ukaž `README.md` — Mermaid diagram. Zmíň tři vrstvy: Ingestion → STT → Scoring.

### 3:45–4:00 — Závěr

*"Celý projekt stál $0.32 na API, běží přes docker compose up, podporuje live i file mód."*

## Checklist

- [ ] Žádné API klíče na obrazovce
- [ ] Dashboard čitelný (velký font)
- [ ] Video pod 5 minut
