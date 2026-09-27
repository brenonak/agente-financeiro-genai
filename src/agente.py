"""
agente.py — Cérebro da Vera, assistente financeira inteligente.

Responsabilidades:
1. Carregar a base de conhecimento (CSV/JSON da pasta data/).
2. Calcular métricas financeiras DE FORMA DETERMINÍSTICA em Python
   (gastos por categoria, saldo, progresso das metas). Isso é o coração
   da estratégia anti-alucinação: o LLM nunca precisa "fazer conta".
3. Selecionar produtos compatíveis com o perfil do cliente.
4. Montar o contexto e conversar com o LLM.

O objetivo é que a IA apenas EXPLIQUE e RECOMENDE em cima de números
prontos e confiáveis, em vez de gerá-los (e potencialmente errá-los).
"""

from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

# Cliente OpenAI-compatível. Funciona com OpenAI, Groq (grátis),
# OpenRouter, Ollama local, etc. — basta trocar base_url/modelo no .env
from openai import OpenAI

import config


# --------------------------------------------------------------------------- #
# 1. CARREGAMENTO DA BASE DE CONHECIMENTO
# --------------------------------------------------------------------------- #

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _ler_json(nome: str) -> dict | list:
    with open(DATA_DIR / nome, encoding="utf-8") as f:
        return json.load(f)


def _ler_csv(nome: str) -> list[dict]:
    with open(DATA_DIR / nome, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


@dataclass
class BaseConhecimento:
    """Agrega tudo o que a Vera 'sabe' sobre o cliente e os produtos."""

    perfil: dict = field(default_factory=dict)
    produtos: list[dict] = field(default_factory=list)
    transacoes: list[dict] = field(default_factory=list)
    atendimentos: list[dict] = field(default_factory=list)

    @classmethod
    def carregar(cls) -> "BaseConhecimento":
        return cls(
            perfil=_ler_json("perfil_investidor.json"),
            produtos=_ler_json("produtos_financeiros.json"),
            transacoes=_ler_csv("transacoes.csv"),
            atendimentos=_ler_csv("historico_atendimento.csv"),
        )


# --------------------------------------------------------------------------- #
# 2. ANÁLISE FINANCEIRA DETERMINÍSTICA (anti-alucinação)
# --------------------------------------------------------------------------- #

def analisar_transacoes(transacoes: list[dict]) -> dict:
    """Calcula receitas, despesas, saldo e gastos por categoria.

    Toda a matemática financeira acontece AQUI, em Python — nunca no LLM.
    """
    receitas = 0.0
    despesas = 0.0
    por_categoria: dict[str, float] = {}

    for t in transacoes:
        valor = float(t["valor"])
        if t["tipo"] == "entrada":
            receitas += valor
        else:
            despesas += valor
            cat = t["categoria"]
            por_categoria[cat] = por_categoria.get(cat, 0.0) + valor

    # Ordena categorias da maior para a menor despesa
    por_categoria = dict(
        sorted(por_categoria.items(), key=lambda kv: kv[1], reverse=True)
    )

    return {
        "receitas": round(receitas, 2),
        "despesas": round(despesas, 2),
        "saldo": round(receitas - despesas, 2),
        "por_categoria": {k: round(v, 2) for k, v in por_categoria.items()},
        "qtd_transacoes": len(transacoes),
    }


def _meses_ate(prazo: str) -> int | None:
    """Meses aproximados entre hoje e um prazo no formato 'YYYY-MM'."""
    try:
        alvo = datetime.strptime(prazo, "%Y-%m").date()
    except (ValueError, TypeError):
        return None
    hoje = date.today()
    meses = (alvo.year - hoje.year) * 12 + (alvo.month - hoje.month)
    return max(meses, 0)


def analisar_metas(perfil: dict, sobra_mensal: float) -> list[dict]:
    """Para cada meta, calcula quanto falta e o aporte mensal necessário."""
    resultados = []
    reserva_atual = float(perfil.get("reserva_emergencia_atual", 0))
    patrimonio = float(perfil.get("patrimonio_total", 0))

    for meta in perfil.get("metas", []):
        necessario = float(meta["valor_necessario"])
        nome = meta["meta"].lower()

        # Heurística simples para saber o "quanto já tem" de cada meta:
        # metas de reserva usam a reserva atual; demais usam o patrimônio.
        if "reserva" in nome:
            ja_possui = reserva_atual
        else:
            ja_possui = patrimonio

        falta = max(necessario - ja_possui, 0.0)
        meses = _meses_ate(meta.get("prazo", ""))
        aporte_mensal = round(falta / meses, 2) if meses and meses > 0 else None

        viavel = None
        if aporte_mensal is not None:
            viavel = aporte_mensal <= sobra_mensal

        resultados.append(
            {
                "meta": meta["meta"],
                "valor_necessario": round(necessario, 2),
                "ja_possui_estimado": round(ja_possui, 2),
                "falta": round(falta, 2),
                "prazo": meta.get("prazo"),
                "meses_restantes": meses,
                "aporte_mensal_necessario": aporte_mensal,
                "viavel_com_sobra_atual": viavel,
            }
        )
    return resultados


def selecionar_produtos(perfil: dict, produtos: list[dict]) -> list[dict]:
    """Filtra produtos coerentes com o perfil e a tolerância a risco.

    Regra de segurança: se o cliente declara que NÃO aceita risco
    (aceita_risco = false), produtos de risco 'alto' são removidos,
    mesmo que o rótulo do perfil diga 'moderado'. O comportamento
    declarado pesa mais que o rótulo.
    """
    aceita_risco = bool(perfil.get("aceita_risco", False))
    perfil_nome = perfil.get("perfil_investidor", "conservador").lower()

    risco_permitido = {"baixo"}
    if perfil_nome in {"moderado", "arrojado"} and aceita_risco:
        risco_permitido.add("medio")
    if perfil_nome == "arrojado" and aceita_risco:
        risco_permitido.add("alto")

    compativeis = [p for p in produtos if p.get("risco") in risco_permitido]
    # Ordena do menor para o maior aporte mínimo (mais acessível primeiro)
    compativeis.sort(key=lambda p: float(p.get("aporte_minimo", 0)))
    return compativeis


# --------------------------------------------------------------------------- #
# 3. MONTAGEM DO CONTEXTO PARA O LLM
# --------------------------------------------------------------------------- #

def _fmt(v: float) -> str:
    """Formata número como moeda brasileira: 1234.5 -> 'R$ 1.234,50'."""
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def montar_contexto(base: BaseConhecimento) -> str:
    """Gera o bloco de dados factuais que vai junto do system prompt.

    Tudo aqui já vem calculado e formatado. O LLM só precisa ler.
    """
    p = base.perfil
    analise = analisar_transacoes(base.transacoes)
    sobra = analise["saldo"]
    metas = analisar_metas(p, sobra)

    linhas = []
    linhas.append("=== PERFIL DO CLIENTE ===")
    linhas.append(f"Nome: {p.get('nome')}")
    linhas.append(f"Idade: {p.get('idade')} anos")
    linhas.append(f"Profissão: {p.get('profissao')}")
    linhas.append(f"Renda mensal: {_fmt(float(p.get('renda_mensal', 0)))}")
    linhas.append(f"Perfil de investidor (rótulo): {p.get('perfil_investidor')}")
    linhas.append(
        f"Aceita correr risco? {'Sim' if p.get('aceita_risco') else 'Não'}"
    )
    linhas.append(f"Objetivo principal: {p.get('objetivo_principal')}")
    linhas.append(f"Patrimônio total: {_fmt(float(p.get('patrimonio_total', 0)))}")
    linhas.append(
        "Reserva de emergência atual: "
        f"{_fmt(float(p.get('reserva_emergencia_atual', 0)))}"
    )

    linhas.append("\n=== RESUMO FINANCEIRO DO PERÍODO (já calculado) ===")
    linhas.append(f"Total de receitas: {_fmt(analise['receitas'])}")
    linhas.append(f"Total de despesas: {_fmt(analise['despesas'])}")
    linhas.append(f"Saldo (sobra) do período: {_fmt(analise['saldo'])}")
    linhas.append("Gastos por categoria (maior para menor):")
    for cat, val in analise["por_categoria"].items():
        pct = (val / analise["despesas"] * 100) if analise["despesas"] else 0
        linhas.append(f"  - {cat}: {_fmt(val)} ({pct:.0f}% das despesas)")

    linhas.append("\n=== PROGRESSO DAS METAS (já calculado) ===")
    for m in metas:
        linhas.append(f"Meta: {m['meta']}")
        linhas.append(f"  Valor necessário: {_fmt(m['valor_necessario'])}")
        linhas.append(f"  Já possui (estimado): {_fmt(m['ja_possui_estimado'])}")
        linhas.append(f"  Falta: {_fmt(m['falta'])}")
        linhas.append(f"  Prazo: {m['prazo']} ({m['meses_restantes']} meses restantes)")
        if m["aporte_mensal_necessario"] is not None:
            situacao = (
                "dentro da sobra mensal atual"
                if m["viavel_com_sobra_atual"]
                else "ACIMA da sobra mensal atual — exige ajustes"
            )
            linhas.append(
                f"  Aporte mensal necessário: {_fmt(m['aporte_mensal_necessario'])}"
                f" ({situacao})"
            )

    linhas.append("\n=== PRODUTOS COMPATÍVEIS COM O PERFIL ===")
    compat = selecionar_produtos(p, base.produtos)
    if compat:
        for prod in compat:
            linhas.append(
                f"  - {prod['nome']} | risco {prod['risco']} | "
                f"{prod['rentabilidade']} | aporte mínimo "
                f"{_fmt(float(prod['aporte_minimo']))} | {prod['indicado_para']}"
            )
    else:
        linhas.append("  (Nenhum produto compatível encontrado na base.)")

    linhas.append("\n=== PRODUTOS NÃO INDICADOS PARA ESTE PERFIL ===")
    nomes_compat = {p_["nome"] for p_ in compat}
    nao_compat = [x for x in base.produtos if x["nome"] not in nomes_compat]
    for prod in nao_compat:
        linhas.append(f"  - {prod['nome']} (risco {prod['risco']})")

    linhas.append("\n=== HISTÓRICO DE ATENDIMENTOS ===")
    for a in base.atendimentos:
        linhas.append(
            f"  - {a['data']} [{a['canal']}] {a['tema']}: {a['resumo']} "
            f"(resolvido: {a['resolvido']})"
        )

    return "\n".join(linhas)


# --------------------------------------------------------------------------- #
# 4. O AGENTE (conversa com o LLM)
# --------------------------------------------------------------------------- #

SYSTEM_PROMPT = """Você é a Vera, uma consultora financeira virtual do banco.
Seu nome vem de "verdade": você só responde com base em dados reais.

QUEM VOCÊ ATENDE:
Você conversa com o próprio cliente sobre as finanças DELE. Todos os dados
do cliente estão no bloco "CONTEXTO" fornecido a cada conversa.

SEU JEITO DE SER:
- Consultiva, acolhedora e educativa. Explica termos financeiros em
  linguagem simples, como se falasse com quem está começando.
- Proativa: além de responder, aponta oportunidades e riscos que o
  cliente não perguntou, sempre que forem relevantes.
- Objetiva: respostas curtas e organizadas. Use no máximo 1 emoji quando
  fizer sentido, sem exageros.

REGRAS INEGOCIÁVEIS (ANTI-ALUCINAÇÃO):
1. Baseie 100% das respostas nos dados do CONTEXTO. NUNCA invente valores,
   produtos, rentabilidades, taxas ou datas.
2. Todos os cálculos financeiros JÁ ESTÃO PRONTOS no CONTEXTO (saldo,
   gastos por categoria, progresso de metas). Use esses números tais como
   estão. Não refaça contas de cabeça nem estime.
3. Se a informação não estiver no CONTEXTO, diga claramente que você não
   tem esse dado e ofereça uma alternativa. Exemplo: "Não tenho essa
   informação nos seus dados. Posso te ajudar com o resumo dos seus gastos?"
4. Ao recomendar investimentos, use SOMENTE os produtos listados como
   "COMPATÍVEIS COM O PERFIL". Nunca recomende os "NÃO INDICADOS".
5. Você NÃO é um consultor certificado. Sempre que der uma recomendação de
   investimento, feche com um lembrete leve de que são sugestões
   educativas, não garantia de rentabilidade.
6. Você só trata de finanças. Para assuntos fora disso (clima, esportes,
   etc.), recuse educadamente e reconduza para o tema financeiro.
7. Nunca compartilhe ou peça senhas, e nunca fale sobre dados de outros
   clientes — você só conhece os dados deste cliente.

EXEMPLOS DO PADRÃO DE RESPOSTA ESPERADO:

[Pergunta: "Quanto gastei com alimentação?"]
Vera: "Você gastou R$ 570,00 com alimentação no período 🍽️. Isso foi
R$ 450,00 no supermercado e R$ 120,00 no restaurante — cerca de 23% das
suas despesas. É a sua segunda maior categoria de gasto."

[Pergunta: "Onde devo investir?"]
Vera: "Considerando seu objetivo de completar a reserva de emergência e o
fato de você preferir não correr risco, faria sentido começar pelo Tesouro
Selic (risco baixo, rende 100% da Selic, a partir de R$ 30) — ele é indicado
justamente para reserva de emergência. Lembrando que é uma sugestão
educativa, combinado? 😊"

[Pergunta: "Qual a previsão do tempo?"]
Vera: "Eu cuido só das suas finanças, então não tenho como ver o tempo 🙂.
Mas posso te mostrar como está o progresso das suas metas, se quiser."

[Pergunta: "Quanto rende o produto XYZ?"]
Vera: "Não encontrei nenhum produto chamado XYZ na sua base. Os produtos
que tenho disponíveis para o seu perfil são o Tesouro Selic e o CDB
Liquidez Diária. Quer que eu explique algum deles?"
"""


class Vera:
    """Encapsula a conversa: guarda o histórico e fala com o LLM."""

    def __init__(self, base: BaseConhecimento | None = None):
        self.base = base or BaseConhecimento.carregar()
        self.contexto = montar_contexto(self.base)
        self.cliente = OpenAI(
            api_key=config.API_KEY,
            base_url=config.BASE_URL,
        )
        # Histórico de mensagens (sem contar system/contexto, que são fixos)
        self.historico: list[dict] = []

    def _mensagens(self, pergunta: str) -> list[dict]:
        system = f"{SYSTEM_PROMPT}\n\n=== CONTEXTO (dados reais do cliente) ===\n{self.contexto}"
        return (
            [{"role": "system", "content": system}]
            + self.historico
            + [{"role": "user", "content": pergunta}]
        )

    def responder(self, pergunta: str) -> str:
        """Envia a pergunta ao LLM e devolve a resposta da Vera."""
        try:
            resp = self.cliente.chat.completions.create(
                model=config.MODELO,
                messages=self._mensagens(pergunta),
                temperature=0.3,  # baixa = mais previsível, menos "criativa"
                max_tokens=600,
            )
            resposta = resp.choices[0].message.content.strip()
        except Exception as e:  # noqa: BLE001
            return (
                "Ops, tive um problema para me conectar ao serviço de IA. "
                f"Verifique sua API key e conexão. (Detalhe técnico: {e})"
            )

        # Atualiza o histórico para dar memória de contexto à conversa
        self.historico.append({"role": "user", "content": pergunta})
        self.historico.append({"role": "assistant", "content": resposta})
        return resposta

    def resumo_rapido(self) -> dict:
        """Métricas prontas para exibir na interface (sem chamar o LLM)."""
        analise = analisar_transacoes(self.base.transacoes)
        metas = analisar_metas(self.base.perfil, analise["saldo"])
        return {"analise": analise, "metas": metas, "perfil": self.base.perfil}


# --------------------------------------------------------------------------- #
# Execução direta no terminal (modo CLI, sem interface gráfica)
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    print("=" * 60)
    print("VERA — Assistente Financeira Inteligente (modo terminal)")
    print("Digite 'sair' para encerrar.")
    print("=" * 60)

    vera = Vera()
    print("\n[Contexto carregado com sucesso]\n")

    while True:
        try:
            pergunta = input("Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if pergunta.lower() in {"sair", "exit", "quit"}:
            break
        if not pergunta:
            continue
        print(f"\nVera: {vera.responder(pergunta)}\n")

    print("Até logo! 👋")
