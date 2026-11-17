"""Demo do classificador de veracidade do Crivo Factual (Space).

Cole o texto COMPLETO de uma notícia em português e veja a
probabilidade estimada de ela ser falsa. É um sinal de triagem —
não um veredito: no Crivo Factual, o veredito é decidido por
regras sobre fontes primárias, nunca por este modelo.

O modelo é baixado do Hub na primeira execução.
"""

import gradio as gr
import joblib
from huggingface_hub import hf_hub_download

# Troque pelo seu repositório no Hub (o mesmo nome do model card).
HF_MODEL_REPO = "SEU_USUARIO/crivo-factual-fakebr"
MODEL_FILE = "model.joblib"

# Mínimo de texto para o modelo opinar (ver crivo/ml/classifier.py).
MIN_CHARS = 500


def load_model():
    path = hf_hub_download(repo_id=HF_MODEL_REPO, filename=MODEL_FILE)
    return joblib.load(path)


MODEL = load_model()


def classify(text):
    text = (text or "").strip()
    if len(text) < MIN_CHARS:
        return (
            None,
            f"Texto curto demais ({len(text)} caracteres). O modelo só "
            f"foi treinado com artigos completos — cole o texto inteiro "
            f"da notícia (mínimo de {MIN_CHARS} caracteres).",
        )
    proba = float(MODEL.predict_proba([text])[0][1])
    verdict = (
        "provavelmente falsa" if proba >= 0.8 else
        "suspeita" if proba >= 0.6 else
        "provavelmente verdadeira"
    )
    return (
        {"Falsa": proba, "Verdadeira": 1 - proba},
        f"Suspeita: {proba:.2f} — {verdict}. Isso é um sinal de "
        f"triagem, não um veredito: no Crivo Factual, a conclusão "
        f"vem de fontes primárias (Câmara, Senado, Diário Oficial).",
    )


demo = gr.Interface(
    fn=classify,
    inputs=gr.Textbox(
        label="Texto completo da notícia (português)",
        placeholder="Cole aqui o texto inteiro da notícia...",
        lines=10,
    ),
    outputs=[
        gr.Label(label="Probabilidade"),
        gr.Markdown(label="Leitura"),
    ],
    title="Crivo Factual — Classificador de veracidade",
    description=(
        "Modelo treinado no Fake.Br Corpus (7.200 notícias, "
        "Monteiro et al., 2018). Cole o artigo completo — manchetes "
        "sozinhas não funcionam com este modelo."
    ),
    examples=[
        ["A Câmara dos Deputados aprovou nesta terça-feira o projeto "
         "que trata da renegociação de dívidas rurais. A votação "
         "contou com ampla maioria dos parlamentares presentes, e o "
         "texto segue agora para análise do Senado Federal, onde deve "
         "ser votado ainda nesta semana, segundo a liderança do "
         "governo na Casa."],
    ],
)

if __name__ == "__main__":
    demo.launch()
