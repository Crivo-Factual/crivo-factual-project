"""Demo do classificador de veracidade do Crivo Factual (Space).

Cole um texto em português e veja a probabilidade estimada de
ele ser falso. Três modelos:
- v1 (Fake.Br, artigos completos): só opina a partir de 500
  caracteres — é o especialista em artigos.
- v2 (FakenewsBR, notícias + tweets + WhatsApp): opina sobre
  texto curto, mas com viés de falso positivo — sinal fraco.
- unificado (Fake.Br + FakenewsBR): um só modelo para qualquer
  tamanho de texto — artigos F1 0,9646, misto F1 0,7924.

É um sinal de triagem — não um veredito: no Crivo Factual, o
veredito é decidido por regras sobre fontes primárias, nunca por
este modelo.

Os modelos são baixados do Hub na primeira execução.
"""

import gradio as gr
import joblib
from huggingface_hub import hf_hub_download

# Troque pelo seu repositório no Hub (o mesmo nome do model card).
HF_MODEL_REPO = "brenindexdev/crivo-factual-fakebr"

# Mínimo de texto para a v1 opinar (ver crivo/ml/classifier.py).
MIN_CHARS_V1 = 500


def load(name):
    path = hf_hub_download(repo_id=HF_MODEL_REPO, filename=name)
    return joblib.load(path)


V1 = load("model_v1.joblib")
V2 = load("model_v2.joblib")
UNI = load("model_unified.joblib")


def _leitura(proba):
    return (
        "provavelmente falsa" if proba >= 0.8 else
        "suspeita" if proba >= 0.6 else
        "provavelmente verdadeira"
    )


def classify(text, modelo_escolhido):
    text = (text or "").strip()
    if not text:
        return None, "Cole um texto para classificar."
    if modelo_escolhido == "Unificado (um só modelo)":
        proba = float(UNI.predict_proba([text])[0][1])
        modelo = "unificado"
        aviso = ""
    elif len(text) >= MIN_CHARS_V1:
        proba = float(V1.predict_proba([text])[0][1])
        modelo = "v1 (artigo completo)"
        aviso = ""
    else:
        proba = float(V2.predict_proba([text])[0][1])
        modelo = "v2 (texto curto)"
        aviso = (" A v2 opina sobre texto curto, mas com viés: "
                 "verdadeiro curto pontua 0,46 em média — leia "
                 "como sinal fraco.")
    return (
        {"Falsa": proba, "Verdadeira": 1 - proba},
        f"Modelo: {modelo}. Suspeita: {proba:.2f} — "
        f"{_leitura(proba)}.{aviso} Isso é um sinal de triagem, "
        f"não um veredito: no Crivo Factual, a conclusão vem de "
        f"fontes primárias (Câmara, Senado, Diário Oficial).",
    )


demo = gr.Interface(
    fn=classify,
    inputs=[
        gr.Textbox(
            label="Texto em português (artigo ou texto curto)",
            placeholder="Cole aqui o texto...",
            lines=10,
        ),
        gr.Radio(
            choices=["Roteador (v1/v2 por tamanho)",
                     "Unificado (um só modelo)"],
            value="Unificado (um só modelo)",
            label="Modelo",
        ),
    ],
    outputs=[
        gr.Label(label="Probabilidade"),
        gr.Markdown(label="Leitura"),
    ],
    title="Crivo Factual — Classificador de veracidade",
    description=(
        "Três modelos: v1 treinada no Fake.Br Corpus (7.200 "
        "artigos) para textos longos, v2 treinada no FakenewsBR "
        "(36.594 itens: notícias, tweets, WhatsApp) para textos "
        "curtos, e o unificado (Fake.Br + FakenewsBR) que serve "
        "para qualquer tamanho. O score é um sinal de triagem, "
        "não um veredito."
    ),
    examples=[
        ["A Câmara dos Deputados aprovou nesta terça-feira o projeto "
         "que trata da renegociação de dívidas rurais. A votação "
         "contou com ampla maioria dos parlamentares presentes, e o "
         "texto segue agora para análise do Senado Federal, onde deve "
         "ser votado ainda nesta semana, segundo a liderança do "
         "governo na Casa."],
        ["URGENTE: você não vai acreditar no que o governo escondeu! "
         "Compartilhe antes que apaguem!"],
    ],
)

if __name__ == "__main__":
    demo.launch()
