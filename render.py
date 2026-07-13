"""HTML-Ausgabe für die Policy Scanning Routine.

Themen-zentrierte, interaktive Website:
  - Guthaben-Anzeige (geschätzter Verbrauch des GLM-Keys)
  - interaktiver Policy-Radar (Relevanz × Timing, Blasengröße = PR-Potenzial)
  - je Thema EINE Karte, die Fund, Bewertung und PR-Winkel kombiniert
    (kein Scrollen zwischen Schritten); bei hoher Relevanz mit
    vorgeschlagener Presse-Überschrift.
"""

from __future__ import annotations
import json
import datetime as dt

TEAL = "#008b8b"
DARK = "#14304a"

MONATE = ["", "Januar", "Februar", "März", "April", "Mai", "Juni",
          "Juli", "August", "September", "Oktober", "November", "Dezember"]

# Relevanz → Sortier-/Achsenscore und Farbe (Heat: hoch = dringlich)
REL_SCORE = {"sehr hoch": 4, "hoch": 3, "mittel": 2, "niedrig": 1}
REL_COLOR = {"sehr hoch": "#c0392b", "hoch": "#e67e22", "mittel": "#008b8b", "niedrig": "#8a8f98"}

# Timing-Bucket → x-Position (0 = jetzt … 3 = spät)
TIMING_X = {"jetzt": 0, "6-12 monate": 1, "6–12 monate": 1, "1-3 jahre": 2, "1–3 jahre": 2, ">3 jahre": 3}
TIMING_LABELS = ["jetzt", "6–12 Mon.", "1–3 Jahre", ">3 Jahre"]

PR_RADIUS = {"hoch": 13, "mittel": 9, "niedrig": 6}

# Bereich → Farbe (für den Radar-Chart)
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
# Guthaben-Widget
# --------------------------------------------------------------------------- #

def _balance_widget(spend: dict) -> str:
    if not spend:
        return ""
    cur = spend.get("currency", "€")
    start = float(spend.get("start_balance", 0) or 0)
    remaining = float(spend.get("remaining", start) or 0)
    spent = float(spend.get("spent_usd", 0) or 0)
    pct = max(0.0, min(100.0, (remaining / start * 100) if start else 0))
    color = "#2e8b57" if pct > 40 else ("#e67e22" if pct > 15 else "#c0392b")
    runs = spend.get("runs", 0)
    return f"""
    <div class="balance">
      <div class="bal-head">
        <span class="bal-title">GLM-Key · Guthaben (geschätzt)</span>
        <span class="bal-num">~{cur}{remaining:.2f} <span class="bal-of">von {cur}{start:.0f}</span></span>
      </div>
      <div class="bal-bar"><div class="bal-fill" style="width:{pct:.0f}%;background:{color}"></div></div>
      <div class="bal-foot">
        verbraucht ~${spent:.2f} über {runs} Läufe ·
        <a href="https://z.ai/manage-apikey/billing" target="_blank" rel="noopener">exakter Stand im z.ai-Dashboard →</a>
      </div>
    </div>"""


# --------------------------------------------------------------------------- #
# Radar-Chart (SVG, serverseitig positioniert + JS-Tooltip/Klick)
# --------------------------------------------------------------------------- #

def _radar_chart(themen: list[dict]) -> str:
    if not themen:
        return ""
    L, R, T, B = 64, 700, 24, 300
    innerW, innerH = R - L, B - T

    def x_of(i):  # i = timing index 0..3
        return L + (i + 0.5) * (innerW / 4)

    def y_of(score):  # score 1..4 (4 oben)
        return T + (4 - score) / 3 * (innerH - 30) + 15

    # Gitter + Achsenbeschriftung
    grid = []
    for i, lab in enumerate(TIMING_LABELS):
        gx = x_of(i)
        grid.append(f'<line x1="{gx:.0f}" y1="{T}" x2="{gx:.0f}" y2="{B}" class="grid"/>')
        grid.append(f'<text x="{gx:.0f}" y="{B+18}" class="axlab" text-anchor="middle">{lab}</text>')
    for score, lab in [(4, "sehr hoch"), (3, "hoch"), (2, "mittel"), (1, "niedrig")]:
        gy = y_of(score)
        grid.append(f'<line x1="{L}" y1="{gy:.0f}" x2="{R}" y2="{gy:.0f}" class="grid"/>')
        grid.append(f'<text x="{L-8}" y="{gy+4:.0f}" class="axlab" text-anchor="end">{lab}</text>')

    # Blasen (mit leichtem Jitter bei Kollision in derselben Zelle)
    cell_count: dict = {}
    bubbles = []
    for idx, t in enumerate(themen):
        rel = _norm(t.get("relevanz"))
        score = REL_SCORE.get(rel, 1)
        ti = TIMING_X.get(_norm(t.get("timing_bucket")), 2)
        key = (ti, score)
        n = cell_count.get(key, 0)
        cell_count[key] = n + 1
        jitter = (n % 3 - 1) * 16
        cx = x_of(ti) + jitter
        cy = y_of(score) + (n // 3) * 16
        r = PR_RADIUS.get(_norm(t.get("pr_potenzial")), 8)
        color = BEREICH_COLOR.get(t.get("bereich"), "#8a8f98")
        bubbles.append(
            f'<circle class="bub" cx="{cx:.0f}" cy="{cy:.0f}" r="{r}" '
            f'fill="{color}" data-i="{idx}" tabindex="0"/>'
        )

    # Legende Bereiche
    used_bereiche = []
    for t in themen:
        b = t.get("bereich") or "Sonstiges"
        if b not in used_bereiche:
            used_bereiche.append(b)
    legend = "".join(
        f'<span class="lg"><span class="dot" style="background:{BEREICH_COLOR.get(b,"#8a8f98")}"></span>{_esc(b)}</span>'
        for b in used_bereiche
    )

    return f"""
    <div class="chart-card">
      <div class="chart-title">Policy-Radar <span class="chart-hint">Relevanz × Timing · Blasengröße = PR-Potenzial · Klick springt zum Thema</span></div>
      <div class="chart-wrap">
        <svg viewBox="0 0 720 330" class="radar" role="img" aria-label="Policy-Radar">
          <text x="{L}" y="14" class="axtitle">▲ Relevanz</text>
          <text x="{R}" y="{B+18}" class="axtitle" text-anchor="end">Timing ▶</text>
          {''.join(grid)}
          {''.join(bubbles)}
        </svg>
      </div>
      <div class="legend">{legend}</div>
      <div id="tip" class="tip" hidden></div>
    </div>"""


# --------------------------------------------------------------------------- #
# Themen-Karten (kombiniert: Fund + Bewertung + PR-Winkel)
# --------------------------------------------------------------------------- #

def _chip(label: str, value: str, color: str = "") -> str:
    style = f' style="--c:{color}"' if color else ""
    return f'<span class="chip"{style}><b>{_esc(label)}</b> {_esc(value)}</span>'


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
      <p class="topic-reason">{_esc(t.get("relevanz_begruendung"))}</p>
      {ueberschrift_html}
      <p class="kernaussage">{_esc(t.get("kernaussage"))}</p>
      <div class="formel">
        <div class="f-step"><span class="f-label">Entwicklung</span><p>{_esc(t.get("was_aendert_sich"))}</p></div>
        <div class="f-step"><span class="f-label">Auswirkung</span><p>{_esc(t.get("wer_betroffen"))}</p></div>
        <div class="f-step"><span class="f-label">Handlung</span><p>{_esc(t.get("was_tun"))}</p></div>
        <div class="f-step tuev"><span class="f-label">TÜV NORD Lösung</span><p>{_esc(t.get("wo_tuev_nord_hilft"))}</p></div>
      </div>
    </article>"""


# --------------------------------------------------------------------------- #
# Seite
# --------------------------------------------------------------------------- #

def build_report(data: dict, generated_at: dt.datetime, spend: dict | None = None) -> str:
    local = generated_at.astimezone()
    datum = f"{local.day}. {MONATE[local.month]} {local.year}"
    kw = _kw(local.date())
    hinweis = _esc(data.get("hinweis", ""))

    themen = sorted(data.get("themen", []), key=_sort_key)
    cards = "".join(_topic_card(i, t) for i, t in enumerate(themen)) or \
        '<p class="empty">Heute keine relevanten neuen Themen erfasst.</p>'

    # Chart-Tooltipdaten für JS
    tip_data = [{
        "titel": t.get("titel", ""), "bereich": t.get("bereich", ""),
        "relevanz": t.get("relevanz", ""), "timing": t.get("timing_bucket", ""),
        "pr": t.get("pr_potenzial", ""),
    } for t in themen]

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

  /* Guthaben */
  .balance {{ background:var(--card); border:1px solid var(--border); border-radius:10px; padding:14px 16px; margin:18px 0 6px; }}
  .bal-head {{ display:flex; justify-content:space-between; align-items:baseline; gap:12px; flex-wrap:wrap; }}
  .bal-title {{ font-size:13px; font-weight:700; color:var(--dark); text-transform:uppercase; letter-spacing:.5px; }}
  .bal-num {{ font-size:20px; font-weight:800; color:var(--dark); }}
  .bal-of {{ font-size:13px; font-weight:500; color:var(--muted); }}
  .bal-bar {{ height:9px; background:var(--border); border-radius:6px; overflow:hidden; margin:9px 0 7px; }}
  .bal-fill {{ height:100%; border-radius:6px; transition:width .4s; }}
  .bal-foot {{ font-size:12.5px; color:var(--muted); }}

  /* Chart */
  .chart-card {{ background:var(--card); border:1px solid var(--border); border-radius:10px; padding:14px 16px 10px; margin:14px 0 8px; position:relative; }}
  .chart-title {{ font-size:15px; font-weight:700; color:var(--dark); margin-bottom:6px; }}
  .chart-hint {{ font-size:12px; font-weight:400; color:var(--muted); }}
  .chart-wrap {{ overflow-x:auto; }}
  .radar {{ width:100%; min-width:480px; height:auto; display:block; }}
  .radar .grid {{ stroke:var(--border); stroke-width:1; }}
  .radar .axlab {{ fill:var(--muted); font-size:11px; }}
  .radar .axtitle {{ fill:var(--teal); font-size:11px; font-weight:700; }}
  .radar .bub {{ opacity:.82; cursor:pointer; stroke:var(--card); stroke-width:1.5; transition:opacity .15s; outline:none; }}
  .radar .bub:hover, .radar .bub:focus {{ opacity:1; stroke:var(--dark); stroke-width:2; }}
  .legend {{ display:flex; flex-wrap:wrap; gap:12px; margin-top:4px; font-size:12px; color:var(--muted); }}
  .lg {{ display:inline-flex; align-items:center; gap:5px; }}
  .dot {{ width:10px; height:10px; border-radius:50%; display:inline-block; }}
  .tip {{ position:fixed; z-index:20; background:var(--dark); color:#fff; padding:8px 11px; border-radius:7px; font-size:12.5px; max-width:260px; pointer-events:none; box-shadow:0 4px 16px rgba(0,0,0,.25); }}
  .tip b {{ display:block; margin-bottom:3px; }}

  h2.sec {{ font-size:20px; color:var(--dark); margin:30px 0 4px; padding-bottom:6px; border-bottom:2px solid var(--teal); }}
  .sec-sub {{ color:var(--muted); font-size:14px; margin:0 0 14px; }}
  .empty {{ color:var(--muted); font-style:italic; }}

  /* Themen-Karten */
  .topic {{ background:var(--card); border:1px solid var(--border); border-left:5px solid var(--rel);
            border-radius:10px; padding:16px 18px; margin-bottom:14px; scroll-margin-top:16px; }}
  .topic.flash {{ animation:flash 1.2s ease; }}
  @keyframes flash {{ 0%,100%{{background:var(--card);}} 25%{{background:rgba(0,139,139,.10);}} }}
  .topic-top {{ display:flex; flex-wrap:wrap; gap:6px; margin-bottom:8px; }}
  .chip {{ font-size:12px; border:1px solid var(--border); border-radius:20px; padding:2px 10px; color:var(--muted); background:var(--soft); }}
  .chip b {{ color:var(--dark); font-weight:700; }}
  .chip[style*="--c"] {{ border-color:var(--c); }}
  .chip[style*="--c"] b {{ color:var(--c); }}
  .chip.bereich {{ background:var(--c); border-color:var(--c); color:#fff; font-weight:700; }}
  .topic-title {{ font-size:19px; line-height:1.25; margin:2px 0 4px; color:var(--dark); }}
  .topic-meta {{ font-size:13px; color:var(--muted); margin-bottom:6px; }}
  .topic-meta a {{ color:var(--teal); }}
  .topic-reason {{ font-size:14.5px; margin:0 0 10px; }}

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
  .f-label {{ display:block; font-size:11px; text-transform:uppercase; letter-spacing:1px; color:var(--teal); font-weight:700; margin-bottom:4px; }}
  .f-step p {{ margin:0; font-size:14px; }}

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
    {_balance_widget(spend or {})}
  </header>

  {_radar_chart(themen)}

  <h2 class="sec">Themen</h2>
  <p class="sec-sub">Nach Relevanz sortiert. Jede Karte kombiniert Fund, Bewertung und PR-Winkel (Erfolgsformel).</p>
  {cards}

  <footer>
    Automatisch erzeugt durch die Policy Scanning Routine · GLM-5.2 · z.ai Web Search.
    Guthaben ist geschätzt (Token-/Suchverbrauch). Quellen verlinkt; vor Veröffentlichung redaktionell prüfen.
    · <a href="archiv/">Archiv</a>
  </footer>
</div>

<script>
  var TIP = {json.dumps(tip_data, ensure_ascii=False)};
  var tip = document.getElementById('tip');
  function showTip(e, i) {{
    var d = TIP[i]; if (!d) return;
    tip.innerHTML = '<b>' + d.titel + '</b>' +
      d.bereich + ' · Relevanz: ' + d.relevanz + ' · Timing: ' + d.timing + ' · PR: ' + d.pr;
    tip.hidden = false;
    var x = (e.clientX || 0) + 14, y = (e.clientY || 0) + 14;
    if (x > window.innerWidth - 280) x = window.innerWidth - 280;
    tip.style.left = x + 'px'; tip.style.top = y + 'px';
  }}
  function hideTip() {{ tip.hidden = true; }}
  document.querySelectorAll('.radar .bub').forEach(function(c) {{
    var i = +c.getAttribute('data-i');
    c.addEventListener('mousemove', function(e) {{ showTip(e, i); }});
    c.addEventListener('mouseleave', hideTip);
    c.addEventListener('focus', function(e) {{
      var r = c.getBoundingClientRect();
      showTip({{clientX: r.left, clientY: r.top}}, i);
    }});
    c.addEventListener('blur', hideTip);
    function go() {{
      var el = document.getElementById('thema-' + i);
      if (el) {{ el.scrollIntoView({{behavior:'smooth', block:'center'}});
                el.classList.remove('flash'); void el.offsetWidth; el.classList.add('flash'); }}
    }}
    c.addEventListener('click', go);
    c.addEventListener('keydown', function(e) {{ if (e.key === 'Enter' || e.key === ' ') {{ e.preventDefault(); go(); }} }});
  }});
</script>
</body>
</html>"""
