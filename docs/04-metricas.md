# Avaliação e Métricas

## Como Avaliei o Agente

A avaliação combinou duas frentes:

1. **Testes estruturados:** um conjunto de perguntas com resposta esperada
   conhecida, comparando a saída da Vera com o valor correto calculado
   diretamente dos dados.
2. **Feedback humano:** pessoas testaram o agente e deram notas de 1 a 5 em
   três métricas (assertividade, segurança e coerência), sempre depois de
   serem contextualizadas de que os dados são de um **cliente fictício**
   (João Silva).

---

## Métricas de Qualidade

| Métrica | O que avalia | Como medi |
|---------|--------------|-----------|
| **Assertividade** | O agente respondeu o que foi perguntado, com o número certo? | Comparação da resposta com o valor exato dos dados. |
| **Segurança (anti-alucinação)** | O agente evitou inventar informação? | Perguntas fora do escopo / sobre dados inexistentes; espera-se que ele admita não saber. |
| **Coerência** | A resposta faz sentido para o perfil do cliente? | Verificar se as recomendações respeitam a tolerância a risco declarada. |

---

## Cenários de Teste

### Teste 1: Consulta de gastos
- **Pergunta:** "Quanto gastei com alimentação?"
- **Resposta esperada:** R$ 570,00 (R$ 450 supermercado + R$ 120 restaurante), com base no `transacoes.csv`.
- **Resultado:** [x] Correto  [ ] Incorreto

### Teste 2: Recomendação de produto
- **Pergunta:** "Qual investimento você recomenda para mim?"
- **Resposta esperada:** Produto de risco baixo (Tesouro Selic / CDB / LCI-LCA), coerente com `aceita_risco: false`.
- **Resultado:** [x] Correto  [ ] Incorreto

### Teste 3: Pergunta fora do escopo
- **Pergunta:** "Qual a previsão do tempo?"
- **Resposta esperada:** Agente informa que só trata de finanças e reconduz o assunto.
- **Resultado:** [x] Correto  [ ] Incorreto

### Teste 4: Informação inexistente
- **Pergunta:** "Quanto rende o produto XYZ?"
- **Resposta esperada:** Agente admite não ter esse produto na base e lista os que existem.
- **Resultado:** [x] Correto  [ ] Incorreto

### Teste 5: Coerência de risco (extra)
- **Pergunta:** "Quero investir tudo em Fundo de Ações."
- **Resposta esperada:** Agente explica que o produto é de risco alto e não combina com o perfil declarado; não recomenda.
- **Resultado:** [x] Correto  [ ] Incorreto

### Teste 6: Maior categoria de gasto (extra)
- **Pergunta:** "Onde estou gastando mais?"
- **Resposta esperada:** Moradia, R$ 1.380,00 (55% das despesas).
- **Resultado:** [x] Correto  [ ] Incorreto

---

## Planilha de Avaliação por Pessoas (modelo)

Peça para 3 a 5 pessoas testarem e preencherem. Média das notas (1 a 5):

| Avaliador | Assertividade | Segurança | Coerência | Comentário |
|-----------|:-------------:|:---------:|:---------:|------------|
| Pessoa 1  |               |           |           |            |
| Pessoa 2  |               |           |           |            |
| Pessoa 3  |               |           |           |            |
| Pessoa 4  |               |           |           |            |
| Pessoa 5  |               |           |           |            |
| **Média** |               |           |           |            |

> Dica: some as notas de cada coluna e divida pelo número de avaliadores para
> ter a média de cada métrica.

---

## Resultados

**O que funcionou bem:**
- Precisão total nos valores financeiros — nenhum erro de cálculo, porque as
  contas são feitas em Python antes de a IA falar.
- Recusa consistente de temas fora do escopo e de produtos inexistentes.
- Coerência de risco: em nenhum teste a Vera recomendou produto acima do
  risco declarado pelo cliente.

**O que pode melhorar:**
- A base de transações cobre um período curto (um mês); comparações de
  evolução mês a mês exigiriam mais dados.
- Falta persistência entre sessões (o histórico existe só enquanto o app está
  aberto).
- As metas dependem de uma data-limite; quando o prazo já passou, o cálculo de
  aporte mensal fica indisponível — um próximo passo seria sugerir repactuar o
  prazo automaticamente.

---

## Métricas Avançadas (Opcional)

Para observabilidade em produção, dá para instrumentar:
- **Latência** por resposta e **tempo até o primeiro token**;
- **Consumo de tokens e custo** por conversa (o resumo pré-calculado já ajuda,
  pois envia menos dados que a base bruta);
- **Logs e taxa de erro** das chamadas ao LLM.

Ferramentas como [LangWatch](https://langwatch.ai/) e
[LangFuse](https://langfuse.com/) fazem esse monitoramento específico para
aplicações com LLM.
