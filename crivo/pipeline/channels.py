"""Mensagens de canal (M4): foto + resumo + link, por canal.

Formato único em 3 partes (Onda 0, v3): imagem do assunto, resumo curto
para despertar curiosidade e link direto para a análise no fim.
Adaptações por canal:
- Instagram: caption sem link clicável — o link vai como texto com a
  orientação "link na bio"; a imagem é a foto do assunto.
- X: texto até 280 caracteres + link. Cada post COM link custa
  US$ 0,20 na API paga — por isso o X é manual/racionado (ver doc 10).
- WhatsApp: texto pronto para o Canal (postagem manual, gratuita).
"""

X_POST_WITH_LINK_USD = 0.20
X_MAX_LEN = 280


def _fit_x(head, summary, link):
    base = f"{head}\n\n{link}"
    if len(base) > X_MAX_LEN:
        head = head[: max(X_MAX_LEN - len(link) - 5, 0)] + "…"
        base = f"{head}\n\n{link}"
    room = X_MAX_LEN - len(base) - 2  # 2 = as quebras antes do resumo
    if room <= 0 or not summary:
        return base
    return f"{head}\n\n{summary[:room]}\n\n{link}"


def build_messages(analysis):
    """Monta as 3 mensagens de uma análise.

    analysis: {id, title, label, index, summary, image_url}.
    Devolve {instagram, x, whatsapp}, cada um com text, image_url e link.
    """
    link = f"https://crivofactual.com.br/analise/{analysis['id']}"
    label = analysis["label"]
    index = analysis.get("index")
    head = f"{analysis['title']} — Veredito: {label}" + (
        f" ({index:.0f}%)" if index is not None else ""
    )
    summary = (analysis.get("summary") or "")[:200]
    image_url = analysis.get("image_url") or ""
    instagram = {
        "text": f"{head}\n\n{summary}\n\nLink na bio: {link}",
        "image_url": image_url,
        "link": link,
    }
    x = {
        "text": _fit_x(head, summary, link),
        "image_url": image_url,
        "link": link,
        "cost_usd": X_POST_WITH_LINK_USD,
    }
    whatsapp = {
        "text": f"{head}\n\n{summary}\n\nAnálise completa: {link}",
        "image_url": image_url,
        "link": link,
    }
    return {"instagram": instagram, "x": x, "whatsapp": whatsapp}
