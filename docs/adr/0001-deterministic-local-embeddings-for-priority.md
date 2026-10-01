---
status: accepted
---

# Priorização de reuniões por tópico usa embeddings locais determinísticos, não um LLM

Para calcular a relevância de uma reunião frente aos tópicos de interesse do usuário, consideramos duas rotas: pedir a um LLM para julgar relevância (como já é feito para gerar `simple_summary`/`keywords`), ou calcular embeddings localmente (modelo multilíngue offline, sem chamada externa) e comparar por similaridade de cosseno. Escolhemos embeddings locais porque a prioridade precisa ser **reproduzível e auditável** — o mesmo tópico contra a mesma reunião sempre produz o mesmo score, sem custo por chamada, sem latência de rede e sem depender de disponibilidade de um provedor externo (diferente do restante do pipeline de resumo, que já depende do OpenRouter). O trade-off aceito é que embeddings capturam similaridade semântica geral, mas são menos flexíveis que um LLM para julgar relevância contextual sutil.

## Consequences

- Nova coluna `topic_embedding` em `meeting_summaries`, calculada no sync/upload e recalculada quando `keywords`/`simple_summary` mudam.
- Nova dependência de modelo de embeddings local (multilíngue) no `resume-ai-service`, distinta do fluxo de LLM via OpenRouter usado pelo resto do sistema.
- Cortes de score/tier (`urgent ≥ 70`, `high ≥ 40`) são constantes ajustáveis, não uma escala validada empiricamente — esperado recalibrar após ver dados reais.

## Revisions

- **Transcript evidence (after ADR-0002).** The score no longer reads only the `title + summary + keywords` embedding, which hid topics discussed in a meeting but left out of its 70-word summary (e.g. all six meetings that mention "JGB" scored Routine). Per topic it now combines the overview similarity, the mean similarity of the meeting's best three transcript chunks, and the number of transcript lines that name the topic as a whole word (composite topics such as "Fed & Rates" are split into their parts). One mention guarantees High; Urgent from mentions alone needs five lines. See `priority.combine` and `retrieval.topic_evidence`. It stays deterministic, local and LLM-free; thresholds are unchanged, and an unindexed meeting keeps the summary-only score.
- The response carries `priority_reason` (topic, mentioned/discussed/summary, mention count, and the cue it came from), so the UI can say why a meeting was flagged and open it at that moment.
