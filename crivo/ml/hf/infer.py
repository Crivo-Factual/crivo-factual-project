"""Teste local dos classificadores de veracidade do Crivo Factual.

Dois modelos, um roteador por tamanho do texto:
- v1 (Fake.Br, artigos completos): o especialista. Só opina a
  partir de 500 caracteres — manchete sozinha não serve.
- v2 (FakenewsBR, 36.594 itens: notícias, tweets, WhatsApp):
  o generalista. Opina sobre texto curto, mas com viés de
  falso positivo (verdadeiro curto pontua 0,58 em média) —
  é sinal fraco, nunca veredito.

Uso:
    pip install scikit-learn
    python infer.py "cole aqui o texto da notícia..."
    python infer.py --arquivo noticia.txt
    python infer.py   (modo interativo)

Os arquivos model_v1.joblib e model_v2.joblib precisam estar
nesta mesma pasta.
"""

import argparse
import os
import sys

import joblib

HERE = os.path.dirname(os.path.abspath(__file__))
MIN_CHARS_V1 = 500


def _load(name):
    path = os.path.join(HERE, name)
    if not os.path.exists(path):
        return None
    return joblib.load(path)


def _score(pipe, text):
    return float(pipe.predict_proba([text])[0][1])


def _leitura(proba):
    return (
        "provavelmente falsa" if proba >= 0.8 else
        "suspeita" if proba >= 0.6 else
        "provavelmente verdadeira"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Classificadores de veracidade (Crivo Factual).")
    parser.add_argument("texto", nargs="?", help="texto da notícia")
    parser.add_argument("--arquivo", help="arquivo .txt com a notícia")
    args = parser.parse_args()

    v1 = _load("model_v1.joblib")
    v2 = _load("model_v2.joblib")
    if v1 is None and v2 is None:
        print("Nenhum modelo encontrado nesta pasta "
              "(model_v1.joblib / model_v2.joblib).")
        return 1
    if v1 is not None:
        print("v1 carregada: TF-IDF + regressão logística "
              "(Fake.Br, 7.200 artigos).")
    if v2 is not None:
        print("v2 carregada: TF-IDF + regressão logística "
              "(FakenewsBR, 36.594 itens).")

    texts = []
    if args.arquivo:
        with open(args.arquivo, encoding="utf-8") as fh:
            texts.append(fh.read())
    elif args.texto:
        texts.append(args.texto)
    else:
        print("Cole o texto da notícia (linha vazia para avaliar, "
              "outra vazia para sair):")
        buf = []
        for line in sys.stdin:
            line = line.rstrip("\n")
            if not line.strip() and buf:
                break
            buf.append(line)
        texts.append("\n".join(buf))

    for text in texts:
        text = (text or "").strip()
        n = len(text)
        print(f"\nTexto: {n} caracteres.")
        if v1 is not None and n >= MIN_CHARS_V1:
            p = _score(v1, text)
            print(f"v1 (artigo): suspeita {p:.2f} — {_leitura(p)}.")
        elif v1 is not None:
            print(f"v1: sem score — texto curto demais "
                  f"(mínimo {MIN_CHARS_V1} caracteres).")
        if v2 is not None:
            p = _score(v2, text)
            print(f"v2 (geral): suspeita {p:.2f} — {_leitura(p)}.")
            if n < MIN_CHARS_V1:
                print("  (v2 opina sobre texto curto, mas com viés: "
                      "verdadeiro curto pontua 0,58 em média — "
                      "leia como sinal fraco.)")
        print("Isso é um sinal de triagem, não um veredito: no Crivo "
              "Factual, a conclusão vem de fontes primárias "
              "(Câmara, Senado, Diário Oficial).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
