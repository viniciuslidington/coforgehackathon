---
status: accepted
---

# Quick Chat usa evidências pré-indexadas e recuperação híbrida antes da síntese

O Quick Chat precisa responder tanto investigações direcionadas quanto sínteses abrangentes sem enviar todas as transcrições ao LLM. Escolhemos preparar, durante a ingestão, captions normalizadas, chunks com embeddings e Meeting Briefs ligados às evidências; na pergunta, uma camada determinística aplica o meeting scope e combina busca lexical e semântica, enquanto um agente fino classifica a intenção, planeja a recuperação e sintetiza apenas o material permitido. O trade-off aceito é aumentar o custo e a complexidade da ingestão para reduzir latência, custo de tokens e risco de respostas sem sustentação.

## Consequences

- Investigações direcionadas recuperam poucas reuniões e trechos relevantes; sínteses abrangentes processam todas as reuniões do meeting scope em lotes, sem usar `top-k` como substituto de cobertura.
- Afirmações factuais carregam Evidence references verificáveis; Meeting Briefs aceleram a busca, mas nunca substituem o transcript como evidência.
- O LLM não executa consultas irrestritas nem recebe transcrições completas por padrão; filtros de escopo, limites e acesso permanecem determinísticos.
- A ingestão precisa expor um estado de indexação e permitir reprocessamento idempotente quando chunking, embeddings ou extrações mudarem.
