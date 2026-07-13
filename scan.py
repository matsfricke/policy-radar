#!/usr/bin/env python3
"""
Policy Scanning Routine – automatisierter Tageslauf.

Setzt den "30-Minuten-Wochenworkflow" (Policy Scanning) für die TÜV-NORD-
Pressearbeit automatisch um.
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

# oneMonth statt oneWeek: der Zeitfilter wird von der Such-API nur lose beachtet;
# ein größeres Fenster liefert mehr relevantes Material, GLM sortiert Altes aus.
RECENCY = os.environ.get("SEARCH_RECENCY", "oneMonth")
RESULTS_PER_SOURCE = int(os.environ.get("RESULTS_PER_SOURCE", "8"))
YEAR = dt.datetime.now().year

OUT_DIR = Path(os.environ.get("OUT_DIR", "docs"))

# Quellen: label · Domain · Bereich · q (gezielte Suchbegriffe für diese Quelle).
# Wichtig: Die Suche wird als `site:<domain> <q> <jahr>` gestellt – der site:-Operator
# scopt zuverlässig auf die Quelle (der reine search_domain_filter tut das nicht).
SOURCES = [
    {"label": "EU-Kommission (Presscorner)", "domain": "ec.europa.eu",        "bereich": "Policy / Gesetzesinitiativen",
     "q": "new regulation OR directive OR guidelines OR strategy policy"},
    {"label": "OECD",                        "domain": "oecd.org",            "bereich": "Strategische Trends",
     "q": "new report OR policy OR recommendation OR outlook"},
    {"label": "ISO",                         "domain": "iso.org",             "bereich": "Normen / Zertifizierung",
     "q": "new standard OR consultation OR revision news"},
    {"label": "EFSA",                        "domain": "efsa.europa.eu",      "bereich": "Food / Lebensmittelsicherheit",
     "q": "scientific opinion OR guidance OR safety assessment news"},
    {"label": "EU Medizinprodukte (DG Health)","domain": "health.ec.europa.eu","bereich": "MedTech (MDR/IVDR)",
     "q": "medical devices MDR OR IVDR OR MDCG guidance"},
    {"label": "EFRAG",                       "domain": "efrag.org",           "bereich": "ESG / CSRD",
     "q": "ESRS OR sustainability reporting OR CSRD OR VSME"},
    {"label": "ENISA",                       "domain": "enisa.europa.eu",     "bereich": "KRITIS / Cyber (NIS2)",
     "q": "NIS2 OR cybersecurity OR guidelines OR report"},
    {"label": "BSI",                         "domain": "bsi.bund.de",         "bereich": "KRITIS / Cyber (national)",
     "q": "Sicherheit OR Richtlinie OR KRITIS OR Warnung Pressemitteilung"},
    {"label": "Bruegel",                     "domain": "bruegel.org",         "bereich": "EU Think Tank",
     "q": "policy analysis OR regulation OR economy"},
    {"label": "McKinsey Insights",           "domain": "mckinsey.com",        "bereich": "Industrienahe Analyse",
     "q": "regulation OR ESG OR sustainability OR compliance insights"},
]

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
        except (URLError, TimeoutError, OSError) as e:
            # Timeout, Verbindungsabbruch, DNS etc. – erneut versuchen
            last_err = f"{type(e).__name__}: {e}"
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
        time.sleep(2 * attempt)
    raise RuntimeError(f"Request an {url} fehlgeschlagen: {last_err}")


# --------------------------------------------------------------------------- #
# Schritt 1 – Scannen
# --------------------------------------------------------------------------- #

def scan_source(source: dict) -> tuple[list[dict], bool]:
    # site:-Operator scopt zuverlässig auf die Quelle; Jahr hält die Treffer aktuell.
    query = f"site:{source['domain']} {source['q']} {YEAR}"
    payload = {
        "search_engine": "search-prime",
        "search_query": query,
        "count": RESULTS_PER_SOURCE,
        "search_recency_filter": RECENCY,
        "search_domain_filter": source["domain"],
    }
    try:
        res = _post_with_retry(SEARCH_URL, payload, timeout=90)
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

DIAGRAMM (optional, pro Thema): Wenn zu dem Thema konkrete, belastbare Zahlen
vorliegen (z.B. Grenzwerte, Fristen, Marktgrößen, Betroffenenzahlen, Fördersummen,
Prozentwerte, Zeitreihen), dann liefere ein "chart"-Objekt, das diese Statistik
sinnvoll visualisiert. NUR echte, aus dem Quellmaterial/Kontext begründbare Werte –
ERFINDE KEINE ZAHLEN. Wenn es keine sinnvollen Zahlen gibt, setze "chart": null.
Mindestens 2 Datenpunkte, sonst null.

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
      "wo_tuev_nord_hilft": ["Stichpunkt", "..."],
      "chart": {{
        "type": "bar",
        "title": "Aussagekräftiger Diagrammtitel",
        "unit": "Einheit, z.B. % oder Mrd. €",
        "data": [{{"label": "Kategorie/Jahr", "value": 12.3}}, {{"label": "...", "value": 45.6}}],
        "quelle": "woher die Zahlen stammen"
      }}
    }}
  ]
}}

Hinweis: "chart" ist optional – setze es auf null, wenn keine echten Zahlen vorliegen.
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


def evaluate(items: list[dict]) -> dict:
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
    print(f"  → {len(data.get('themen', []))} Themen ausgewertet\n")
    return data


# --------------------------------------------------------------------------- #
# Schritt 3 – Pressemitteilung je Thema (GLM-5.2 schreibt sie vor)
# --------------------------------------------------------------------------- #

PM_SYSTEM = ("Du bist Presseredakteur der TÜV NORD GROUP und schreibst "
             "professionelle, sachliche Pressemitteilungen.")


def _bullets_text(v) -> str:
    if isinstance(v, (list, tuple)):
        return "\n".join(f"- {x}" for x in v if str(x).strip())
    return str(v or "")


def _pm_prompt(t: dict) -> str:
    return f"""Schreibe eine vollständige, veröffentlichungsfähige Pressemitteilung im
nüchtern-sachlichen Stil der TÜV NORD GROUP zu folgendem Thema.

Thema: {t.get('titel','')}
Bereich: {t.get('bereich','')}
Quelle: {t.get('source','')} ({t.get('date','')}) {t.get('url','')}
Vorgeschlagene Überschrift: {t.get('vorschlag_ueberschrift') or '(frei wählen)'}

Hintergrund:
{t.get('zusammenfassung','')}

Was ändert sich:
{_bullets_text(t.get('was_aendert_sich'))}

Wer ist betroffen:
{_bullets_text(t.get('wer_betroffen'))}

Was sollten Unternehmen jetzt tun:
{_bullets_text(t.get('was_tun'))}

Wie kann TÜV NORD helfen:
{_bullets_text(t.get('wo_tuev_nord_hilft'))}

Vorgaben: prägnante Überschrift, optional Unterzeile, dann Fließtext-Absätze;
erster Absatz beantwortet Wer/Was/Wann/Warum; ein sachliches Zitat einer
TÜV-NORD-Sprecherin/eines Experten als Platzhalter „[Name, Funktion]"; konkreter
Handlungsaufruf ohne werbliche Übertreibung; reiner Fließtext (kein Markdown);
Deutsch; 250–400 Wörter; am Ende kurzer Boilerplate „Über TÜV NORD" als Platzhalter."""


def write_pressemitteilungen(themen: list[dict]) -> None:
    """Schreibt pro Thema eine Pressemitteilung und hängt sie als t['pressemitteilung'] an.
    Läuft im Batch auf GitHub (Key sicher) – kein Live-Backend nötig."""
    if not themen:
        return
    print("Schritt 3 – Pressemitteilungen schreiben (GLM-5.2):")
    for i, t in enumerate(themen, 1):
        payload = {
            "model": MODEL,
            "temperature": 0.6,
            "messages": [
                {"role": "system", "content": PM_SYSTEM},
                {"role": "user", "content": _pm_prompt(t)},
            ],
        }
        try:
            res = _post_with_retry(CHAT_URL, payload, timeout=180)
            t["pressemitteilung"] = res["choices"][0]["message"]["content"].strip()
            print(f"  · {i}/{len(themen)}: {t.get('titel','')[:50]} ✓")
        except Exception as e:
            t["pressemitteilung"] = ""
            print(f"  ! {i}/{len(themen)}: fehlgeschlagen – {e}", file=sys.stderr)
    print()


# --------------------------------------------------------------------------- #
# Historie / Archiv
# --------------------------------------------------------------------------- #

REL_RANK = {"sehr hoch": 4, "hoch": 3, "mittel": 2, "niedrig": 1}


def update_history(now: dt.datetime, data: dict) -> list[dict]:
    """Tageseintrag in docs/archiv/history.json fortschreiben (persistente Historie)."""
    archive_dir = OUT_DIR / "archiv"
    archive_dir.mkdir(parents=True, exist_ok=True)
    hist_file = archive_dir / "history.json"

    history = []
    if hist_file.exists():
        try:
            history = json.loads(hist_file.read_text(encoding="utf-8"))
        except Exception:
            history = []

    themen = data.get("themen", [])
    top = sorted(themen, key=lambda t: -REL_RANK.get(str(t.get("relevanz", "")).lower(), 0))
    date_str = f"{now:%Y-%m-%d}"
    entry = {
        "date": date_str,
        "kw": now.isocalendar()[1],
        "count": len(themen),
        "hoch": sum(1 for t in themen if REL_RANK.get(str(t.get("relevanz", "")).lower(), 0) >= 3),
        "top_headline": (top[0].get("titel", "") if top else ""),
        "top_relevanz": (top[0].get("relevanz", "") if top else ""),
        "hinweis": data.get("hinweis", ""),
    }
    # heutigen Eintrag ersetzen (falls mehrmals am Tag), sonst anhängen
    history = [h for h in history if h.get("date") != date_str]
    history.append(entry)
    history.sort(key=lambda h: h.get("date", ""), reverse=True)

    hist_file.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    return history


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main() -> int:
    if not API_KEY:
        print("FEHLER: Umgebungsvariable GLM_API_KEY ist nicht gesetzt.", file=sys.stderr)
        return 2

    now = dt.datetime.now(dt.timezone.utc)
    items, searches = run_scan()

    if not items:
        data = {"hinweis": "Keine Fundstellen aus den Quellen erhalten (Suche leer oder fehlgeschlagen).",
                "themen": []}
    else:
        try:
            data = evaluate(items)
        except Exception as e:
            print(f"FEHLER bei der Auswertung: {e}", file=sys.stderr)
            return 1
        write_pressemitteilungen(data.get("themen", []))

    from render import build_report, build_archive_index

    html = build_report(data, now)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "index.html").write_text(html, encoding="utf-8")

    # Tages-Snapshot ins Archiv (bleibt dauerhaft im Repo erhalten)
    archive_dir = OUT_DIR / "archiv"
    archive_dir.mkdir(exist_ok=True)
    (archive_dir / f"{now:%Y-%m-%d}.html").write_text(html, encoding="utf-8")

    # Historie fortschreiben und Übersichtsseite neu bauen
    history = update_history(now, data)
    (archive_dir / "index.html").write_text(build_archive_index(history), encoding="utf-8")

    (OUT_DIR / "latest.json").write_text(
        json.dumps({"generated_at": now.isoformat(), **data}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Fertig. {len(history)} Tage in der Historie. Geschrieben: {OUT_DIR/'index.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
