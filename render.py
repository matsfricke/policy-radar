"""HTML-Ausgabe für die Policy Scanning Routine.

Themen-zentrierte, interaktive Website:
  - je Thema EINE Karte, die Fund, Bewertung und PR-Winkel kombiniert
    (kein Scrollen zwischen Schritten); bei hoher Relevanz mit
    vorgeschlagener Presse-Überschrift.
  - pro Thema optional ein von GLM geliefertes Statistik-Diagramm (bar/line).
  - pro Thema eine vorab von GLM geschriebene Pressemitteilung (per Button einblendbar).
  - Historie: build_archive_index() rendert die Übersicht vergangener Tage.
"""

from __future__ import annotations
import datetime as dt

TEAL = "#008b8b"
DARK = "#14304a"

MONATE = ["", "Januar", "Februar", "März", "April", "Mai", "Juni",
          "Juli", "August", "September", "Oktober", "November", "Dezember"]

# Relevanz → Sortier-/Achsenscore und Farbe (Heat: hoch = dringlich)
REL_SCORE = {"sehr hoch": 4, "hoch": 3, "mittel": 2, "niedrig": 1}
REL_COLOR = {"sehr hoch": "#c0392b", "hoch": "#e67e22", "mittel": "#008b8b", "niedrig": "#8a8f98"}

# Bereich → Farbe (für die Bereichs-Chips)
BEREICH_COLOR = {
    "Zertifizierung": "#008b8b", "ESG": "#2e8b57", "MedTech": "#6a5acd",
    "Food": "#d97706", "KRITIS": "#c0392b", "Sonstiges": "#8a8f98",
}


def _esc(s) -> str:
    return (str(s if s is not None else "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _norm(s) -> str:
    return str(s or "").strip().lower()


def _kw(d: dt.date) -> int:
    return d.isocalendar()[1]


def _link(url: str, text: str) -> str:
    url = (url or "").strip()
    if not url:
        return _esc(text)
    return f'<a href="{_esc(url)}" target="_blank" rel="noopener noreferrer">{_esc(text)}</a>'


def _sort_key(t: dict):
    rel = REL_SCORE.get(_norm(t.get("relevanz")), 0)
    pr = {"hoch": 3, "mittel": 2, "niedrig": 1}.get(_norm(t.get("pr_potenzial")), 0)
    return (-rel, -pr)


# --------------------------------------------------------------------------- #
# Themen-Chart (von GLM gelieferte Statistik, als SVG gerendert)
# --------------------------------------------------------------------------- #

def _isnum(x) -> bool:
    try:
        float(x)
        return True
    except (TypeError, ValueError):
        return False


def _topic_chart(chart) -> str:
    """Rendert ein von GLM geliefertes Statistik-Diagramm (bar/line) als SVG.
    Zeigt nur etwas an, wenn mindestens 2 echte Zahlenwerte vorliegen."""
    if not isinstance(chart, dict):
        return ""
    data = [d for d in (chart.get("data") or [])
            if isinstance(d, dict) and _isnum(d.get("value"))]
    if len(data) < 2:
        return ""
    data = data[:8]
    ctype = _norm(chart.get("type")) or "bar"
    title = chart.get("title", "")
    unit = chart.get("unit", "")
    quelle = chart.get("quelle", "")
    labels = [str(d.get("label", "")) for d in data]
    values = [float(d["value"]) for d in data]

    W, H = 640, 220
    L, R, T, B = 44, 16, 16, 46
    plotW, plotH = W - L - R, H - T - B
    vmax = max(values + [0.0])
    vmin = min(values + [0.0])
    span = (vmax - vmin) or 1.0

    def y_of(v):
        return T + plotH * (1 - (v - vmin) / span)

    zero_y = y_of(0)
    grid = f'<line x1="{L}" y1="{zero_y:.1f}" x2="{W-R}" y2="{zero_y:.1f}" class="c-axis"/>'

    def fmt(v):
        return (f"{v:.0f}" if abs(v) >= 10 or v == int(v) else f"{v:.1f}") + (f" {unit}" if unit else "")

    n = len(data)
    step = plotW / n
    marks = []
    if ctype == "line":
        pts = []
        for i, v in enumerate(values):
            x = L + step * (i + 0.5)
            y = y_of(v)
            pts.append(f"{x:.1f},{y:.1f}")
            marks.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" class="c-dot"/>')
            marks.append(f'<text x="{x:.1f}" y="{y-8:.1f}" class="c-val" text-anchor="middle">{_esc(fmt(v))}</text>')
        marks.insert(0, f'<polyline points="{" ".join(pts)}" class="c-line"/>')
    else:  # bar
        bw = step * 0.6
        for i, v in enumerate(values):
            x = L + step * i + (step - bw) / 2
            y = y_of(v)
            h = abs(y - zero_y)
            top = min(y, zero_y)
            marks.append(f'<rect x="{x:.1f}" y="{top:.1f}" width="{bw:.1f}" height="{h:.1f}" rx="3" class="c-bar"/>')
            marks.append(f'<text x="{x+bw/2:.1f}" y="{top-6:.1f}" class="c-val" text-anchor="middle">{_esc(fmt(v))}</text>')

    xlabels = "".join(
        f'<text x="{L + step*(i+0.5):.1f}" y="{H-26:.1f}" class="c-lab" text-anchor="middle">{_esc(lab[:22])}</text>'
        for i, lab in enumerate(labels)
    )
    src = f'<div class="c-src">Quelle: {_esc(quelle)}</div>' if quelle else ""

    return f"""
      <figure class="topic-chart">
        {f'<figcaption>{_esc(title)}</figcaption>' if title else ''}
        <svg viewBox="0 0 {W} {H}" role="img" aria-label="{_esc(title) or 'Diagramm'}">
          {grid}{''.join(marks)}{xlabels}
        </svg>
        <div class="c-note">📊 Werte von GLM-5.2 aus den Quellen zusammengestellt – vor Veröffentlichung prüfen.</div>
        {src}
      </figure>"""


# --------------------------------------------------------------------------- #
# Themen-Karten (kombiniert: Fund + Bewertung + PR-Winkel)
# --------------------------------------------------------------------------- #

def _chip(label: str, value: str, color: str = "") -> str:
    style = f' style="--c:{color}"' if color else ""
    return f'<span class="chip"{style}><b>{_esc(label)}</b> {_esc(value)}</span>'


def _bullets(value) -> str:
    """Rendert ein Erfolgsformel-Feld als Stichpunktliste (akzeptiert Liste oder String)."""
    if isinstance(value, (list, tuple)):
        items = [str(x).strip() for x in value if str(x).strip()]
    else:
        items = [s.strip() for s in str(value or "").replace("•", "\n").split("\n") if s.strip()]
    if not items:
        return ""
    if len(items) == 1:
        return f"<p>{_esc(items[0])}</p>"
    lis = "".join(f"<li>{_esc(it)}</li>" for it in items)
    return f"<ul>{lis}</ul>"


def _topic_card(idx: int, t: dict) -> str:
    rel = _norm(t.get("relevanz"))
    rel_color = REL_COLOR.get(rel, "#8a8f98")
    bereich = t.get("bereich") or "Sonstiges"
    ber_color = BEREICH_COLOR.get(bereich, "#8a8f98")
    src = " · ".join(x for x in [_esc(t.get("source")), _esc(t.get("date"))] if x)
    quelle = _link(t.get("url"), src or t.get("source")) if (src or t.get("url")) else ""

    ueberschrift = (t.get("vorschlag_ueberschrift") or "").strip()
    ueberschrift_html = ""
    if ueberschrift and rel in ("sehr hoch", "hoch"):
        ueberschrift_html = f"""
        <div class="headline-box">
          <span class="hl-label">Überschriften-Vorschlag</span>
          <p class="hl-text">{_esc(ueberschrift)}</p>
        </div>"""

    return f"""
    <article class="topic" id="thema-{idx}" style="--rel:{rel_color}">
      <div class="topic-top">
        <span class="chip bereich" style="--c:{ber_color}">{_esc(bereich)}</span>
        {_chip("Relevanz", t.get("relevanz",""), rel_color)}
        {_chip("Timing", t.get("timing_bucket",""))}
        {_chip("PR", t.get("pr_potenzial",""))}
      </div>
      <h3 class="topic-title">{_esc(t.get("titel"))}</h3>
      <div class="topic-meta">{quelle}{(' · ' + _esc(t.get('timing_text'))) if t.get('timing_text') else ''}</div>
      <p class="topic-summary">{_esc(t.get("zusammenfassung") or t.get("kernaussage"))}</p>
      {_topic_chart(t.get("chart"))}
      {f'<p class="topic-reason"><b>Warum relevant:</b> {_esc(t.get("relevanz_begruendung"))}</p>' if t.get("relevanz_begruendung") else ''}
      {ueberschrift_html}
      <div class="formel">
        <div class="f-step"><span class="f-label">Entwicklung</span>{_bullets(t.get("was_aendert_sich"))}</div>
        <div class="f-step"><span class="f-label">Auswirkung</span>{_bullets(t.get("wer_betroffen"))}</div>
        <div class="f-step"><span class="f-label">Handlung</span>{_bullets(t.get("was_tun"))}</div>
        <div class="f-step tuev"><span class="f-label">TÜV NORD Lösung</span>{_bullets(t.get("wo_tuev_nord_hilft"))}</div>
      </div>
      {_pm_zone(idx, t.get("pressemitteilung", ""))}
    </article>"""


def _pm_zone(idx: int, pm: str) -> str:
    pm = (pm or "").strip()
    if not pm:
        return ""
    return f"""
      <div class="pm-zone">
        <button class="pm-btn" data-target="pm-out-{idx}">✍️ Pressemitteilung anzeigen</button>
        <div class="pm-out" id="pm-out-{idx}" hidden>{_esc(pm)}<div class="pm-tools"><button class="pm-copy">📋 Kopieren</button></div></div>
      </div>"""


# --------------------------------------------------------------------------- #
# Seite
# --------------------------------------------------------------------------- #

def build_report(data: dict, generated_at: dt.datetime) -> str:
    local = generated_at.astimezone()
    datum = f"{local.day}. {MONATE[local.month]} {local.year}"
    kw = _kw(local.date())
    hinweis = _esc(data.get("hinweis", ""))

    themen = sorted(data.get("themen", []), key=_sort_key)
    cards = "".join(_topic_card(i, t) for i, t in enumerate(themen)) or \
        '<p class="empty">Heute keine relevanten neuen Themen erfasst.</p>'

    return f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Policy Radar – KW {kw}/{local.year}</title>
<style>
  :root {{
    --teal:{TEAL}; --dark:{DARK};
    --bg:#f4f6f8; --card:#fff; --text:#1d2330; --muted:#5a6472;
    --border:#e2e6eb; --soft:#fbfcfd;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg:#0f1620; --card:#17212e; --text:#e6ebf1; --muted:#9aa6b4;
             --border:#26333f; --soft:#1c2733; --dark:#cfe0ee; }}
  }}
  * {{ box-sizing:border-box; }}
  body {{ font-family:-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
          background:var(--bg); color:var(--text); margin:0; line-height:1.55; font-size:16px; }}
  .wrap {{ max-width:900px; margin:0 auto; padding:26px 20px 64px; }}
  header.cover {{ border-top:6px solid var(--teal); padding-top:18px; }}
  .kicker {{ color:var(--teal); font-size:13px; letter-spacing:1.5px; text-transform:uppercase; font-weight:700; margin:0 0 6px; }}
  h1 {{ font-size:29px; line-height:1.15; margin:0 0 6px; color:var(--dark); }}
  .subtitle {{ color:var(--muted); margin:0 0 14px; }}
  .meta {{ font-size:13.5px; color:var(--muted); margin-bottom:8px; }}
  .meta b {{ color:var(--dark); }}
  .hinweis {{ font-size:14px; color:var(--muted); font-style:italic; margin:6px 0 0; }}
  .topnav {{ margin:14px 0 4px; }}
  .topnav a {{ display:inline-block; font-size:14px; font-weight:600; color:var(--teal);
               border:1px solid var(--border); border-radius:8px; padding:7px 14px; text-decoration:none; background:var(--card); }}
  .topnav a:hover {{ border-color:var(--teal); }}

  h2.sec {{ font-size:20px; color:var(--dark); margin:26px 0 4px; padding-bottom:6px; border-bottom:2px solid var(--teal); }}
  .sec-sub {{ color:var(--muted); font-size:14px; margin:0 0 14px; }}
  .empty {{ color:var(--muted); font-style:italic; }}

  /* Themen-Karten */
  .topic {{ background:var(--card); border:1px solid var(--border); border-left:5px solid var(--rel);
            border-radius:10px; padding:16px 18px; margin-bottom:14px; scroll-margin-top:16px; }}
  .topic-top {{ display:flex; flex-wrap:wrap; gap:6px; margin-bottom:8px; }}
  .chip {{ font-size:12px; border:1px solid var(--border); border-radius:20px; padding:2px 10px; color:var(--muted); background:var(--soft); }}
  .chip b {{ color:var(--dark); font-weight:700; }}
  .chip[style*="--c"] {{ border-color:var(--c); }}
  .chip[style*="--c"] b {{ color:var(--c); }}
  .chip.bereich {{ background:var(--c); border-color:var(--c); color:#fff; font-weight:700; }}
  .topic-title {{ font-size:19px; line-height:1.25; margin:2px 0 4px; color:var(--dark); }}
  .topic-meta {{ font-size:13px; color:var(--muted); margin-bottom:8px; }}
  .topic-meta a {{ color:var(--teal); }}
  .topic-summary {{ font-size:15px; margin:0 0 10px; }}
  .topic-reason {{ font-size:14px; color:var(--muted); margin:0 0 12px; }}
  .topic-reason b {{ color:var(--dark); }}

  /* Themen-Chart (von GLM erzeugte Statistik) */
  .topic-chart {{ margin:2px 0 14px; padding:12px 14px 8px; border:1px solid var(--border);
                  border-radius:8px; background:var(--soft); overflow-x:auto; }}
  .topic-chart figcaption {{ font-size:13.5px; font-weight:700; color:var(--dark); margin-bottom:6px; }}
  .topic-chart svg {{ width:100%; min-width:340px; height:auto; display:block; }}
  .topic-chart .c-axis {{ stroke:var(--border); stroke-width:1; }}
  .topic-chart .c-bar {{ fill:var(--teal); }}
  .topic-chart .c-line {{ fill:none; stroke:var(--teal); stroke-width:2.5; }}
  .topic-chart .c-dot {{ fill:var(--teal); }}
  .topic-chart .c-val {{ fill:var(--dark); font-size:11px; font-weight:700; }}
  .topic-chart .c-lab {{ fill:var(--muted); font-size:11px; }}
  .topic-chart .c-note {{ font-size:11.5px; color:var(--muted); margin-top:4px; }}
  .topic-chart .c-src {{ font-size:11.5px; color:var(--muted); margin-top:2px; }}

  .headline-box {{ background:linear-gradient(0deg,rgba(0,139,139,.08),rgba(0,139,139,.08)); border:1px dashed var(--teal);
                   border-radius:8px; padding:10px 14px; margin:0 0 12px; }}
  .hl-label {{ font-size:11px; text-transform:uppercase; letter-spacing:1px; color:var(--teal); font-weight:700; }}
  .hl-text {{ margin:4px 0 0; font-size:17px; font-weight:700; color:var(--dark); line-height:1.3; }}

  .kernaussage {{ color:var(--muted); font-size:14.5px; margin:0 0 12px; }}
  .formel {{ display:grid; grid-template-columns:1fr 1fr; gap:1px; background:var(--border);
             border:1px solid var(--border); border-radius:8px; overflow:hidden; }}
  @media (max-width:560px) {{ .formel {{ grid-template-columns:1fr; }} }}
  .f-step {{ background:var(--soft); padding:11px 14px; }}
  .f-step.tuev {{ background:rgba(0,139,139,.08); }}
  .f-label {{ display:block; font-size:11px; text-transform:uppercase; letter-spacing:1px; color:var(--teal); font-weight:700; margin-bottom:5px; }}
  .f-step p {{ margin:0; font-size:14px; }}
  .f-step ul {{ margin:0; padding-left:17px; }}
  .f-step li {{ font-size:14px; margin-bottom:4px; }}

  /* Live-Pressemitteilung */
  .pm-zone {{ margin-top:14px; }}
  .pm-btn {{ font:inherit; font-size:14px; font-weight:700; color:#fff; background:var(--teal);
             border:none; border-radius:8px; padding:9px 16px; cursor:pointer; transition:opacity .15s; }}
  .pm-btn:hover {{ opacity:.88; }}
  .pm-btn:disabled {{ opacity:.6; cursor:default; }}
  .pm-out {{ margin-top:12px; padding:16px 18px; border:1px solid var(--border);
             border-left:4px solid var(--teal); border-radius:8px; background:var(--soft);
             font-size:14.5px; line-height:1.6; white-space:pre-wrap; }}
  .pm-out.err {{ border-left-color:#c0392b; color:#c0392b; white-space:normal; }}
  .pm-tools {{ margin-top:10px; display:flex; gap:8px; }}
  .pm-tools button {{ font:inherit; font-size:12.5px; border:1px solid var(--border);
                      background:var(--card); color:var(--muted); border-radius:6px; padding:4px 10px; cursor:pointer; }}

  a {{ color:var(--teal); }}
  footer {{ margin-top:44px; padding-top:16px; border-top:1px solid var(--border); font-size:12.5px; color:var(--muted); }}
</style>
</head>
<body>
<div class="wrap">
  <header class="cover">
    <p class="kicker">Policy Scanning Routine · TÜV NORD</p>
    <h1>Policy Radar</h1>
    <p class="subtitle">Wirtschafts- und Politikthemen mit PR-Relevanz für TÜV-NORD-Kunden</p>
    <div class="meta"><b>{datum}</b> (KW {kw}) · Bereiche: Zertifizierung · ESG · MedTech · Food · KRITIS · automatisch via GLM-5.2</div>
    {f'<p class="hinweis">{hinweis}</p>' if hinweis else ''}
    <nav class="topnav"><a href="archiv/">🗂 Historie – frühere Tage ansehen</a></nav>
  </header>

  <h2 class="sec">Themen</h2>
  <p class="sec-sub">Nach Relevanz sortiert. Jede Karte kombiniert Fund, Bewertung und PR-Winkel (Erfolgsformel).</p>
  {cards}

  <footer>
    Automatisch erzeugt durch die Policy Scanning Routine · GLM-5.2 · z.ai Web Search.
    Quellen verlinkt; vor Veröffentlichung redaktionell prüfen.
    · <a href="archiv/">🗂 Historie</a>
  </footer>
</div>

<script>
  // --- Pressemitteilung: vorab von GLM geschrieben, hier ein-/ausblenden ---
  document.querySelectorAll('.pm-btn').forEach(function(btn) {{
    btn.addEventListener('click', function() {{
      var out = document.getElementById(btn.getAttribute('data-target'));
      if (!out) return;
      out.hidden = !out.hidden;
      btn.textContent = out.hidden ? '✍️ Pressemitteilung anzeigen' : '✕ Pressemitteilung ausblenden';
    }});
  }});
  document.querySelectorAll('.pm-copy').forEach(function(cp) {{
    cp.addEventListener('click', function() {{
      var box = cp.closest('.pm-out');
      var text = box ? box.childNodes[0].textContent : '';
      navigator.clipboard.writeText(text).then(function() {{
        cp.textContent = '✓ kopiert';
        setTimeout(function() {{ cp.textContent = '📋 Kopieren'; }}, 2000);
      }});
    }});
  }});
</script>
</body>
</html>"""


# --------------------------------------------------------------------------- #
# Historie / Archiv-Übersicht
# --------------------------------------------------------------------------- #

def build_archive_index(history: list[dict]) -> str:
    """Übersichtsseite aller archivierten Tage (newest first)."""
    def fmt_date(ds: str) -> str:
        try:
            d = dt.date.fromisoformat(ds)
            return f"{d.day}. {MONATE[d.month]} {d.year}"
        except Exception:
            return ds

    rows = []
    for h in history:
        ds = h.get("date", "")
        rel = _norm(h.get("top_relevanz"))
        rel_color = REL_COLOR.get(rel, "#8a8f98")
        cnt = h.get("count", 0)
        hoch = h.get("hoch", 0)
        badge = (f'<span class="h-badge" style="--c:{rel_color}">{_esc(h.get("top_relevanz"))}</span>'
                 if h.get("top_relevanz") else "")
        rows.append(f"""
        <a class="h-row" href="{_esc(ds)}.html">
          <div class="h-date">{fmt_date(ds)} <span class="h-kw">KW {h.get('kw','')}</span></div>
          <div class="h-top">{_esc(h.get('top_headline') or h.get('hinweis') or '—')}</div>
          <div class="h-meta">{cnt} Themen · {hoch}× hohe Relevanz {badge}</div>
        </a>""")
    body = "".join(rows) or '<p class="empty">Noch keine archivierten Tage.</p>'

    return f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Policy Radar – Historie</title>
<style>
  :root {{ --teal:{TEAL}; --dark:{DARK}; --bg:#f4f6f8; --card:#fff; --text:#1d2330;
           --muted:#5a6472; --border:#e2e6eb; --soft:#fbfcfd; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg:#0f1620; --card:#17212e; --text:#e6ebf1; --muted:#9aa6b4;
             --border:#26333f; --soft:#1c2733; --dark:#cfe0ee; }}
  }}
  * {{ box-sizing:border-box; }}
  body {{ font-family:-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
          background:var(--bg); color:var(--text); margin:0; line-height:1.5; }}
  .wrap {{ max-width:820px; margin:0 auto; padding:28px 20px 64px; }}
  header {{ border-top:6px solid var(--teal); padding-top:18px; margin-bottom:6px; }}
  .kicker {{ color:var(--teal); font-size:13px; letter-spacing:1.5px; text-transform:uppercase; font-weight:700; margin:0 0 6px; }}
  h1 {{ font-size:27px; margin:0 0 6px; color:var(--dark); }}
  .sub {{ color:var(--muted); margin:0 0 8px; }}
  .back {{ display:inline-block; margin:8px 0 20px; font-size:14px; font-weight:600; color:var(--teal);
           text-decoration:none; border:1px solid var(--border); border-radius:8px; padding:7px 14px; background:var(--card); }}
  .h-row {{ display:block; text-decoration:none; color:inherit; background:var(--card);
            border:1px solid var(--border); border-left:4px solid var(--teal); border-radius:10px;
            padding:14px 16px; margin-bottom:10px; transition:border-color .15s; }}
  .h-row:hover {{ border-color:var(--teal); }}
  .h-date {{ font-weight:700; color:var(--dark); font-size:15px; }}
  .h-kw {{ font-weight:500; color:var(--muted); font-size:13px; margin-left:6px; }}
  .h-top {{ margin:4px 0 6px; font-size:15px; }}
  .h-meta {{ font-size:13px; color:var(--muted); }}
  .h-badge {{ display:inline-block; font-size:11px; font-weight:700; color:#fff; background:var(--c);
              border-radius:20px; padding:1px 9px; margin-left:6px; }}
  .empty {{ color:var(--muted); font-style:italic; }}
  footer {{ margin-top:40px; padding-top:16px; border-top:1px solid var(--border); font-size:12.5px; color:var(--muted); }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <p class="kicker">Policy Scanning Routine · TÜV NORD</p>
    <h1>🗂 Historie</h1>
    <p class="sub">Alle bisherigen Tagesscans – bleiben dauerhaft erhalten.</p>
  </header>
  <a class="back" href="../">← Zum aktuellen Scan</a>
  {body}
  <footer>Automatisch erzeugt durch die Policy Scanning Routine · GLM-5.2.</footer>
</div>
</body>
</html>"""
