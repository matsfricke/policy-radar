# Live-Pressemitteilung – Cloudflare Worker

Kleiner Serverless-Endpoint, der den GLM-Key geheim hält und auf Anfrage eine
Pressemitteilung zu genau einem Thema schreibt. Die öffentliche Policy-Radar-Seite
ruft ihn per POST auf.

## Einmal einrichten (kostenlos)

Voraussetzung: ein (gratis) Cloudflare-Account.

```bash
# Wrangler (Cloudflare CLI) – einmalig
npm install -g wrangler
cd worker

# Login im Browser (deine Aktion)
wrangler login

# GLM-Key als Secret hinterlegen (wird NICHT im Code gespeichert)
wrangler secret put GLM_API_KEY      # dann Key einfügen

# Deployen
wrangler deploy
```

`wrangler deploy` gibt eine URL aus, z. B.
`https://policy-radar-pm.<dein-subdomain>.workers.dev`.

## Mit der Website verbinden

Diese URL im GitHub-Repo als **Variable** hinterlegen:
**Settings → Secrets and variables → Actions → Variables →** `PM_ENDPOINT` = die Worker-URL.

Beim nächsten Lauf rendert die Seite den Button „Pressemitteilung live schreiben"
gegen diesen Endpoint. (Zum sofortigen Testen: Actions → Run workflow.)

## Missbrauch eindämmen

Nach dem Pages-Setup in `wrangler.toml` `ALLOWED_ORIGIN` auf deine Website-Origin
setzen (z. B. `https://DEIN-USER.github.io`) und erneut `wrangler deploy`. Das ist
ein weicher Schutz (CORS) – für strengere Limits ließe sich ein geteiltes Token
oder Cloudflare-Rate-Limiting ergänzen.
