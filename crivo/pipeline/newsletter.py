"""Boletim semanal (M4).

Monta o resumo das verificações dos últimos N dias, pronto para envio
por tier gratuito de e-mail (Resend/Brevo — ver DEVELOPMENT.md). O
envio em si não está neste módulo: sem chave e sem remetente
configurados, o boletim é gerado como arquivo no outbox.
"""

from datetime import datetime, timedelta, timezone

BASE_URL = "https://crivofactual.com.br/analise"


def build_weekly_digest(conn, days=7, now=None):
    now_dt = now or datetime.now(timezone.utc)
    since = (now_dt - timedelta(days=days)).isoformat()
    rows = conn.execute(
        "SELECT p.id, p.title, v.label, v.index_value FROM verdicts v"
        " JOIN publications p ON p.id = v.publication_id"
        " WHERE v.created_at >= ?"
        " AND v.id IN (SELECT MAX(id) FROM verdicts GROUP BY publication_id)"
        " ORDER BY v.created_at DESC",
        (since,),
    ).fetchall()
    lines_md = []
    lines_html = []
    for pub_id, title, label, index in rows:
        idx = f" ({index:.0f}%)" if index is not None else ""
        lines_md.append(
            f"- **{title}** — {label}{idx} — {BASE_URL}/{pub_id}\n"
        )
        lines_html.append(
            f"<li><strong>{title}</strong> — {label}{idx} — "
            f"<a href='{BASE_URL}/{pub_id}'>análise completa</a></li>"
        )
    subject = (
        f"Crivo Factual — {len(rows)} verificações "
        f"nos últimos {days} dias"
    )
    body_md = (
        "# Crivo Factual — boletim semanal\n\n"
        + (f"{len(rows)} verificações publicadas.\n\n" if rows else "Nenhuma verificação nova no período.\n\n")
        + "".join(lines_md)
    )
    body_html = (
        "<h1>Crivo Factual — boletim semanal</h1>"
        + (f"<p>{len(rows)} verificações publicadas.</p>" if rows else "<p>Nenhuma verificação nova no período.</p>")
        + "<ul>" + "".join(lines_html) + "</ul>"
    )
    return {
        "subject": subject,
        "body_md": body_md,
        "body_html": body_html,
        "count": len(rows),
    }
