# Demo Video — Scénář (~4 min)

## Příprava

- `.env` vyplněné, MP4 v `fixtures/sample_stream.mp4`
- Zvětšit font terminálu, schovat API klíče z historie
- Mít otevřený editor s kódem vedle terminálu
- Předem pustit `uv run python -m app.main` ať dashboard už má pár signálů

## Natáčení

### 0:00–0:30 — Co to je + architektura

Ukaž README.md s Mermaid diagramem. Body k zmínění:
- Pipeline má 3 vrstvy: ingestion (ffmpeg/yt-dlp), STT (Groq Whisper), scoring (GPT-5-mini)
- Podporuje live YouTube streamy i lokální soubory
- Výstup je Rich terminálový dashboard

### 0:30–1:30 — Běžící dashboard

Přepni na terminál kde běží pipeline. Body k zmínění:
- Signály přibývají v reálném čase
- Ukaž na konkrétní řádek — jaká komodita, jaký směr, proč (rationale)
- Zmíň že chunky bez commodity obsahu správně vracejí 0 signálů
- Dole status bar ukazuje latence a počet zpracovaných chunků

### 1:30–2:30 — Kód (4 soubory, stručně)

1. **`main.py`** — 3 async workery + dashboard, propojené asyncio frontami
2. **`prompts.py`** — system prompt s 8 komoditami, confidence kalibrací, entity extraction pravidly
3. **`scorer.py`** — structured tool calling, model vrací JSON, ne volný text
4. **`eval/run.py`** — offline evaluace, měří accuracy + generuje confusion matrix

### 2:30–3:30 — Evaluace

Otevři `eval_report.md`. Body k zmínění:
- 10 případů, 100% overall accuracy
- Confusion matrix — žádné záměny bullish/bearish/neutral
- Extrahované entity — osoby (Powell), organizace (OPEC+, Fed), indikátory
- Error analysis — 5 konkrétních failure modes pro produkci

### 3:30–4:00 — Závěr

- Celkové API náklady: ~$0.32
- Spustitelné přes `docker compose up`
- Podporuje live i file mód, 3 LLM providery (OpenAI, Groq, Anthropic)
- Všechny bonusy: diarization, backtesting, Slack webhook, multi-jazyk

## Checklist před natáčením

- [ ] Pipeline běží a má signály v dashboardu
- [ ] Žádné API klíče na obrazovce ani v shell historii
- [ ] Font terminálu dostatečně velký
- [ ] `eval_report.md` je aktuální
- [ ] Video se vejde do 5 minut
