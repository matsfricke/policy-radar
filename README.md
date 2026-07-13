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
   Lösung). Bei hoher Relevanz zusätzlich ein Presse-Überschriften-Vorschlag.
3. **Veröffentlichen** – themen-zentrierte Website mit interaktivem Policy-Radar
   (Relevanz × Timing) und geschätzter Key-Guthaben-Anzeige. Wird als
   `docs/index.html` ins Repo committet und von GitHub Pages ausgeliefert; ältere
   Läufe liegen in `docs/archiv/`.

## Guthaben-Anzeige

z.ai bietet keinen API-Endpoint für den Kontostand. Die Seite zeigt daher einen
**geschätzten** Verbrauch: jeder Lauf rechnet Token- und Suchverbrauch zu
z.ai-Listenpreisen (USD) hoch und schreibt die Summe in `docs/spend.json` fort,
abgezogen vom Startguthaben (`START_BALANCE`, Standard 10). Der exakte Stand steht
im [z.ai-Dashboard](https://z.ai/manage-apikey/billing) (dorthin verlinkt die Seite).

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
| `START_BALANCE`  | `10`      | Startguthaben für die Anzeige |
| `CURRENCY`       | `€`       | Währungssymbol der Anzeige |
| `SEARCH_RECENCY` | `oneWeek` | Suchzeitraum (`oneDay`/`oneWeek`/`oneMonth`) |
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
