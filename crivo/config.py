"""Configuração do Crivo Factual (esqueleto M1, free-first).

Nenhum segredo vive aqui. Chaves futuras entram por variáveis de
ambiente (ver .env.example) e nunca são commitadas.
"""

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.environ.get("CRIVO_DB_PATH", os.path.join(ROOT, "crivo.db"))
SITE_DIR = os.environ.get("CRIVO_SITE_DIR", os.path.join(ROOT, "site"))
DATA_DIR = os.path.join(ROOT, "data")
SCHEMA_PATH = os.path.join(ROOT, "crivo", "factbank", "schema.sql")

# Chaves opcionais futuras (não usadas pelo esqueleto).
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
