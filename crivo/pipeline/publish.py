"""Gerador de páginas estáticas (etapa 6 do pipeline).

Cada análise vira uma página permanente (ficha de verificação) e o
índice lista todas. Sem dependências externas; o visual segue a
identidade da Onda 0 de forma simplificada.
"""

import html

STATUS_LABEL = {
    "confirmada": "Confirmada",
    "contraditada": "Contraditada",
    "sem_evidencia": "Sem evidência",
}


def _esc(text):
    return html.escape(str(text or ""))


def render_analysis(analysis, label, index, rule):
    claims_html = ""
    for claim in analysis["claims"]:
        evs = [e for e in analysis.get("evidences", [])
               if e.get("claim_text") == claim["text"]]
        ev_html = "".join(
            f"<li><strong>{_esc(e['source_name'])}</strong>"
            + (f" — <a href='{_esc(e['source_url'])}'>fonte</a>"
               if e.get("source_url") else "")
            + (f": {_esc(e['excerpt'])}" if e.get("excerpt") else "")
            + "</li>"
            for e in evs
        )
        claims_html += (
            f"<li><strong>{_esc(claim['text'])}</strong> "
            f"— {STATUS_LABEL[claim['status']]}"
            + (f"<ul>{ev_html}</ul>" if ev_html else
               " <em>(sem evidência localizada)</em>")
            + "</li>"
        )
    index_txt = f"{index:.0f}%" if index is not None else "sem índice"
    meter = f"{index:.0f}" if index is not None else "0"
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="utf-8">
<title>{_esc(analysis['title'])} — Crivo Factual</title></head>
<body>
<h1>Crivo Factual</h1>
<p><em>Todo fato passa pelo crivo. A conclusão é sua.</em></p>
<h2>{_esc(analysis['title'])}</h2>
<p><strong>Veredito: {label}</strong> — índice {index_txt} (regra: {rule})</p>
<div>Medidor do crivo: {meter}/100</div>
<h3>Resumo</h3>
<p>{_esc(analysis['summary'])}</p>
<h3>Alegações verificadas</h3>
<ul>{claims_html}</ul>
<h3>Mensagem para os canais</h3>
<p>{_esc(analysis.get('channel_summary', ''))}</p>
<p><a href="https://crivofactual.com.br/analise/{_esc(analysis['id'])}">Análise completa</a></p>
<p><small>Índice de sustentação pelas provas localizadas. Novas evidências podem alterá-lo.</small></p>
</body>
</html>
"""


def render_index(analyses):
    links = "".join(
        f"<li><a href='analise-{_esc(a['id'])}.html'>{_esc(a['title'])}</a></li>"
        for a in analyses
    )
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="utf-8">
<title>Crivo Factual — Verificações</title></head>
<body>
<h1>Crivo Factual</h1>
<p><em>Todo fato passa pelo crivo. A conclusão é sua.</em></p>
<h2>Verificações concluídas</h2>
<ul>{links}</ul>
</body>
</html>
"""
