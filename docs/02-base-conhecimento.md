# Base de Conhecimento

## Dados Utilizados

Foram usados os quatro arquivos da pasta `data/`, sem substituir nenhum
deles — o objetivo é mostrar como o agente extrai valor dos dados mockados
originais do desafio.

| Arquivo | Formato | Utilização no Agente |
|---------|---------|---------------------|
| `perfil_investidor.json` | JSON | Personaliza tudo: renda, objetivo, tolerância a risco e metas. É a base das recomendações e da coerência das respostas. |
| `transacoes.csv` | CSV | Calcula receitas, despesas, saldo do período e gastos por categoria. |
| `produtos_financeiros.json` | JSON | Fonte única de produtos que a Vera pode recomendar. Filtrados por risco compatível com o perfil. |
| `historico_atendimento.csv` | CSV | Contextualiza interações anteriores (ex.: cliente já perguntou sobre CDB e Tesouro Selic), permitindo continuidade. |

---

## Adaptações nos Dados
Os dados **não foram alterados**. Todo o enriquecimento acontece em tempo de
execução, na camada de análise (`agente.py`):

- as transações viram um **resumo por categoria** com percentuais;
- o perfil + as metas viram um **cálculo de progresso** (quanto falta, em
  quantos meses, qual aporte mensal necessário e se ele cabe na sobra atual);
- os produtos são **filtrados e ordenados** por compatibilidade de risco e
  acessibilidade (menor aporte mínimo primeiro).

Isso mantém a base simples e auditável, e concentra a inteligência no código.

---

## Estratégia de Integração

### Como os dados são carregados?
No início da sessão, a classe `BaseConhecimento.carregar()` lê os quatro
arquivos de `data/` para a memória. Os CSVs são lidos com `csv.DictReader`
(encoding `utf-8-sig`, para lidar com BOM) e os JSONs com `json.load`.

### Como os dados são usados no prompt?
Esta é uma abordagem **híbrida (código + contexto)**, mais robusta que jogar
o JSON cru no prompt:

1. **A camada determinística calcula os números primeiro.** Nenhuma conta é
   deixada para o LLM.
2. **O resultado vira um bloco de texto factual** (função `montar_contexto`),
   já formatado em moeda brasileira e organizado em seções.
3. **Esse bloco é anexado ao system prompt** a cada conversa, junto das
   regras de comportamento. O LLM recebe dados prontos e só precisa
   interpretar e comunicar.

Vantagens: elimina erros de cálculo, reduz alucinação, economiza tokens
(enviamos um resumo, não a base inteira) e torna as respostas auditáveis —
dá para conferir cada número no código.

---

## Exemplo de Contexto Montado
Trecho real do contexto gerado pelo `agente.py` a partir dos dados do João:

```
=== PERFIL DO CLIENTE ===
Nome: João Silva
Idade: 32 anos
Profissão: Analista de Sistemas
Renda mensal: R$ 5.000,00
Perfil de investidor (rótulo): moderado
Aceita correr risco? Não
Objetivo principal: Construir reserva de emergência
Patrimônio total: R$ 15.000,00
Reserva de emergência atual: R$ 10.000,00

=== RESUMO FINANCEIRO DO PERÍODO (já calculado) ===
Total de receitas: R$ 5.000,00
Total de despesas: R$ 2.488,90
Saldo (sobra) do período: R$ 2.511,10
Gastos por categoria (maior para menor):
  - moradia: R$ 1.380,00 (55% das despesas)
  - alimentacao: R$ 570,00 (23% das despesas)
  - transporte: R$ 295,00 (12% das despesas)
  - saude: R$ 188,00 (8% das despesas)
  - lazer: R$ 55,90 (2% das despesas)

=== PROGRESSO DAS METAS (já calculado) ===
Meta: Completar reserva de emergência
  Valor necessário: R$ 15.000,00
  Já possui (estimado): R$ 10.000,00
  Falta: R$ 5.000,00
  ...

=== PRODUTOS COMPATÍVEIS COM O PERFIL ===
  - Tesouro Selic | risco baixo | 100% da Selic | aporte mínimo R$ 30,00 | ...
  - CDB Liquidez Diária | risco baixo | 102% do CDI | aporte mínimo R$ 100,00 | ...
  - LCI/LCA | risco baixo | 95% do CDI | aporte mínimo R$ 1.000,00 | ...

=== PRODUTOS NÃO INDICADOS PARA ESTE PERFIL ===
  - Fundo Multimercado (risco medio)
  - Fundo de Ações (risco alto)
```

> Note que os fundos de risco médio/alto aparecem numa lista separada de
> "não indicados" — isso impede a Vera de recomendá-los para um cliente que
> declarou não aceitar risco, reforçando a coerência.
