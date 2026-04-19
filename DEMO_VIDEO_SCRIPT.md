# Scénář Demo Videa

Tento scénář je připravený pro **4-5 minutové video** a odpovídá tomu, co zadání požaduje:
- ukázka systému na reálném nebo simulovaném streamu
- komentovaný výstup v reálném čase
- krátký walk-through kódu

## Doporučené Nastavení

Na nahrávání doporučuju použít **lokální MP4 soubor**, i když systém umí i live URL. Pro demo je to spolehlivější, opakovatelné a lépe se to komentuje.

Doporučené rozložení:
- levé okno terminálu: běžící aplikace
- pravé okno terminálu nebo editoru: kód a artefakty (`README.md`, `src/app/main.py`, `src/app/llm/scorer.py`, `eval_report.md`)

Doporučené nastavení:
- `CHUNK_DURATION=10`
- `LLM_PROVIDER=openai`
- použít krátký vstupní soubor, kde jsou aspoň 2-3 zjevné komoditní signály

## Struktura Videa

### 0:00-0:20 Úvod

Ukaž root repozitáře a řekni:

> Tohle je Commodity Sentiment Monitor.  
> Cílem projektu je v reálném čase z audio streamu nebo nahrávky získat řeč, identifikovat komoditně relevantní témata a odhadnout pravděpodobný směr trhu včetně confidence.

Na obrazovce může být:
- root repozitáře
- `README.md`

### 0:20-0:45 Co Systém Dělá

Otevři `README.md` a krátce ukaž architekturu.

Řekni:

> Řešení je rozdělené do tří povinných vrstev ze zadání.  
> První je ingestion, tedy příjem live streamu nebo lokálního souboru a segmentace audia na chunky.  
> Druhá vrstva je STT plus NLP, kde používám Whisper s word-level timestampy a následné zpracování textu.  
> Třetí vrstva je scoring, kde se ke komoditě přiřadí direction, confidence, rationale a timeframe.

### 0:45-1:45 Live Ukázka

Ukaž příkaz, kterým to spustíš.

Pokud používáš Docker:

```bash
docker compose up
```

Pokud lokálně:

```bash
uv run python -m app.main
```

Jakmile běží dashboard, komentuj:

> Aplikace teď zpracovává audio po 10sekundových chuncích.  
> Každý chunk se nejdřív přepíše do textu pomocí Whisperu a potom jde do scoring vrstvy, která vrací strukturovaný výstup.  
> V terminálu je vidět čas, komodita, direction, confidence, extrahované entity a stručné vysvětlení, takže výstup je čitelný bez dalšího zpracování.

Jakmile se objeví konkrétní řádky, řekni třeba:

> Tady je vidět bullish signál pro gold s konkrétním confidence score.  
> Tady naopak model vrací neutral, protože transcript obsahuje smíšené nebo vzájemně se rušící informace a nechci vynucovat falešný directional signál.

### 1:45-2:20 Chování V Reálném Čase

Nech dashboard běžet a řekni:

> Pipeline je postavená asynchronně a jednotlivé vrstvy jsou oddělené frontami s omezenou kapacitou.  
> To znamená, že když scoring zpomalí, ingestion a STT se přirozeně přibrzdí přes backpressure místo toho, aby systém nekontrolovaně rostl v paměti.  
> U live vstupu je navíc řešený reconnect a restart při výpadku nebo stall situaci.

Pokud chceš zmínit diarizaci:

> Speaker segmentation je tady řešená jako lehká heuristika podle pauz ve word timestamp datech. V dokumentaci je to záměrně popsané poctivě jako proxy, ne jako plnohodnotná neural diarization.

### 2:20-3:00 Scoring A Strukturovaný Výstup

Otevři `src/app/llm/scorer.py` a `src/app/llm/prompts.py`.

Řekni:

> Ve scoring vrstvě používám structured tool calling, takže model nevrací volný text, ale přesně danou strukturu.  
> Každý signál obsahuje commodity, direction, confidence, rationale, timeframe, extrahované entity a také raw quote, tedy podpůrný úsek textu z transcriptu.

Pak doplň:

> Raw quote navíc kontroluju proti transcriptu, aby systém nebral jako validní důkaz něco, co si model vymyslí nebo příliš parafrázuje.

### 3:00-3:35 Krátký Walk-Through Kódu

Otevři `src/app/main.py`.

Řekni:

> Tady je vidět hlavní orchestrace celé pipeline.  
> Je tu ingestion worker, STT worker, LLM worker a dashboard.  
> Zvolil jsem spíš modulární composition přístup než těžkou objektovou hierarchii, protože pro tenhle scope je to jednodušší na testování, čitelnější a rychlejší na úpravy.

Rychle ukaž:
- `src/app/main.py`
- `src/app/stt/groq_whisper.py`
- `src/app/llm/scorer.py`
- `src/app/eval/run.py`

### 3:35-4:15 Evaluace

Otevři `eval_report.md`.

Řekni:

> Součástí odevzdání je i offline evaluační sada.  
> Tady mám připravené testovací případy a měřím nejen direction accuracy, ale i behavior accuracy a commodity accuracy zvlášť.  
> To je důležité, protože nestačí trefit bullish nebo bearish, ale i správně určit, jestli systém měl vrátit empty, neutral signal, nebo directional signal, a pro jakou komoditu.

Když je report vidět na obrazovce, ukaž:
- overall accuracy
- direction accuracy
- behavior accuracy
- commodity accuracy

Můžeš dodat:

> Aktuální eval sada je spíš sanity check benchmark než plnohodnotný produkční benchmark, ale pokrývá základní bullish, bearish, neutral a empty scénáře napříč více komoditami.

### 4:15-4:40 Co By Šlo Dál Zlepšit

Volitelně otevři `TECHNICAL_DOC.md`.

Řekni:

> V technickém dokumentu popisuju i další produkční rozšíření.  
> Největší přínos by podle mě měly overlapping chunky, lepší diarization, confidence calibration, monitoring a lehká retrieval vrstva pro kontext mezi sousedními chunky.

### 4:40-5:00 Závěr

Zakonči to například takto:

> Shrnutí je tedy takové, že řešení pokrývá všechny tři povinné vrstvy zadání, umí generovat čitelný real-time výstup, obsahuje offline evaluaci a dokumentuje i hlavní architektonická rozhodnutí a trade-offy.

## Bezpečnější Varianta, Pokud Nechceš Riskovat Live Problém

Jestli nechceš při natáčení riskovat síť nebo API problém, drž se tohoto postupu:

1. Připrav si krátký lokální MP4 vstup.
2. Měj předem vygenerovaný `eval_report.md`.
3. Natoč běžící dashboard nad lokálním souborem.
4. Potom plynule přepni do kódu a dokumentace.
5. Jen slovně zmiň, že stejná pipeline podporuje i live URL přes `yt-dlp` a `ffmpeg`.

## Krátký Checklist Před Natáčením

- `.env` je správně vyplněné
- vstupní MP4 je připravené
- terminál má dost velké písmo
- dashboard je dobře čitelný
- `eval_report.md` je aktuální
- na obrazovce nejsou API klíče ani shell historie se secrets
- video se vejde do 5 minut
