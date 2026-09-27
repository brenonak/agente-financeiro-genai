"""
app.py — Interface do chat da Vera em Streamlit.

Como rodar:
    pip install -r requirements.txt
    (copie .env.example para .env e preencha a API key)
    streamlit run app.py
"""

import streamlit as st

from agente import Vera, _fmt

st.set_page_config(page_title="Vera — Assistente Financeira", page_icon="💰")


# --------------------------------------------------------------------------- #
# Inicialização (uma única vez por sessão)
# --------------------------------------------------------------------------- #

@st.cache_resource
def carregar_vera() -> Vera:
    return Vera()


vera = carregar_vera()

if "mensagens" not in st.session_state:
    st.session_state.mensagens = [
        {
            "role": "assistant",
            "content": (
                f"Olá, {vera.base.perfil.get('nome', '').split(' ')[0]}! "
                "Eu sou a Vera, sua consultora financeira 💰\n\n"
                "Posso te mostrar seus gastos, o progresso das suas metas e "
                "sugerir investimentos compatíveis com o seu perfil. "
                "O que você gostaria de saber?"
            ),
        }
    ]


# --------------------------------------------------------------------------- #
# Barra lateral — painel do cliente (dados já calculados, sem LLM)
# --------------------------------------------------------------------------- #

with st.sidebar:
    st.header("👤 Painel do Cliente")
    resumo = vera.resumo_rapido()
    perfil = resumo["perfil"]
    analise = resumo["analise"]

    st.markdown(f"**{perfil.get('nome')}**")
    st.caption(
        f"{perfil.get('idade')} anos · {perfil.get('profissao')} · "
        f"perfil {perfil.get('perfil_investidor')}"
    )

    st.divider()
    st.subheader("Resumo do período")
    st.metric("Receitas", _fmt(analise["receitas"]))
    st.metric("Despesas", _fmt(analise["despesas"]))
    st.metric("Sobra", _fmt(analise["saldo"]))

    st.subheader("Gastos por categoria")
    st.bar_chart(analise["por_categoria"])

    st.subheader("Metas")
    for m in resumo["metas"]:
        pct = 0
        if m["valor_necessario"]:
            pct = min(m["ja_possui_estimado"] / m["valor_necessario"], 1.0)
        st.markdown(f"**{m['meta']}**")
        st.progress(pct, text=f"{pct*100:.0f}% — falta {_fmt(m['falta'])}")

    st.divider()
    st.caption(
        "⚠️ Dados fictícios de cliente para fins do desafio. "
        "As sugestões são educativas, não recomendação de investimento."
    )


# --------------------------------------------------------------------------- #
# Área principal — chat
# --------------------------------------------------------------------------- #

st.title("💬 Converse com a Vera")

# Sugestões clicáveis de perguntas
st.caption("Sugestões de perguntas:")
sugestoes = [
    "Quanto gastei com alimentação?",
    "Qual investimento você recomenda para mim?",
    "Como está o progresso da minha reserva de emergência?",
    "Onde estou gastando mais?",
]
cols = st.columns(2)
pergunta_clicada = None
for i, s in enumerate(sugestoes):
    if cols[i % 2].button(s, use_container_width=True):
        pergunta_clicada = s

# Mostra o histórico
for msg in st.session_state.mensagens:
    avatar = "💰" if msg["role"] == "assistant" else "🧑"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

# Entrada do usuário (campo ou botão de sugestão)
pergunta = st.chat_input("Digite sua pergunta sobre finanças...") or pergunta_clicada

if pergunta:
    st.session_state.mensagens.append({"role": "user", "content": pergunta})
    with st.chat_message("user", avatar="🧑"):
        st.markdown(pergunta)

    with st.chat_message("assistant", avatar="💰"):
        with st.spinner("Vera está analisando seus dados..."):
            resposta = vera.responder(pergunta)
        st.markdown(resposta)

    st.session_state.mensagens.append({"role": "assistant", "content": resposta})
