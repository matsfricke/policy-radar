#!/usr/bin/env python3
"""
Policy Scanning Routine – automatisierter Tageslauf.

Setzt den "30-Minuten-Wochenworkflow" von Svea Fricke (TÜV NORD) automatisch um.
Pro Thema werden alle Workflow-Schritte kombiniert (Was ist neu? · Bewertung ·
PR-Winkel), damit auf der Website ohne Scrollen sichtbar ist, was relevant ist.

Ablauf:
  1. Scannen    – z.ai Web-Search je Quelle (auf Domain gefiltert)
  2. Auswerten  – GLM-5.2 liefert je Thema Bewertung + PR-Winkel als JSON
  3. Rendern    – themen-zentrierte Website (render.py), inkl. Radar-Chart
  4. Kosten     – Token-/Suchverbrauch schätzen und kumuliert mitschreiben

Kein Schlüssel im Code: GLM_API_KEY kommt aus der Umgebung.
"""

from __future__ import annotations

import json
import os
import sys
import time
import datetime as dt
from pathlib import Path
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError

# --------------------------------------------------------------------------- #
# Konfiguration
# --------------------------------------------------------------------------- #

API_BASE = os.environ.get("GLM_API_BASE", "https://api.z.ai/api/paas/v4")
CHAT_URL = f"{API_BASE}/chat/completions"
SEARCH_URL = f"{API_BASE}/web_search"

MODEL = os.environ.get("GLM_MODEL", "glm-5.2")
API_KEY = os.environ.get("GLM_API_KEY", "").strip()

RECENCY = os.environ.get("SEARCH_RECENCY", "oneWeek")
RESULTS_PER_SOURCE = int(os.environ.get("RESULTS_PER_SOURCE", "6"))

OUT_DIR = Path(os.environ.get("OUT_DIR", "docs"))

# Preise (USD, z.ai Listenpreise GLM-5.2) für die Verbrauchsschätzung.
PRICE_IN = float(os.environ.get("GLM_PRICE_IN", "1.40")) / 1_000_000    # pro Input-Token
PRICE_OUT = float(os.environ.get("GLM_PRICE_OUT", "4.40")) / 1_000_000  # pro Output-Token
SEARCH_COST = float(os.environ.get("SEARCH_COST", "0.01"))             # pro Web-Suche (Schätzwert)
START_BALANCE = float(os.environ.get("START_BALANCE", "10"))          # Startguthaben
CURRENCY = os.environ.get("CURRENCY", "€")

# Quellen aus dem Workflow-Dokument: label · Domain-Filter · Bereich.
SOURCES = [
    {"label": "EU-Kommission (Presscorner)", "domain": "ec.europa.eu",       "bereich": "Policy / Gesetzesinitiativen"},
    {"label": "OECD",                        "domain": "oecd.org",           "bereich": "Strategische Trends"},
    {"label": "ISO",                         "domain": "iso.org",            "bereich": "Normen / Zertifizierung"},
    {"label": "EFSA",                        "domain": "efsa.europa.eu",     "bereich": "Food / Lebensmittelsicherheit"},
    {"label": "EU Medizinprodukte (DG Health)","domain": "health.ec.europa.eu","bereich": "MedTech (MDR/IVDR)"},
    {"label": "EFRAG",                       "domain": "efrag.org",          "bereich": "ESG / CSRD"},
    {"label": "ENISA",                       "domain": "enisa.europa.eu",    "bereich": "KRITIS / Cyber (NIS2)"},
    {"label": "BSI",                         "domain": "bsi.bund.de",        "bereich": "KRITIS / Cyber (national)"},
    {"label": "Bruegel",                     "domain": "bruegel.org",        "bereich": "EU Think Tank"},
    {"label": "McKinsey Insights",           "domain": "mckinsey.com",       "bereich": "Industrienahe Analyse"},
]

SEARCH_QUERY = os.environ.get(
    "SEARCH_QUERY",
    "neue Leitlinien Draft Positionspapier Standard Regulierung Konsultation "
    "Zertifizierung ESG Nachhaltigkeit MedTech Lebensmittel Cybersicherheit KRITIS",
)

RELEVANTE_BEREICHE = "Zertifizierung, ESG/Nachhaltigkeit, MedTech, Food, KRITIS/Infrastruktur/Cybersicherheit"


# --------------------------------------------------------------------------- #
# HTTP-Helfer (nur Standardbibliothek)
# --------------------------------------------------------------------------- #

def _post_json(url: str, payload: dict, timeout: int = 120) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urlrequest.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {API_KEY}")
    with urlrequest.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _post_with_retry(url: str, payload: dict, timeout: int = 120, tries: int = 3) -> dict:
    last_err = None
    for attempt in range(1, tries + 1):
        try:
            return _post_json(url, payload, timeout=timeout)
        except HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:500]
            last_err = f"HTTP {e.code}: {body}"
            if e.code != 429 and 400 <= e.code < 500:
                break
        except URLError as e:
            last_err = f"URLError: {e.reason}"
        time.sleep(2 * attempt)
    raise RuntimeError(f"Request an {url} fehlgeschlagen: {last_err}")


# --------------------------------------------------------------------------- #
# Schritt 1 – Scannen
# --------------------------------------------------------------------------- #

def scan_source(source: dict) -> tuple[list[dict], bool]:
    payload = {
        "search_engine": "search-prime",
        "search_query": SEARCH_QUERY,
        "count": RESULTS_PER_SOURCE,
        "search_recency_filter": RECENCY,
        "search_domain_filter": source["domain"],
    }
    try:
        res = _post_with_retry(SEARCH_URL, payload, timeout=60)
    except RuntimeError as e:
        print(f"  ! {source['label']}: Suche fehlgeschlagen – {e}", file=sys.stderr)
        return [], False

    items = []
    for r in res.get("search_result", []) or []:
        items.append({
            "source": source["label"],
            "bereich": source["bereich"],
            "title": (r.get("title") or "").strip(),
            "content": (r.get("content") or "").strip()[:600],
            "url": (r.get("link") or "").strip(),
            "date": (r.get("publish_date") or "").strip(),
        })
    print(f"  · {source['label']}: {len(items)} Treffer")
    return items, True


def run_scan() -> tuple[list[dict], int]:
    print("Schritt 1 – Scannen:")
    all_items: list[dict] = []
    seen: set[str] = set()
    searches = 0
    for source in SOURCES:
        items, ok = scan_source(source)
        if ok:
            searches += 1
        for item in items:
            key = item["url"] or item["title"]
            if key and key not in seen:
                seen.add(key)
                all_items.append(item)
    print(f"  → {len(all_items)} eindeutige Fundstellen aus {searches} Suchen\n")
    return all_items, searches


# --------------------------------------------------------------------------- #
# Schritt 2 – Auswerten (GLM-5.2): pro Thema Bewertung + PR-Winkel kombiniert
# --------------------------------------------------------------------------- #

SYSTEM_PROMPT = (
    "Du bist Rechercheassistenz für die Pressesprecherin von TÜV NORD. "
    "Du hilfst, aus Wirtschafts- und Politikthemen PR-Chancen zu erkennen und "
    "Pressetexte im nüchtern-sachlichen Stil von TÜV-NORD-Pressemitteilungen "
    "vorzubereiten. Du antwortest ausschließlich mit gültigem JSON, ohne "
    "Markdown-Codeblöcke und ohne Text davor oder danach."
)

USER_PROMPT_TEMPLATE = """\
Hier sind die heute gefundenen Fundstellen aus den Policy-Quellen (JSON):

{funde}

Wähle die relevantesten NEUEN Themen (neue Leitlinien, Drafts, Positionspapiere,
Normen-Updates, politisch hochgezogene Themen) für TÜV-NORD-Kunden aus – maximal 8.
Erfinde nichts; wenn nichts wirklich relevant ist, gib ein leeres Array zurück.

Relevante Bereiche: {bereiche}.

Erzeuge für JEDES ausgewählte Thema EINEN kombinierten Eintrag, der Fund, Bewertung
und PR-Winkel zusammenführt (Erfolgsformel: Entwicklung → Auswirkung → Handlung →
TÜV NORD Lösung). Bei Relevanz "hoch" oder "sehr hoch" schlägst du zusätzlich eine
starke Presse-Überschrift vor (konkret, im "Was jetzt zu tun ist"-Stil, kein
"EU arbeitet an ..."). Bei "mittel"/"niedrig" lässt du "vorschlag_ueberschrift" leer.

Die vier Erfolgsformel-Felder (was_aendert_sich, wer_betroffen, was_tun,
wo_tuev_nord_hilft) sind JEWEILS eine Liste aus 2–4 kurzen, konkreten Stichpunkten
(je 1 knapper Satz) – nur das, was für dieses Thema wirklich relevant ist.

Sortiere die Themen absteigend nach Relevanz (sehr hoch zuerst).

Antworte GENAU in diesem JSON-Schema:
{{
  "hinweis": "kurzer Statushinweis, z.B. 'X relevante Themen, davon Y mit hoher Relevanz'",
  "themen": [
    {{
      "titel": "faktische Kurz-Headline der Fundstelle",
      "source": "Quellenname",
      "date": "Datum wie gefunden",
      "url": "Link zur Quelle",
      "bereich": "einer von: Zertifizierung | ESG | MedTech | Food | KRITIS | Sonstiges",
      "relevanz": "einer von: sehr hoch | hoch | mittel | niedrig",
      "relevanz_begruendung": "1 Satz: warum es TÜV-NORD-Kunden konkret betrifft",
      "timing_bucket": "einer von: jetzt | 6-12 Monate | 1-3 Jahre | >3 Jahre",
      "timing_text": "1 kurzer Satz zur zeitlichen Einordnung",
      "pr_potenzial": "einer von: hoch | mittel | niedrig",
      "zusammenfassung": "ca. 4 Sätze: worum geht es konkret, was genau ist neu/der Inhalt der Meldung, welcher Kontext, warum ist das gerade jetzt ein Thema",
      "vorschlag_ueberschrift": "starke Presse-Überschrift (nur bei hoch/sehr hoch, sonst leerer String)",
      "kernaussage": "eine prägnante Kernaussage",
      "was_aendert_sich": ["Stichpunkt", "Stichpunkt", "..."],
      "wer_betroffen": ["Stichpunkt", "..."],
      "was_tun": ["Stichpunkt", "..."],
      "wo_tuev_nord_hilft": ["Stichpunkt", "..."]
    }}
  ]
}}
"""


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.lstrip().startswith("json"):
            text = text.lstrip()[4:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"Keine JSON-Struktur in der Antwort:\n{text[:500]}")
    return json.loads(text[start:end + 1])


def evaluate(items: list[dict]) -> tuple[dict, dict]:
    """Gibt (data, usage) zurück; usage = Token-Verbrauch der Auswertung."""
    print("Schritt 2 – Auswerten (GLM-5.2):")
    funde = json.dumps(items, ensure_ascii=False, indent=2)
    user_prompt = USER_PROMPT_TEMPLATE.format(funde=funde, bereiche=RELEVANTE_BEREICHE)
    payload = {
        "model": MODEL,
        "temperature": 0.3,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
    }
    res = _post_with_retry(CHAT_URL, payload, timeout=180)
    content = res["choices"][0]["message"]["content"]
    data = _extract_json(content)
    usage = res.get("usage", {}) or {}
    print(f"  → {len(data.get('themen', []))} Themen ausgewertet "
          f"(Tokens: {usage.get('prompt_tokens','?')} in / {usage.get('completion_tokens','?')} out)\n")
    return data, usage


# --------------------------------------------------------------------------- #
# Kosten-/Guthaben-Tracking
# --------------------------------------------------------------------------- #

def update_spend(usage: dict, searches: int) -> dict:
    """Kumulierten Verbrauch schätzen und in docs/spend.json fortschreiben."""
    spend_file = OUT_DIR / "spend.json"
    prev = {"spent_usd": 0.0, "runs": 0}
    if spend_file.exists():
        try:
            prev = json.loads(spend_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    in_tok = usage.get("prompt_tokens", 0) or 0
    out_tok = usage.get("completion_tokens", 0) or 0
    run_cost = in_tok * PRICE_IN + out_tok * PRICE_OUT + searches * SEARCH_COST

    spent = round(float(prev.get("spent_usd", 0.0)) + run_cost, 4)
    state = {
        "spent_usd": spent,
        "runs": int(prev.get("runs", 0)) + 1,
        "start_balance": START_BALANCE,
        "currency": CURRENCY,
        "remaining": round(START_BALANCE - spent, 4),
        "last_run_usd": round(run_cost, 4),
        "updated": dt.datetime.now(dt.timezone.utc).isoformat(),
        "note": "Geschätzt aus Token-/Suchverbrauch (z.ai bietet keinen Guthaben-Endpoint).",
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    spend_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Verbrauch dieser Lauf: ~${run_cost:.4f} · kumuliert: ~${spent:.2f} "
          f"· Rest (geschätzt): ~{CURRENCY}{state['remaining']:.2f}\n")
    return state


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main() -> int:
    if not API_KEY:
        print("FEHLER: Umgebungsvariable GLM_API_KEY ist nicht gesetzt.", file=sys.stderr)
        return 2

    now = dt.datetime.now(dt.timezone.utc)
    items, searches = run_scan()

    usage = {}
    if not items:
        data = {"hinweis": "Keine Fundstellen aus den Quellen erhalten (Suche leer oder fehlgeschlagen).",
                "themen": []}
    else:
        try:
            data, usage = evaluate(items)
        except Exception as e:
            print(f"FEHLER bei der Auswertung: {e}", file=sys.stderr)
            return 1

    spend = update_spend(usage, searches)

    from render import build_report
    html = build_report(data, now, spend)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "index.html").write_text(html, encoding="utf-8")

    archive_dir = OUT_DIR / "archiv"
    archive_dir.mkdir(exist_ok=True)
    (archive_dir / f"{now:%Y-%m-%d}.html").write_text(html, encoding="utf-8")

    (OUT_DIR / "latest.json").write_text(
        json.dumps({"generated_at": now.isoformat(), **data}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Fertig. Geschrieben: {OUT_DIR/'index.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
