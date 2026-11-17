"""Teste rápido do classificador de veracidade do Crivo Factual.

Uso:
    pip install scikit-learn
    python infer.py "cole aqui o texto COMPLETO da notícia..."
    python infer.py --arquivo noticia.txt

Sem argumento, abre o modo interativo (cole o texto, Enter vazio
para sair). O modelo só opina sobre artigos completos (500+
caracteres) — manchete sozinha devolve o aviso de texto curto,
que é o comportamento certo.
"""

import argparse
import os
import sys

import joblib

MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "model.joblib")
MIN_CHARS = 500


def classify(pipe, text):
    text = (text or "").strip()
    if len(text) < MIN_CHARS:
        return None, (
            f"Texto curto demais ({len(text)} caracteres). O modelo só "
            f"foi treinado com artigos completos — cole o texto inteiro "
            f"da notícia (mínimo de {MIN_CHARS} caracteres)."
        )
    proba = float(pipe.predict_proba([text])[0][1])
    leitura = (
        "provavelmente falsa" if proba >= 0.8 else
        "suspeita" if proba >= 0.6 else
        "provavelmente verdadeira"
    )
    return proba, (
        f"Suspeita: {proba:.2f} — {leitura}.\n"
        f"Isso é um sinal de triagem, não um veredito: no Crivo "
        f"Factual, a conclusão vem de fontes primárias (Câmara, "
        f"Senado, Diário Oficial)."
    )


def main():
    parser = argparse.ArgumentParser(
        description="Classificador de veracidade (Crivo Factual).")
    parser.add_argument("texto", nargs="?", help="texto da notícia")
    parser.add_argument("--arquivo", help="arquivo .txt com a notícia")
    args = parser.parse_args()

    if not os.path.exists(MODEL_PATH):
        print("model.joblib não encontrado nesta pasta.")
        return 1
    pipe = joblib.load(MODEL_PATH)
    print("Modelo carregado: TF-IDF + regressão logística "
          "(Fake.Br Corpus, 7.200 notícias).")

    texts = []
    if args.arquivo:
        with open(args.arquivo, encoding="utf-8") as fh:
            texts.append(fh.read())
    elif args.texto:
        texts.append(args.texto)
    else:
        print("Cole o texto completo da notícia (linha vazia para "
              "avaliar, outra vazia para sair):")
        buf = []
        for line in sys.stdin:
            line = line.rstrip("\n")
            if not line.strip() and buf:
                break
            buf.append(line)
        texts.append("\n".join(buf))

    for text in texts:
        proba, msg = classify(pipe, text)
        print(msg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
