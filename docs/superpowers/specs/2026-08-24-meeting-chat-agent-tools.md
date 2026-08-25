# Feature Spec: Agente de Chat por Reunião com Tools

**Projeto:** Shift Briefing — Meeting Insights (FastAPI + LangGraph / Next.js)
**Status:** Draft para hackathon (MVP)
**Escopo:** Chat modal por-reunião (`MeetingDetailModal` / `DetailChat`, já conectado ao backend). O `quick-chat` mockado (chat global/cross-meeting) **não** faz parte deste plano.

---

## Objetivo

Transformar o chat por-reunião de uma chamada única de LLM (transcript inteira + pergunta → resposta) num **agente com tools**, capaz de:

1. Responder com mais precisão sobre o que foi dito na reunião (busca literal, filtro por falante, metadados), reduzindo alucinação em citações/números.
2. Enriquecer a resposta com **contexto externo real** (cotação de mercado, notícia recente, análise geopolítica) quando a reunião menciona um ativo/empresa — algo que hoje é impossível, já que o agente só enxerga a transcript.
3. Manter memória de conversa dentro de uma sessão de chat (perguntas de acompanhamento funcionam).
4. Mostrar ao usuário, em tempo real, o que o agente está fazendo (trace de passos) enquanto processa a pergunta.

## Fora de escopo (este MVP)

- **Chat cross-meeting / agente global** — o `quick-chat` mockado vira essa feature depois; usa embeddings (via módulo que o workstream de priorização está construindo em paralelo). Não confundir com este plano.
- **Chunking/embeddings da transcript** — a transcript inteira continua indo pro contexto, como hoje (mediana de reunião: ~13min, cabe folgado). Busca semântica dentro da própria reunião fica de fora.
- **`get_transcript_segment(início, fim)`** — redundante com a transcript já estar inteira no contexto; `search_transcript_keyword` cobre o caso de uso real.
- **Extração estruturada sob demanda** (`extract_action_items`, `extract_decisions`, etc.) — fase 2 natural do mesmo scaffolding agentic, não bloqueia esta v1.
- **Persistência formal de `Topic`** (a entidade de `CONTEXT.md` usada na priorização) — este chat não pede tópico ao usuário, o agente decide sozinho quando buscar dado externo.

---

## Arquitetura

```
Next.js (client)                                         FastAPI (resume-ai-service)
─────────────────                                        ───────────────────────────
MeetingDetailModal                                        meeting_summaries.router
  └─ DetailChat (trace de passos + mensagens)                │
       │                                                     ▼
useMeetingDetail.ts ──session_id, question──▶  POST /meeting-summaries/{id}/questions  (SSE)
       │   (fetch + ReadableStream, parse SSE manualmente)    │
       ▼                                                      ▼
  steps: string[]  ◀── evento "step" por tool executada   graphs/meeting_chat/graph.py
  answer: string   ◀── evento final "answer"                │  (agent → tools → agent, LangGraph)
                                                              │
                                    ┌─────────────────────────┼─────────────────────────┐
                                    ▼                         ▼                          ▼
                          tools.py (determinísticas)   services/finnhub_service.py   SqliteSaver
                          metadata / keyword / speaker  quote / news / symbol         (session_id → histórico,
                                                         + cache TTL em memória        persistido em
                                                                                       meeting_insights.db)
```

**Regra de seam:** só `services/finnhub_service.py` conhece a API do Finnhub — o `graph.py`/`tools.py` só chamam funções tipadas (`get_quote`, `search_symbol`, `get_news`), sem saber de HTTP/headers/rate-limit. Mesmo princípio de seam único já usado em `priority.py` (spec irmã).

---

## Backend

### `app/graphs/meeting_chat/` (reescrito)

- **`state.py`** — `ChatState` ganha `messages: Annotated[list[BaseMessage], add_messages]` (padrão LangGraph para histórico gerenciado pelo checkpointer) além dos campos já existentes (`meeting_id`, `transcript`).
- **`graph.py`** — vira um grafo de três nodes: `agent` (LLM com `bind_tools`), `tools` (`ToolNode`) e `synthesize` (resposta final sem tools). A aresta condicional volta de `tools` para `agent` enquanto houver tool calls; quando o agente não pedir mais tools, segue para `synthesize`, que transforma o rascunho/raciocínio e as evidências em uma resposta exclusivamente user-facing. Compilado com `checkpointer=SqliteSaver` (ver abaixo), `thread_id=session_id`.
- **`tools.py`** — implementa as 7 tools (ver seção Tools).
- **`nodes.py`** — node do agente principal, node de síntese da resposta final e node dedicado de síntese geopolítica (`get_geopolitical_analysis` roda sua própria chamada LLM focada, não reaproveita o histórico da conversa principal). O rascunho do agente nunca é enviado ao frontend e é substituído pela resposta sintetizada no histórico persistido.
- **`prompts.py`** — prompt atual mantido (atribuição por falante/timestamp) **+** nova regra: toda informação vinda de tool externa (Finnhub) deve ser citada explicitamente como tal (fonte + momento), nunca misturada sem distinção com o que foi dito na reunião.

### Tools (`app/graphs/meeting_chat/tools.py`)

**Determinísticas — sem LLM, sem rede externa, operam sobre `state["transcript"]`/captions já carregadas:**

| Tool | Faz |
|---|---|
| `get_meeting_metadata()` | Participantes, data, duração, keywords da reunião atual |
| `search_transcript_keyword(termo)` | Busca literal (case-insensitive) por trecho/citação exata, retorna com timestamp |
| `get_statements_by_speaker(nome)` | Filtra falas de um participante específico |

**Externas — via `finnhub_service.py`, com fallback gracioso:**

| Tool | Faz |
|---|---|
| `resolve_symbol(nome)` | Nome em linguagem natural → ticker, via endpoint de busca de símbolo do Finnhub |
| `get_market_quote(ticker)` | Cotação/variação atual |
| `get_market_news(ticker_ou_termo)` | Notícias recentes relacionadas |
| `get_geopolitical_analysis(ativo_ou_tema)` | Chama `get_market_news` internamente, depois roda uma síntese LLM dedicada (chamada própria, focada) sobre os artigos reais retornados — produz um parecer geopolítico curto ancorado em notícia real, não em conhecimento estático do modelo |

Toda tool externa: timeout curto (ex: 5s), captura exceção/timeout e retorna um resultado estruturado tipo `{"ok": False, "reason": "..."}` em vez de propagar erro — o agente principal decide como comunicar isso na resposta (nunca derruba a requisição inteira).

### `app/services/finnhub_service.py` (novo)

- Client fino sobre a API REST do Finnhub (`httpx`, chave via `FINNHUB_API_KEY`).
- `search_symbol(query) -> str | None`, `get_quote(ticker) -> dict | None`, `get_news(ticker_or_term) -> list[dict]`.
- Cache em memória com TTL curto (ex: 5 min), chave = (função, argumento normalizado) — protege contra rate limit do free tier em perguntas repetidas na mesma demo.

### `app/core/config.py`

- `FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")` — novo.
- `OPENROUTER_MODEL` — valor recomendado no `.env`: `meta-llama/llama-3.3-70b-instruct:free` (tool-calling confirmado, bom em PT-BR), no lugar do router aleatório `openrouter/free` (tem bug documentado de falhar tool-calling ao sortear modelo sem suporte).

### Sessão / memória (`SqliteSaver`)

- `graphs/meeting_chat/graph.py` compila com `checkpointer=SqliteSaver.from_conn_string(DATABASE_PATH)` (pacote `langgraph-checkpoint-sqlite`) — reaproveita o mesmo `meeting_insights.db`, sem tabela desenhada à mão (o checkpointer gerencia seu próprio schema).
- `thread_id` = `session_id` recebido do frontend.
- Sem expiração/limpeza explícita de sessão neste MVP — linhas órfãs acumulam no banco após o modal fechar; aceitável pro escopo de PoC/demo.

### `app/routers/meeting_summaries.py`

- `POST /meeting-summaries/{meeting_id}/questions` **substituído** (não duplicado — único consumidor real é `DetailChat`) por uma versão que retorna `StreamingResponse(media_type="text/event-stream")`.
- Request (`QuestionRequest`) ganha `session_id: str`.
- Stream: itera `graph.stream(..., stream_mode="updates")`; a cada node executado, emite `data: {"type": "step", "label": "<label amigável>"}\n\n` (mapeamento nome-do-node → label em `prompts.py` ou `nodes.py`); somente a saída de `synthesize` gera o evento final `data: {"type": "answer", "text": "...", "caption_count": N}\n\n`.
- Erro de tool não interrompe o stream — vira parte do reasoning do agente (fallback gracioso já tratado na tool). Erro de infraestrutura (OpenRouter fora do ar) ainda pode emitir um evento `{"type": "error", "detail": "..."}` antes de fechar o stream.

### `app/schemas/agent.py`

- `QuestionRequest` ganha `session_id: str`.
- (Opcional, só documentação) modelos `StepEvent`/`AnswerEvent`/`ErrorEvent` descrevendo o payload de cada linha SSE — não precisam virar `response_model` do FastAPI já que streaming não usa validação de schema Pydantic na resposta.

---

## Frontend

### `src/shared/api/meetings.ts`

- `askMeetingQuestion` (ou uma nova função) passa a usar `fetch()` + leitura manual de `ReadableStream`, parseando frames `data: {...}\n\n` (não dá pra usar `EventSource` nativo porque a requisição é `POST` com corpo) — expõe um callback/async-generator que emite `step` e `answer`/`error` conforme chegam.

### `src/features/call-detail/model/useMeetingDetail.ts`

- `openMeeting()`: gera `session_id` novo via `crypto.randomUUID()`, guarda em estado, zera `steps`.
- `sendMessage()`: em vez de `.then()` único, consome o stream — cada evento `step` empurra pro array `steps: string[]`; evento `answer` substitui o placeholder pela resposta final (e limpa `steps` ou mantém como trace colapsável, a decidir na implementação); evento `error` vira mensagem de erro como já acontece hoje.
- `closeMeeting()`: comportamento atual mantido (limpa estado local; sessão persistida no backend não é deletada).

### `src/features/call-detail/ui/DetailChat.tsx`

- Renderiza `steps` como uma lista/trace visual enquanto `asking` está `true` (ex: "🔍 Buscando símbolo…", "📰 Lendo notícias…"), substituída pela bolha de resposta quando o evento final chega.

## Critérios de aceitação

- [ ] Perguntar algo respondível só pela transcript retorna resposta correta sem chamar nenhuma tool externa
- [ ] Perguntar algo que envolve um ativo/empresa mencionado na reunião aciona `resolve_symbol` → `get_market_quote`/`get_market_news`, e a resposta cita explicitamente que aquele dado é externo (fonte + momento), distinto do que foi dito na reunião
- [ ] Falha simulada do Finnhub (ex: chave inválida) não derruba a resposta — o agente responde com o que tem da transcript e menciona que não conseguiu buscar o dado externo
- [ ] Pergunta de acompanhamento ("e sobre isso que você falou?") na mesma sessão usa o histórico corretamente
- [ ] Reiniciar o servidor backend não apaga o histórico de uma sessão em andamento (verificação da persistência via `SqliteSaver`)
- [ ] Durante o processamento de uma pergunta, a UI mostra passos em tempo real (não só "Thinking…" estático) antes da resposta final aparecer
- [ ] Perguntar a mesma coisa duas vezes em sequência não estoura rate limit do Finnhub (cache TTL funcionando)

## Testes

Sem suíte automatizada neste MVP — verificação manual: rodar os critérios de aceitação acima manualmente, incluindo teste de falha proposital do Finnhub (chave errada) pra confirmar degradação graciosa, e teste de restart do backend no meio de uma sessão pra confirmar persistência.
