#!/usr/bin/env python3
"""
Policy Scanning Routine – automatisierter Tageslauf.

Setzt den "30-Minuten-Wochenworkflow" von Svea Fricke (TÜV NORD) automatisch um:
  Schritt 1  Scannen    – die Pflicht- und Frühindikator-Quellen nach neuen
                          Leitlinien / Drafts / Positionspapieren durchsuchen
  Schritt 2  Bewerten   – Relevanz / Timing / PR-Potenzial je Thema
  Schritt 3  Übersetzen – PR-Winkel: Headline + "Was jetzt tun"-Text
  Erfolgsformel          – Entwicklung → Auswirkung → Handlung → TÜV NORD Lösung

Der Scan läuft deterministisch über die z.ai Web-Search-API (eine Suche pro
Quelle, auf deren Domain gefiltert). Die Bewertung und die PR-Texte erzeugt
GLM-5.2 über die (OpenAI-kompatible) Chat-Completions-API.

Kein Schlüssel im Code: GLM_API_KEY kommt aus der Umgebung
(lokal via .env / GitHub via Repository-Secret).
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

# Wie weit zurück gescannt wird. oneWeek passt zum täglichen Lauf;
# für einen echten Wochenlauf auf oneMonth stellen.
RECENCY = os.environ.get("SEARCH_RECENCY", "oneWeek")
RESULTS_PER_SOURCE = int(os.environ.get("RESULTS_PER_SOURCE", "6"))

OUT_DIR = Path(os.environ.get("OUT_DIR", "docs"))

# Die Quellenliste aus dem Workflow-Dokument.
# label  – Anzeigename der Quelle
# domain – Domain-Filter für die Suche
# bereich– thematische Einordnung (nur als Hinweis für das Modell)
SOURCES = [
    # A. Pflichtquellen
    {"label": "EU-Kommission (Presscorner)", "domain": "ec.europa.eu",       "bereich": "Policy / Gesetzesinitiativen"},
    {"label": "OECD",                        "domain": "oecd.org",           "bereich": "Strategische Trends"},
    {"label": "ISO",                         "domain": "iso.org",            "bereich": "Normen / Zertifizierung"},
    {"label": "EFSA",                        "domain": "efsa.europa.eu",     "bereich": "Food / Lebensmittelsicherheit"},
    {"label": "EU Medizinprodukte (DG Health)","domain": "health.ec.europa.eu","bereich": "MedTech (MDR/IVDR)"},
    # B. Frühindikator-Quellen
    {"label": "EFRAG",                       "domain": "efrag.org",          "bereich": "ESG / CSRD"},
    {"label": "ENISA",                       "domain": "enisa.europa.eu",    "bereich": "KRITIS / Cyber (NIS2)"},
    {"label": "BSI",                         "domain": "bsi.bund.de",        "bereich": "KRITIS / Cyber (national)"},
    # C. Übersetzer / Think Tanks
    {"label": "Bruegel",                     "domain": "bruegel.org",        "bereich": "EU Think Tank"},
    {"label": "McKinsey Insights",           "domain": "mckinsey.com",       "bereich": "Industrienahe Analyse"},
]

# Suchbegriff je Quelle – zielt auf genau die Signale, die der Workflow sucht.
SEARCH_QUERY = os.environ.get(
    "SEARCH_QUERY",
    "neue Leitlinien Draft Positionspapier Standard Regulierung Konsultation "
    "Zertifizierung ESG Nachhaltigkeit MedTech Lebensmittel Cybersicherheit KRITIS",
)

RELEVANTE_BEREICHE = "Zertifizierung, ESG/Nachhaltigkeit, MedTech, Food, KRITIS/Infrastruktur/Cybersicherheit"


# --------------------------------------------------------------------------- #
# HTTP-Helfer (nur Standardbibliothek – keine externen Abhängigkeiten nötig)
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
            # 4xx (außer 429) sind nicht durch Wiederholen zu heilen
            if e.code != 429 and 400 <= e.code < 500:
                break
        except URLError as e:
            last_err = f"URLError: {e.reason}"
        time.sleep(2 * attempt)
    raise RuntimeError(f"Request an {url} fehlgeschlagen: {last_err}")


# --------------------------------------------------------------------------- #
# Schritt 1 – Scannen
# --------------------------------------------------------------------------- #

def scan_source(source: dict) -> list[dict]:
    """Eine Quelle durchsuchen und die Treffer normalisiert zurückgeben."""
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
        return []

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
    return items


def run_scan() -> list[dict]:
    print("Schritt 1 – Scannen:")
    all_items: list[dict] = []
    seen_urls: set[str] = set()
    for source in SOURCES:
        for item in scan_source(source):
            key = item["url"] or item["title"]
            if key and key not in seen_urls:
                seen_urls.add(key)
                all_items.append(item)
    print(f"  → {len(all_items)} eindeutige Fundstellen gesamt\n")
    return all_items


# --------------------------------------------------------------------------- #
# Schritt 2 + 3 – Bewerten & Übersetzen (GLM-5.2)
# --------------------------------------------------------------------------- #

SYSTEM_PROMPT = (
    "Du bist Rechercheassistenz für die Pressesprecherin von TÜV NORD. "
    "Du hilfst, aus Wirtschafts- und Politikthemen PR-Chancen zu erkennen und "
    "Pressetexte im nüchtern-sachlichen Stil von TÜV-NORD-Pressemitteilungen "
    "vorzubereiten. Du antwortest ausschließlich mit gültigem JSON, ohne "
    "Markdown-Codeblöcke, ohne erklärenden Text davor oder danach."
)

USER_PROMPT_TEMPLATE = """\
Hier sind die heute gefundenen Fundstellen aus den Policy-Quellen (JSON):

{funde}

Aufgabe – arbeite den Policy-Scanning-Workflow ab:

SCHRITT 1 (Scannen): Wähle die 3–5 relevantesten NEUEN Themen aus (neue
Leitlinien, Drafts, Positionspapiere, Normen-Updates, politisch hochgezogene
Themen). Nur Headlines.

SCHRITT 2 (Bewerten): Bewerte jedes ausgewählte Thema nach:
  - relevanz: Betrifft es TÜV-NORD-Kunden konkret? (hoch/mittel/niedrig + kurze Begründung)
  - timing: Kommt das in 1–3 Jahren? (kurze Einordnung)
  - pr_potenzial: Lässt sich ein klarer "Was jetzt tun"-Text ableiten? (hoch/mittel/niedrig)
Relevante Bereiche sind: {bereiche}.

SCHRITT 3 (Übersetzen): Wähle die 1–2 stärksten Themen aus und baue je einen
PR-Winkel nach der Erfolgsformel:
  - headline: starke, konkrete Presse-Headline (kein "EU arbeitet an..."-Stil,
              sondern "Was jetzt zu tun ist"-Stil)
  - kernaussage: eine prägnante Kernaussage
  - was_aendert_sich: Was passiert gerade?
  - wer_betroffen: Wer ist betroffen?
  - was_tun: Was müssen Unternehmen jetzt tun?
  - wo_tuev_nord_hilft: Wie kann TÜV NORD mit Dienstleistungen/Expertise helfen?

Wenn heute NICHTS wirklich Relevantes dabei ist, gib leere Arrays zurück und
setze "hinweis" entsprechend – erfinde keine Themen.

Antworte GENAU in diesem JSON-Schema:
{{
  "hinweis": "kurzer Statushinweis, z.B. Anzahl relevanter Themen oder 'nichts Relevantes heute'",
  "scan": [
    {{"headline": "...", "source": "...", "date": "...", "url": "...", "bereich": "..."}}
  ],
  "bewertung": [
    {{"thema": "...", "bereich": "...", "relevanz": "...", "timing": "...", "pr_potenzial": "..."}}
  ],
  "top_themen": [
    {{
      "headline": "...", "kernaussage": "...",
      "was_aendert_sich": "...", "wer_betroffen": "...",
      "was_tun": "...", "wo_tuev_nord_hilft": "...",
      "source": "...", "url": "...", "date": "...", "bereich": "..."
    }}
  ]
}}
"""


def _extract_json(text: str) -> dict:
    """JSON aus einer Modellantwort robust herausschälen."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.lstrip().startswith("json"):
            text = text.lstrip()[4:]
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"Keine JSON-Struktur in der Antwort gefunden:\n{text[:500]}")
    return json.loads(text[start:end + 1])


def evaluate_and_translate(items: list[dict]) -> dict:
    print("Schritt 2 + 3 – Bewerten & Übersetzen (GLM-5.2):")
    funde = json.dumps(items, ensure_ascii=False, indent=2)
    user_prompt = USER_PROMPT_TEMPLATE.format(
        funde=funde, bereiche=RELEVANTE_BEREICHE
    )
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
    print(f"  → {len(data.get('scan', []))} Themen gescannt, "
          f"{len(data.get('top_themen', []))} PR-Winkel gebaut\n")
    return data


# --------------------------------------------------------------------------- #
# Rendern
# --------------------------------------------------------------------------- #

def render_html(data: dict, generated_at: dt.datetime) -> str:
    from render import build_report
    return build_report(data, generated_at)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main() -> int:
    if not API_KEY:
        print("FEHLER: Umgebungsvariable GLM_API_KEY ist nicht gesetzt.", file=sys.stderr)
        return 2

    now = dt.datetime.now(dt.timezone.utc)
    items = run_scan()

    if not items:
        data = {"hinweis": "Keine Fundstellen aus den Quellen erhalten (Suche leer oder fehlgeschlagen).",
                "scan": [], "bewertung": [], "top_themen": []}
    else:
        try:
            data = evaluate_and_translate(items)
        except Exception as e:
            print(f"FEHLER bei der Auswertung: {e}", file=sys.stderr)
            return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    html = render_html(data, now)

    index_path = OUT_DIR / "index.html"
    index_path.write_text(html, encoding="utf-8")

    archive_dir = OUT_DIR / "archiv"
    archive_dir.mkdir(exist_ok=True)
    archive_path = archive_dir / f"{now:%Y-%m-%d}.html"
    archive_path.write_text(html, encoding="utf-8")

    # Rohdaten fürs Archiv / spätere Weiterverarbeitung (z.B. Mail)
    (OUT_DIR / "latest.json").write_text(
        json.dumps({"generated_at": now.isoformat(), **data}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Fertig. Geschrieben:\n  {index_path}\n  {archive_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
