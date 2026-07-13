# Policy Scanning Routine – automatisiert

Automatisiert den „30-Minuten-Wochenworkflow" (Policy Scanning Routine) für die
Pressearbeit von TÜV NORD: Jeden Morgen werden die Policy-Quellen gescannt, die
Themen bewertet und PR-Winkel („Was jetzt tun") erzeugt. Das Ergebnis landet als
öffentliche Website (GitHub Pages) und optional zusätzlich per E-Mail.

**Läuft komplett in der Cloud (GitHub Actions) – dein Rechner muss nicht an sein.**

## Was passiert im Lauf

1. **Scannen** – `scan.py` durchsucht via z.ai Web-Search je Quelle (EU-Kommission,
   OECD, ISO, EFSA, EU MedTech, EFRAG, ENISA, BSI, Bruegel, McKinsey) nach neuen
   Leitlinien / Drafts / Positionspapieren.
2. **Bewerten & Übersetzen** – GLM-5.2 wählt die relevanten Themen, bewertet sie
   nach Relevanz / Timing / PR-Potenzial und baut PR-Winkel nach der Erfolgsformel
   (Entwicklung → Auswirkung → Handlung → TÜV NORD Lösung).
3. **Veröffentlichen** – Ergebnis wird als `docs/index.html` geschrieben, ins Repo
   committet und von GitHub Pages ausgeliefert. Ältere Läufe liegen in `docs/archiv/`.

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

## E-Mail-Versand aktivieren (optional)

Zusätzlich zur Website kann jedes Ergebnis per Mail verschickt werden. Dafür diese
Secrets anlegen (Gmail-Beispiel):

| Secret      | Beispielwert            | Hinweis |
|-------------|-------------------------|---------|
| `MAIL_TO`   | `empfaenger@firma.de`   | mehrere kommagetrennt |
| `MAIL_FROM` | `dein.name@gmail.com`   | |
| `SMTP_HOST` | `smtp.gmail.com`        | |
| `SMTP_PORT` | `465`                   | |
| `SMTP_USER` | `dein.name@gmail.com`   | |
| `SMTP_PASS` | *App-Passwort*          | **kein** normales Passwort! |

> **Gmail:** Es funktioniert nur ein **App-Passwort** (Google-Konto → Sicherheit →
> 2-Faktor aktivieren → App-Passwörter). Solange `MAIL_TO` nicht gesetzt ist, wird
> der Mailschritt einfach übersprungen.

Für die Online-Version in der Mail zusätzlich als **Variable** (nicht Secret)
`PAGES_URL` = `https://<DEIN-USER>.github.io/policy-radar/` anlegen.

---

## Anpassen

- **Zeitplan:** `cron` in `.github/workflows/policy-scan.yml`. Täglich ist Standard;
  für einen echten Wochenlauf z. B. `"15 5 * * 1"` (montags).
- **Suchzeitraum:** Repo-Variable `SEARCH_RECENCY` (`oneDay` / `oneWeek` / `oneMonth`).
  Für täglich passt `oneWeek`, für wöchentlich eher `oneMonth`.
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
| `scan.py`   | Scan (z.ai Web-Search) + Auswertung (GLM-5.2) |
| `render.py` | HTML-Ausgabe entlang der Workflow-Schritte |
| `mailer.py` | optionaler Mailversand |
| `.github/workflows/policy-scan.yml` | täglicher Cron-Lauf |
| `docs/` | veröffentlichte Website (wird automatisch befüllt) |
