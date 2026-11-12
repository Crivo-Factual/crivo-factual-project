"""Dashboard estático (M4): volume, latência e distribuição.

Gera uma página HTML simples a partir do banco. Sem dependências.
"""

from ..factbank import audit


def build_dashboard(conn):
    labels = dict(
        conn.execute("SELECT label, COUNT(*) FROM verdicts GROUP BY label").fetchall()
    )
    by_day = conn.execute(
        "SELECT substr(created_at, 1, 10) AS d, COUNT(*) FROM verdicts"
        " WHERE created_at >= date('now', '-7 days') GROUP BY d ORDER BY d"
    ).fetchall()
    latency = conn.execute(
        "SELECT AVG((julianday(v.created_at) - julianday(q.created_at)) * 24 * 60)"
        " FROM verdicts v JOIN queue q"
        " ON q.id = CAST(substr(v.publication_id, 2) AS INTEGER)"
        " WHERE v.publication_id LIKE 'q%'"
    ).fetchone()[0]
    queue_counts = dict(
        conn.execute("SELECT status, COUNT(*) FROM queue GROUP BY status").fetchall()
    )
    dist = conn.execute(
        "SELECT channel, status, COUNT(*) FROM distribution"
        " GROUP BY channel, status ORDER BY channel, status"
    ).fetchall()
    audit_n = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    chain_ok = audit.verify_chain(conn)

    def rows(pairs):
        return "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in pairs)

    latency_txt = f"{latency:.0f} min" if latency is not None else "—"
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="utf-8">
<title>Crivo Factual — Dashboard</title></head>
<body>
<h1>Crivo Factual — Dashboard</h1>
<h2>Vereditos por rótulo</h2>
<table>{rows(sorted(labels.items()))}</table>
<h2>Vereditos por dia (últimos 7 dias)</h2>
<table>{rows(by_day)}</table>
<h2>Latência média (coleta até veredito)</h2>
<p>{latency_txt}</p>
<h2>Fila</h2>
<table>{rows(sorted(queue_counts.items()))}</table>
<h2>Distribuição por canal e estado</h2>
<table>{rows([(f"{c} / {s}", n) for c, s, n in dist])}</table>
<h2>Auditoria</h2>
<p>{audit_n} eventos registrados. Cadeia íntegra: {"sim" if chain_ok else "NÃO"}.</p>
</body>
</html>
"""
