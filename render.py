"""HTML-Ausgabe für die Policy Scanning Routine.

Baut eine eigenständige, responsive Website (light/dark-fähig), gegliedert nach
den drei Workflow-Schritten (Scannen / Bewerten / Übersetzen) und der
Erfolgsformel (Entwicklung → Auswirkung → Handlung → TÜV NORD Lösung).
"""

from __future__ import annotations
import datetime as dt

TEAL = "#008b8b"
DARK = "#14304a"

MONATE = ["", "Januar", "Februar", "März", "April", "Mai", "Juni",
          "Juli", "August", "September", "Oktober", "November", "Dezember"]


def _esc(s) -> str:
    return (str(s if s is not None else "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _kw(d: dt.date) -> int:
    return d.isocalendar()[1]


def _link(url: str, text: str) -> str:
    url = (url or "").strip()
    if not url:
        return _esc(text)
    return f'<a href="{_esc(url)}" target="_blank" rel="noopener noreferrer">{_esc(text)}</a>'


def _scan_section(scan: list[dict]) -> str:
    if not scan:
        return '<p class="empty">Heute keine neuen Themen mit Policy-Charakter erfasst.</p>'
    rows = []
    for i, t in enumerate(scan, 1):
        meta = " · ".join(x for x in [_esc(t.get("source")), _esc(t.get("date"))] if x)
        badge = f'<span class="tag">{_esc(t.get("bereich"))}</span>' if t.get("bereich") else ""
        head = _link(t.get("url"), t.get("headline"))
        rows.append(
            f'<li class="scan-item"><span class="num">{i}</span>'
            f'<div><div class="scan-head">{head} {badge}</div>'
            f'<div class="scan-meta">{meta}</div></div></li>'
        )
    return f'<ol class="scan-list">{"".join(rows)}</ol>'


def _eval_section(bewertung: list[dict]) -> str:
    if not bewertung:
        return '<p class="empty">Keine Bewertung – es wurden keine relevanten Themen ausgewählt.</p>'
    rows = []
    for b in bewertung:
        rows.append(
            "<tr>"
            f'<td class="t-topic">{_esc(b.get("thema"))}<br><span class="tag">{_esc(b.get("bereich"))}</span></td>'
            f'<td>{_esc(b.get("relevanz"))}</td>'
            f'<td>{_esc(b.get("timing"))}</td>'
            f'<td>{_esc(b.get("pr_potenzial"))}</td>'
            "</tr>"
        )
    return (
        '<div class="table-wrap"><table>'
        "<thead><tr><th>Thema</th><th>Relevanz</th><th>Timing</th><th>PR-Potenzial</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


def _translate_section(top: list[dict]) -> str:
    if not top:
        return '<p class="empty">Heute kein Top-Thema mit ausreichendem PR-Potenzial.</p>'
    cards = []
    for t in top:
        src = " · ".join(x for x in [_esc(t.get("source")), _esc(t.get("date"))] if x)
        quelle = f'<div class="pr-source">Quelle: {_link(t.get("url"), src or t.get("source"))}</div>' if src or t.get("url") else ""
        badge = f'<span class="tag light">{_esc(t.get("bereich"))}</span>' if t.get("bereich") else ""
        cards.append(f"""
        <article class="pr-card">
          <div class="pr-bar">{badge} PR-Winkel</div>
          <h3>{_esc(t.get("headline"))}</h3>
          <p class="kernaussage">{_esc(t.get("kernaussage"))}</p>
          <div class="formel">
            <div class="f-step"><span class="f-label">Entwicklung</span><p>{_esc(t.get("was_aendert_sich"))}</p></div>
            <div class="f-step"><span class="f-label">Auswirkung</span><p>{_esc(t.get("wer_betroffen"))}</p></div>
            <div class="f-step"><span class="f-label">Handlung</span><p>{_esc(t.get("was_tun"))}</p></div>
            <div class="f-step tuev"><span class="f-label">TÜV NORD Lösung</span><p>{_esc(t.get("wo_tuev_nord_hilft"))}</p></div>
          </div>
          {quelle}
        </article>""")
    return "".join(cards)


def build_report(data: dict, generated_at: dt.datetime) -> str:
    local = generated_at.astimezone()
    datum = f"{local.day}. {MONATE[local.month]} {local.year}"
    kw = _kw(local.date())
    hinweis = _esc(data.get("hinweis", ""))

    scan_html = _scan_section(data.get("scan", []))
    eval_html = _eval_section(data.get("bewertung", []))
    trans_html = _translate_section(data.get("top_themen", []))

    return f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Policy Radar – KW {kw}/{local.year}</title>
<style>
  :root {{
    --teal: {TEAL}; --dark: {DARK};
    --bg: #f4f6f8; --card: #ffffff; --text: #1d2330; --muted: #5a6472;
    --border: #e2e6eb; --soft: #fbfcfd;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #0f1620; --card: #17212e; --text: #e6ebf1; --muted: #9aa6b4;
      --border: #26333f; --soft: #1c2733; --dark: #cfe0ee;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    background: var(--bg); color: var(--text); margin: 0;
    line-height: 1.55; font-size: 16px;
  }}
  .wrap {{ max-width: 860px; margin: 0 auto; padding: 28px 20px 64px; }}
  header.cover {{ border-top: 6px solid var(--teal); padding-top: 20px; margin-bottom: 8px; }}
  .kicker {{ color: var(--teal); font-size: 13px; letter-spacing: 1.5px;
            text-transform: uppercase; font-weight: 700; margin: 0 0 6px; }}
  h1 {{ font-size: 30px; line-height: 1.15; margin: 0 0 8px; color: var(--dark); }}
  .subtitle {{ color: var(--muted); margin: 0 0 16px; }}
  .meta {{ background: var(--card); border-left: 4px solid var(--teal);
           padding: 12px 16px; border-radius: 4px; font-size: 14px;
           color: var(--muted); margin-bottom: 10px; }}
  .meta b {{ color: var(--dark); }}
  .hinweis {{ font-size: 14px; color: var(--muted); margin: 4px 0 26px; font-style: italic; }}

  section {{ margin-top: 34px; }}
  h2 {{ font-size: 21px; color: var(--dark); margin: 0 0 4px;
        padding-bottom: 6px; border-bottom: 2px solid var(--teal); }}
  .step-sub {{ color: var(--muted); font-size: 14px; margin: 0 0 14px; }}
  .empty {{ color: var(--muted); font-style: italic; }}

  .scan-list {{ list-style: none; padding: 0; margin: 0; }}
  .scan-item {{ display: flex; gap: 12px; align-items: flex-start;
                background: var(--card); border: 1px solid var(--border);
                border-left: 4px solid var(--teal); border-radius: 6px;
                padding: 12px 14px; margin-bottom: 8px; }}
  .num {{ flex: 0 0 26px; height: 26px; border-radius: 50%; background: var(--teal);
          color: #fff; font-weight: 700; font-size: 14px; display: flex;
          align-items: center; justify-content: center; margin-top: 1px; }}
  .scan-head {{ font-weight: 600; color: var(--dark); }}
  .scan-head a {{ color: var(--dark); }}
  .scan-meta {{ font-size: 13px; color: var(--muted); margin-top: 2px; }}

  .tag {{ display: inline-block; font-size: 12px; background: rgba(0,139,139,.14);
          color: var(--teal); border-radius: 4px; padding: 1px 7px;
          margin-left: 4px; font-weight: 700; vertical-align: middle; }}
  .tag.light {{ background: rgba(255,255,255,.2); color: #fff; }}

  .table-wrap {{ overflow-x: auto; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
  th {{ background: var(--dark); color: #fff; text-align: left; padding: 9px 10px; }}
  td {{ border: 1px solid var(--border); padding: 9px 10px; vertical-align: top;
        background: var(--card); }}
  .t-topic {{ font-weight: 600; color: var(--dark); min-width: 180px; }}

  .pr-card {{ border: 1px solid var(--border); border-radius: 8px;
              overflow: hidden; margin-bottom: 18px; background: var(--card); }}
  .pr-bar {{ background: var(--teal); color: #fff; font-weight: 700;
             font-size: 13px; letter-spacing: .5px; text-transform: uppercase;
             padding: 8px 16px; }}
  .pr-card h3 {{ margin: 14px 16px 4px; color: var(--dark); font-size: 19px; line-height: 1.25; }}
  .kernaussage {{ margin: 0 16px 14px; color: var(--muted); font-size: 15px; }}
  .formel {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1px;
             background: var(--border); border-top: 1px solid var(--border); }}
  @media (max-width: 560px) {{ .formel {{ grid-template-columns: 1fr; }} }}
  .f-step {{ background: var(--soft); padding: 12px 16px; }}
  .f-step.tuev {{ background: rgba(0,139,139,.08); }}
  .f-label {{ display: block; font-size: 11px; text-transform: uppercase;
              letter-spacing: 1px; color: var(--teal); font-weight: 700; margin-bottom: 4px; }}
  .f-step p {{ margin: 0; font-size: 14.5px; }}
  .pr-source {{ font-size: 13px; color: var(--muted); padding: 10px 16px; }}
  .pr-source a {{ color: var(--teal); }}

  a {{ color: var(--teal); }}
  footer {{ margin-top: 48px; padding-top: 16px; border-top: 1px solid var(--border);
            font-size: 12.5px; color: var(--muted); }}
</style>
</head>
<body>
<div class="wrap">
  <header class="cover">
    <p class="kicker">Policy Scanning Routine · TÜV NORD</p>
    <h1>Policy Radar – Wochenscan</h1>
    <p class="subtitle">Wirtschafts- und Politikthemen mit PR-Relevanz für TÜV-NORD-Kunden</p>
    <div class="meta">
      <b>Datum:</b> {datum} (KW {kw}) &nbsp;·&nbsp;
      <b>Abgedeckte Bereiche:</b> Zertifizierung · ESG/Nachhaltigkeit · MedTech · Food · KRITIS/Cyber &nbsp;·&nbsp;
      <b>Erstellt:</b> automatisch via GLM-5.2
    </div>
    {f'<p class="hinweis">{hinweis}</p>' if hinweis else ''}
  </header>

  <section>
    <h2>Schritt 1 – Scannen: Was ist neu?</h2>
    <p class="step-sub">Neue Leitlinien, Drafts, Positionspapiere und politisch hochgezogene Themen aus den Pflicht- und Frühindikator-Quellen.</p>
    {scan_html}
  </section>

  <section>
    <h2>Schritt 2 – Bewerten: Ist das relevant?</h2>
    <p class="step-sub">Schnellbewertung nach Relevanz (betrifft es Kunden konkret?), Timing (kommt es in 1–3 Jahren?) und PR-Potenzial.</p>
    {eval_html}
  </section>

  <section>
    <h2>Schritt 3 – Übersetzen: PR-Winkel</h2>
    <p class="step-sub">Erfolgsformel: Entwicklung → Auswirkung → Handlung → TÜV NORD Lösung.</p>
    {trans_html}
  </section>

  <footer>
    Automatisch erzeugt durch die Policy Scanning Routine · GLM-5.2 · z.ai Web Search.
    Quellen sind verlinkt; Angaben ohne Gewähr, vor Veröffentlichung redaktionell prüfen.
    <a href="archiv/">Archiv</a>
  </footer>
</div>
</body>
</html>"""
