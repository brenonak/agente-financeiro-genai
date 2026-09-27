"""
config.py — Configurações da aplicação (chaves e endpoints).

As credenciais NÃO ficam no código: são lidas do arquivo .env.
Copie o arquivo .env.example para .env e preencha com seus dados.

A Vera funciona com qualquer provedor compatível com a API da OpenAI.
Escolha um destes cenários no seu .env:

1) OpenAI (pago):
   OPENAI_API_KEY=sk-...
   OPENAI_BASE_URL=https://api.openai.com/v1
   OPENAI_MODEL=gpt-4o-mini

2) Groq (possui camada gratuita generosa):
   OPENAI_API_KEY=gsk_...
   OPENAI_BASE_URL=https://api.groq.com/openai/v1
   OPENAI_MODEL=llama-3.3-70b-versatile

3) Ollama (100% local e grátis, sem chave):
   OPENAI_API_KEY=ollama
   OPENAI_BASE_URL=http://localhost:11434/v1
   OPENAI_MODEL=llama3.1
"""

import os

from dotenv import load_dotenv

# Carrega o arquivo .env que estiver na pasta src/
load_dotenv()

API_KEY: str = os.getenv("OPENAI_API_KEY", "")
BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
MODELO: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
