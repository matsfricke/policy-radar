/**
 * Policy Radar – Live-Pressemitteilung (Cloudflare Worker)
 *
 * Hält den GLM-Key geheim (als Worker-Secret) und schreibt auf Anfrage eine
 * vollständige Pressemitteilung im TÜV-NORD-Stil zu genau EINEM ausgewählten
 * Thema. Die öffentliche Website ruft diesen Endpoint per POST auf – der Key
 * verlässt niemals den Server.
 *
 * Secrets / Variablen (via `wrangler secret put` bzw. wrangler.toml [vars]):
 *   GLM_API_KEY     (Secret)   z.ai / GLM API-Key
 *   GLM_MODEL       (var)      Standard: glm-5.2
 *   ALLOWED_ORIGIN  (var)      erlaubte Website-Origin (z.B. https://user.github.io), Standard "*"
 */

const API_URL = "https://api.z.ai/api/paas/v4/chat/completions";

function corsHeaders(env) {
  return {
    "Access-Control-Allow-Origin": env.ALLOWED_ORIGIN || "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "86400",
  };
}

function json(body, status, env) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...corsHeaders(env) },
  });
}

function asBullets(v) {
  if (Array.isArray(v)) return v.map((x) => "- " + x).join("\n");
  return String(v || "");
}

function buildPrompt(t) {
  return `Schreibe eine vollständige, veröffentlichungsfähige Pressemitteilung im
nüchtern-sachlichen Stil der TÜV NORD GROUP zu folgendem Thema.

Thema: ${t.titel || ""}
Bereich: ${t.bereich || ""}
Quelle: ${t.source || ""} (${t.date || ""}) ${t.url || ""}
Vorgeschlagene Überschrift: ${t.vorschlag_ueberschrift || "(frei wählen)"}

Hintergrund / Zusammenfassung:
${t.zusammenfassung || ""}

Was ändert sich:
${asBullets(t.was_aendert_sich)}

Wer ist betroffen:
${asBullets(t.wer_betroffen)}

Was sollten Unternehmen jetzt tun:
${asBullets(t.was_tun)}

Wie kann TÜV NORD helfen:
${asBullets(t.wo_tuev_nord_hilft)}

Vorgaben:
- Struktur: prägnante Überschrift, optional Unterzeile, dann Fließtext-Absätze.
- Erster Absatz beantwortet Wer/Was/Wann/Warum.
- Ein sachliches Zitat einer TÜV-NORD-Sprecherin/eines Experten einbauen (als Platzhalter kenntlich, z.B. „[Name, Funktion]").
- Konkreter Nutzen und Handlungsaufruf, ohne werblich zu übertreiben.
- Kein Markdown, reiner Fließtext. Sprache: Deutsch. Länge: 250–400 Wörter.
- Am Ende ein kurzer Boilerplate-Absatz „Über TÜV NORD" als Platzhalter.`;
}

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders(env) });
    }
    if (request.method !== "POST") {
      return json({ error: "Nur POST." }, 405, env);
    }
    if (!env.GLM_API_KEY) {
      return json({ error: "GLM_API_KEY ist im Worker nicht gesetzt." }, 500, env);
    }

    let topic;
    try {
      const body = await request.json();
      topic = body.topic;
      if (!topic || !topic.titel) throw new Error("kein Thema");
    } catch (e) {
      return json({ error: "Ungültige Anfrage: erwarte { topic: {...} }." }, 400, env);
    }

    const payload = {
      model: env.GLM_MODEL || "glm-5.2",
      temperature: 0.6,
      messages: [
        { role: "system", content: "Du bist Presseredakteur der TÜV NORD GROUP und schreibst professionelle, sachliche Pressemitteilungen." },
        { role: "user", content: buildPrompt(topic) },
      ],
    };

    let res;
    try {
      res = await fetch(API_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${env.GLM_API_KEY}`,
        },
        body: JSON.stringify(payload),
      });
    } catch (e) {
      return json({ error: "Verbindung zur GLM-API fehlgeschlagen." }, 502, env);
    }

    if (!res.ok) {
      const detail = await res.text();
      return json({ error: `GLM-API HTTP ${res.status}`, detail: detail.slice(0, 300) }, 502, env);
    }

    const data = await res.json();
    const text = data?.choices?.[0]?.message?.content?.trim() || "";
    return json({ text }, 200, env);
  },
};
