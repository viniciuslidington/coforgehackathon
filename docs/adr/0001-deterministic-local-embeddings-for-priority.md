---
status: accepted
---

# Priorização de reuniões por tópico usa embeddings locais determinísticos, não um LLM

Para calcular a relevância de uma reunião frente aos tópicos de interesse do usuário, consideramos duas rotas: pedir a um LLM para julgar relevância (como já é feito para gerar `simple_summary`/`keywords`), ou calcular embeddings localmente (modelo multilíngue offline, sem chamada externa) e comparar por similaridade de cosseno. Escolhemos embeddings locais porque a prioridade precisa ser **reproduzível e auditável** — o mesmo tópico contra a mesma reunião sempre produz o mesmo score, sem custo por chamada, sem latência de rede e sem depender de disponibilidade de um provedor externo (diferente do restante do pipeline de resumo, que já depende do OpenRouter). O trade-off aceito é que embeddings capturam similaridade semântica geral, mas são menos flexíveis que um LLM para julgar relevância contextual sutil.

## Consequences

- Nova coluna `topic_embedding` em `meeting_summaries`, calculada no sync/upload e recalculada quando `keywords`/`simple_summary` mudam.
- Nova dependência de modelo de embeddings local (multilíngue) no `resume-ai-service`, distinta do fluxo de LLM via OpenRouter usado pelo resto do sistema.
- Cortes de score/tier (`urgent ≥ 70`, `high ≥ 40`) são constantes ajustáveis, não uma escala validada empiricamente — esperado recalibrar após ver dados reais.
