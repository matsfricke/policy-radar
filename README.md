# Policy Scanning Routine – automatisiert

Automatisiert den „30-Minuten-Wochenworkflow" (Policy Scanning Routine) für die
Pressearbeit von TÜV NORD: Jeden Morgen werden die Policy-Quellen gescannt, die
Themen bewertet und PR-Winkel („Was jetzt tun") erzeugt. Das Ergebnis landet als
öffentliche Website (GitHub Pages), die sich täglich selbst aktualisiert.

**Läuft komplett in der Cloud (GitHub Actions) – dein Rechner muss nicht an sein.**

## Was passiert im Lauf

1. **Scannen** – `scan.py` durchsucht via z.ai Web-Search je Quelle (EU-Kommission,
   OECD, ISO, EFSA, EU MedTech, EFRAG, ENISA, BSI, Bruegel, McKinsey) nach neuen
   Leitlinien / Drafts / Positionspapieren.
2. **Auswerten** – GLM-5.2 wählt die relevanten Themen und liefert pro Thema in
   EINEM kombinierten Block: Bewertung (Relevanz / Timing / PR-Potenzial) und
   PR-Winkel nach der Erfolgsformel (Entwicklung → Auswirkung → Handlung → TÜV NORD
   Lösung). Bei hoher Relevanz zusätzlich ein Presse-Überschriften-Vorschlag; wo es
   belastbare Zahlen gibt, ein Statistik-Diagramm.
3. **Pressemitteilung** – GLM-5.2 schreibt im selben Lauf pro Thema eine fertige
   Pressemitteilung im TÜV-NORD-Stil vor. Sie liegt (versteckt) in der Seite und
   erscheint per Knopfdruck – der GLM-Key bleibt sicher in GitHub, kein Backend nötig.
4. **Veröffentlichen** – themen-zentrierte Website. Wird als `docs/index.html` ins
   Repo committet und von GitHub Pages ausgeliefert.

## Historie

Jeder Lauf legt einen Tages-Snapshot unter `docs/archiv/JJJJ-MM-TT.html` ab und
schreibt `docs/archiv/history.json` fort. Die Übersichtsseite `docs/archiv/index.html`
(verlinkt oben auf der Hauptseite) listet alle bisherigen Tage. Da alles ins Repo
committet wird, **verfallen die Ergebnisse nicht** – die komplette Historie bleibt
dauerhaft erhalten und ist über GitHub Pages abrufbar.

## Kosten

Nur die z.ai/GLM-API kostet etwas (10 Suchanfragen + eine GLM-Auswertung pro Tag),
grob 0,10–0,20 € pro Lauf. GitHub Actions und GitHub Pages sind für dieses Setup
kostenlos.

---

## Einrichtung (einmalig)

### 1. Repository anlegen und hochladen

Dieser Ordner ist bereits als Git-Repo vorbereitet. Erstelle auf GitHub ein
**leeres** Repository (z. B. `policy-radar`) und lade den Ordner hoch:

```bash
git remote add origin https://github.com/<DEIN-USER>/policy-radar.git
git branch -M main
git push -u origin main
```

> Öffentliches Repo = unbegrenzte Actions-Minuten. Der GLM-Key liegt nie im Code,
> sondern als Secret (siehe unten), ist also auch bei öffentlichem Repo sicher.

### 2. GLM-API-Key als Secret hinterlegen

Im Repo: **Settings → Secrets and variables → Actions → New repository secret**

| Name          | Wert                    |
|---------------|-------------------------|
| `GLM_API_KEY` | dein z.ai / GLM API-Key |

### 3. GitHub Pages aktivieren

**Settings → Pages → Source: „Deploy from a branch" → Branch: `main`, Ordner: `/docs` → Save**

Nach dem ersten Lauf ist die Seite erreichbar unter:
`https://<DEIN-USER>.github.io/policy-radar/`

### 4. Erster Lauf

**Actions → „Policy Scanning Routine" → „Run workflow"** (manuell auslösen).
Danach läuft es automatisch täglich um 05:15 UTC (~07:15 Uhr Berlin).

---

## Anpassen

Optionale **Repo-Variablen** (Settings → Secrets and variables → Actions → *Variables*):

| Variable         | Standard  | Zweck |
|------------------|-----------|-------|
| `SEARCH_RECENCY` | `oneMonth`| Suchzeitraum (`oneDay`/`oneWeek`/`oneMonth`) |
| `GLM_MODEL`      | `glm-5.2` | Modell |

Weiteres:

- **Zeitplan:** `cron` in `.github/workflows/policy-scan.yml`. Täglich ist Standard;
  für einen echten Wochenlauf z. B. `"15 5 * * 1"` (montags).
- **Quellen:** Liste `SOURCES` in `scan.py`.
- **Ton / PR-Stil:** Prompt-Texte oben in `scan.py` (`SYSTEM_PROMPT`, `USER_PROMPT_TEMPLATE`).

## Lokal testen

```bash
cp .env.example .env        # dann GLM_API_KEY in .env eintragen
set -a && . ./.env && set +a
python3 scan.py             # erzeugt docs/index.html
```

## Dateien

| Datei | Zweck |
|-------|-------|
| `scan.py`   | Scan (z.ai Web-Search) + Auswertung (GLM-5.2) + Kosten-Tracking |
| `render.py` | themen-zentrierte Website + Radar-Chart + Guthaben-Anzeige |
| `.github/workflows/policy-scan.yml` | täglicher Cron-Lauf |
| `docs/` | veröffentlichte Website (wird automatisch befüllt) |
