# Feature Spec: Priorização de Reuniões por Tópico

**Projeto:** Shift Briefing — Meeting Insights (FastAPI + LangGraph / Next.js)
**Status:** Draft para hackathon (MVP)
**Vocabulário:** ver [`CONTEXT.md`](../../../CONTEXT.md) — `Topic`, `Priority score`, `Priority tier`, `Meeting embedding`
**Decisão de arquitetura:** ver [ADR-0001](../../adr/0001-deterministic-local-embeddings-for-priority.md)

---

## Objetivo

O usuário define tópicos de interesse (ex: "orçamento", "cliente X", "prazo") e o sistema calcula, para cada reunião, quão relevante ela é frente a esses tópicos — de forma **determinística**, sem IA generativa. O resultado orienta o que merece atenção primeiro, sem esconder nada da lista.

## Fora de escopo (este MVP)

- Filtro que esconde reuniões não relevantes (tópico só rotula/ordena, nunca remove da lista) — pode virar feature separada depois
- Filtro por colunas existentes (data, participantes, etc.) — feature própria, não misturar com prioridade por tópico
- `CallFlag` / sort por `'mentions'` — legado do mock antigo (`entities/call`), não portado
- Persistência de tópicos por usuário — não existe conceito de usuário/autenticação hoje; tópicos são passados por requisição (cache opcional em `localStorage`)
- Matching contra transcript completo (`captions_json`) — ainda não implementado em outro spec; este MVP usa `title` + `simple_summary` + `keywords`

---

## Arquitetura

```
Next.js (client)                                    FastAPI (resume-ai-service)
─────────────────                                   ───────────────────────────
CallHistory ──topics (session)────▶ shared/api/meetings.ts ──▶ meeting_summaries.router
  │                                                              │        │
  ├─ PriorityBadge (por linha, se topics ativo)                 ▼        ▼
  └─ sort seletor ('priority' | 'time')                   database.py  priority.py
                                                          (topic_embedding  (novo módulo —
                                                           BLOB column)      único que conhece
                                                                             o modelo de embedding)
```

**Regra de seam única:** `priority.py` é o único módulo do backend que sabe que existe um modelo de embeddings — nem `graph.py` (que só conhece o LLM via OpenRouter) nem `database.py` (que só conhece o formato de armazenamento) importam o modelo diretamente.

---

## Mudança de schema

`meeting_summaries` ganha:

- `topic_embedding BLOB` — vetor do modelo multilíngue local, serializado (ex: `float32` packed), calculado sobre `title + simple_summary + keywords`.

Recalculado sempre que `upsert_summary` roda para aquele `meeting_id` com `simple_summary`/`keywords` diferentes do valor já persistido (mesmo gatilho do sync/upload existente — não é um job separado).

---

## Backend

### `app/services/priority.py` (novo)

- Carrega o modelo de embeddings multilíngue local uma vez (singleton), sem chamada externa.
- `embed(text: str) -> np.ndarray` — usado tanto para a reunião (no sync/upload) quanto para o tópico (por requisição).
- `topic_embedding_cache: dict[str, np.ndarray]` — cache em memória por texto de tópico normalizado (lowercase, trim), evita recalcular o mesmo tópico repetidamente entre requisições.
- `score(meeting_vec, topic_vecs: list[np.ndarray]) -> float` — cosseno contra cada tópico, retorna o **máximo** (Q6 do grill).
- `tier(score_0_100: float) -> Literal['urgent', 'high', 'normal']` — cortes `urgent ≥ 70`, `high ≥ 40`, como constantes nomeadas em `priority.py`, fáceis de recalibrar.

### `database.py`

- `upsert_summary` passa a calcular e persistir `topic_embedding` (via `priority.embed`) quando o conteúdo relevante muda.
- Novo: `list_summaries_with_priority(topics: list[str] | None, ...)` — quando `topics` é passado, calcula o score de cada reunião candidata **antes** de paginar (Q13), ordena se `sort='priority'`, então pagina.

### `app/routers/meeting_summaries.py`

- `GET /meeting-summaries` ganha query param opcional `topics: list[str]`. Quando ausente, comportamento idêntico ao atual (sem `priority_score`/`priority_tier` no payload). Quando presente, cada item da página inclui `priority_score: float` e `priority_tier: Literal['urgent','high','normal']`.

### Schemas (`app/schemas/meetings.py`)

- `StoredMeetingSummary` ganha campos opcionais `priority_score: float | None`, `priority_tier: Literal['urgent','high','normal'] | None` — `None` quando não há tópico ativo (Q10).

---

## Frontend

### Migração de `entities/call` → `entities/meeting`

- Mover `Priority`, `score`, `tier`, `SortKey` (agora só `'priority' | 'time'`) para `src/entities/meeting/model/types.ts`, tipados sobre `MeetingSummary`.
- Mover `PriorityBadge` (componente + CSS module) para `src/entities/meeting/ui/`, adaptado para receber `priority_score`/`priority_tier` de `MeetingSummary` (`undefined` → não renderiza nada).
- `sortCalls` vira `sortMeetings`, mesma lógica, tipos atualizados.
- Deletar `src/entities/call/` inteiro após a migração (mocks, `CallFlag`, `CallSegment`/`Call` types, dados fixture) — legado confirmado sem uso futuro (Q9).

### `src/shared/api/meetings.ts`

- `fetchMeetingSummaries` ganha parâmetro opcional `topics?: string[]`, propagado como query param.

### UI

- Um input de tópicos (session-state, `page.tsx` ou `CallHistory`), opcionalmente espelhado em `localStorage` para persistir entre reloads do navegador (não entre dispositivos/usuários).
- `CallRow` renderiza `PriorityBadge` só quando `priority_tier` não é `null`/`undefined`.
- Seletor de sort existente passa a ter `'priority'` funcional quando há tópicos ativos (antes, sem dado real, era mock).

---

## Critérios de aceitação

- [ ] Definir um tópico e consultar a lista retorna `priority_score`/`priority_tier` por reunião, calculado sem nenhuma chamada a LLM
- [ ] O mesmo tópico contra a mesma reunião sempre produz o mesmo score (determinismo verificável rodando duas vezes)
- [ ] Reunião com múltiplos tópicos batendo usa o **maior** score entre eles, não a média
- [ ] Sem tópico ativo, nenhuma reunião mostra badge de prioridade
- [ ] Ordenar por prioridade com resultado paginado traz a reunião mais relevante do dataset inteiro no topo, não só da página atual
- [ ] Nenhuma reunião desaparece da lista por causa do filtro de tópico
- [ ] `entities/call` removido, sem quebrar `CallHistory`/`CallRow` (agora consumindo `entities/meeting`)

## Testes

Sem suíte automatizada neste MVP — verificação manual: definir tópico, conferir badge e ordenação; definir tópico com match repetido para checar cache; rodar sync duas vezes sem mudar conteúdo e confirmar que `topic_embedding` não é recalculado desnecessariamente; testar paginação com sort por prioridade tendo mais de uma página de resultado.
