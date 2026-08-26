# SDD — Quick Chat global cross-meeting

**Status:** Pronto para implementação após Meeting Summary v2  
**Data:** 2026-08-26  
**Pré-requisito:** [Meeting Summary v2 e next steps](./2026-08-26-meeting-summary-v2.md)  
**Decisões relacionadas:** [ADR 0002](../adr/0002-pre-indexed-evidence-for-quick-chat.md), [ADR 0003](../adr/0003-explicit-temporal-provenance-for-meeting-scopes.md), [Glossário](../../CONTEXT.md)

## 1. Resumo

Substituir o Quick Chat mockado por uma conversa global persistente que produz briefings, direcionamento e investigação usando as reuniões pertencentes ao meeting scope selecionado. O agente combina recuperação lexical e semântica, diferencia perguntas direcionadas de sínteses abrangentes e só publica afirmações ligadas a Evidence references verificadas.

O seletor é compartilhado com a tabela de reuniões. Alterá-lo atualiza a tabela imediatamente, mas não chama IA nem altera a conversa até o usuário enviar uma pergunta ou clicar em `Generate briefing`.

## 2. Objetivos

1. Responder perguntas sobre várias reuniões sem enviar todos os transcripts ao modelo.
2. Produzir sínteses realmente abrangentes quando a pergunta exigir cobertura completa.
3. Manter continuidade conversacional mesmo quando o scope muda.
4. Tornar toda resposta factual auditável por reunião e timestamp.
5. Expor cobertura, falhas parciais e qualidade temporal.
6. Persistir sessões, scopes, mensagens e fontes.
7. Suportar inicialmente até 1.000 reuniões no scope.

## 3. Fora de escopo

- Web, notícias, cotações ou qualquer fonte externa.
- Execução de tarefas em outros sistemas.
- Autenticação, times ou compartilhamento de chats na v1 isolada.
- Usar Topics de prioridade como filtro implícito do Quick Chat.
- Busca por sentimento ou inferência de intenção.
- Garantir que um commitment continua aberto fora do corpus de reuniões.

## 4. Experiência do produto

### 4.1 Scope compartilhado

Presets:

- `Last 5 meetings`
- `Last 2 hours`
- `Full shift`
- `Custom range`

O scope controla o conjunto mostrado na tabela e o conjunto elegível para o agente. Topics e ordenação alteram apenas a apresentação/prioridade da tabela.

`Full shift` usa início de turno e timezone configurados pelo ambiente. Janelas móveis são resolvidas no instante do envio. Cada resposta persiste seu intervalo concreto e a lista de reuniões resolvida.

### 4.2 Pending scope change

1. O usuário seleciona outro preset.
2. A tabela muda e o chat mostra um divisor provisório.
3. Se o usuário voltar ao scope corrente antes de perguntar, o divisor desaparece.
4. Enviar uma pergunta ou clicar em `Generate briefing` confirma a mudança.
5. O divisor torna-se permanente e a nova resposta usa apenas o novo scope.

O histórico anterior permanece disponível para resolver referências conversacionais, mas qualquer fato reutilizado deve ser revalidado contra o scope da nova pergunta.

### 4.3 Fontes

Afirmações usam marcadores `[1]`, `[2]`, seguidos por cards contendo:

- Título e data da reunião.
- Participante, quando aplicável.
- Timestamp e trecho curto.
- Indicador de horário aproximado, quando aplicável.

Clicar em uma fonte abre o `MeetingDetailModal` no timestamp correspondente.

### 4.4 Sessões

- `New chat` cria uma sessão vazia.
- Histórico em popover/lista com título automático, última mensagem e último scope.
- Abrir, renomear e excluir.
- Sem expiração automática na v1.
- Alterar scope nunca cria uma nova sessão automaticamente.

## 5. Requisitos funcionais

### P0

- Perguntas direcionadas pesquisam reuniões e trechos relevantes no scope.
- Pedidos abrangentes processam todas as reuniões prontas no scope.
- Toda resposta factual possui fontes válidas.
- Conversas e mudanças de scope sobrevivem a restart.
- Reuniões `pending`, `processing`, `partial` ou `failed` não são usadas como evidência.
- Respostas parciais mostram cobertura, por exemplo `97/100`.
- Informações contraditórias são apresentadas cronologicamente.
- Uma atualização só substitui a anterior quando a evidência torna isso explícito.
- Commitments sem fechamento posterior são chamados de `potentially open`.
- Recorded next steps podem ser apresentados como fatos da reunião; suggested next steps são recomendações do sistema e nunca são descritos como decisões ou compromissos dos participantes.

### P1

- Cache de briefings por fingerprint do scope.
- Renomeação de chats.
- Aliases confirmados de participantes.
- Exportar resposta com fontes.

## 6. Arquitetura

```text
Next.js
  page-level meeting scope
       ├─ Meeting History
       └─ Quick Chat
              │ POST turn + SSE
              ▼
FastAPI Quick Chat service
  ├─ resolve and persist scope snapshot
  ├─ load bounded conversation context
  ├─ classify + plan
  ├─ deterministic retrieval tools
  │    ├─ meeting summaries / briefs
  │    ├─ FTS5 chunks
  │    └─ sqlite-vec chunks
  ├─ synthesize claims + evidence IDs
  ├─ verify grounding
  └─ persist answer, sources and coverage
              │
              ▼
SQLite
  Meeting Summary v2 read model
  Quick Chat product history
  LangGraph internal checkpoints
```

Os checkpoints do LangGraph são estado interno de execução. As tabelas de sessões e mensagens são o contrato de produto e não dependem do formato do checkpointer.

## 7. Modelo de scope

Contrato discriminado:

```ts
type MeetingScopeSelection =
  | { kind: 'last_n'; count: 5 }
  | { kind: 'rolling'; duration_minutes: 120 }
  | { kind: 'shift' }
  | { kind: 'custom'; from: string; to: string; timezone: string };
```

O backend normaliza isso em um snapshot imutável:

```json
{
  "scope_snapshot_id": "scope-uuid",
  "selection": { "kind": "rolling", "duration_minutes": 120 },
  "resolved_at": "2026-08-26T15:00:00-03:00",
  "range_start": "2026-08-26T13:00:00-03:00",
  "range_end": "2026-08-26T15:00:00-03:00",
  "meeting_count": 13,
  "ready_count": 12,
  "approximate_time_count": 2
}
```

Para `last_n`, o snapshot guarda os IDs ordenados, mesmo sem intervalo contínuo. Para scopes temporais, limites usam início inclusivo e fim exclusivo.

## 8. Persistência do Quick Chat

### 8.1 `quick_chat_sessions`

| Campo | Tipo | Regra |
|---|---|---|
| `session_id` | TEXT PK | UUID |
| `title` | TEXT | Derivado da primeira pergunta, editável |
| `created_at` / `updated_at` | TEXT | UTC |
| `current_scope_snapshot_id` | TEXT nullable | Último scope confirmado |

### 8.2 `quick_chat_scope_snapshots`

| Campo | Tipo | Regra |
|---|---|---|
| `snapshot_id` | TEXT PK | UUID |
| `session_id` | TEXT FK | Sessão dona |
| `selection_json` | TEXT | Seleção original |
| `resolved_at` | TEXT | Instante da resolução |
| `range_start` / `range_end` | TEXT nullable | Limites concretos |
| `total_count` / `ready_count` | INTEGER | Base da cobertura |
| `approximate_time_count` | INTEGER | Transparência temporal |

### 8.3 `quick_chat_scope_meetings`

Tabela de associação imutável entre snapshot e meeting, guardando `eligibility` (`ready`, `not_ready`, `failed`) e a versão do índice consultada.

### 8.4 `quick_chat_messages`

| Campo | Tipo | Regra |
|---|---|---|
| `message_id` | TEXT PK | UUID |
| `session_id` | TEXT FK | Sessão |
| `role` | TEXT | `user`, `assistant`, `system_divider` |
| `content` | TEXT | Texto renderizável |
| `status` | TEXT | `running`, `complete`, `partial`, `failed`, `cancelled` |
| `scope_snapshot_id` | TEXT nullable | Obrigatório para turnos com IA |
| `coverage_ready` / `coverage_total` | INTEGER nullable | Cobertura |
| `created_at` | TEXT | UTC |
| `client_turn_id` | TEXT nullable unique | Idempotência de retry |

### 8.5 `quick_chat_evidence_refs`

Relaciona uma resposta a `meeting_id`, `caption_id`, `brief_item_id` opcional, quote, timestamp, número exibido e ordem. A resposta nunca persiste uma citação que não exista nessa tabela.

## 9. API

### Sessões

- `POST /quick-chat/sessions`
- `GET /quick-chat/sessions`
- `GET /quick-chat/sessions/{session_id}`
- `PATCH /quick-chat/sessions/{session_id}`
- `DELETE /quick-chat/sessions/{session_id}`

### Turnos

`POST /quick-chat/sessions/{session_id}/turns` retorna SSE.

```json
{
  "client_turn_id": "uuid",
  "kind": "question",
  "question": "O que mudou no lançamento?",
  "scope": { "kind": "rolling", "duration_minutes": 120 }
}
```

Para briefing, `kind="briefing"` e `question` é omitida.

Eventos SSE:

```text
turn_started  → IDs persistidos e scope resolvido
scope_committed → divisor confirmado, quando aplicável
step          → progresso user-facing
sources       → fontes disponíveis para preview
answer        → texto final, fontes, cobertura e warnings
error         → erro terminal recuperável
```

Exemplo final:

```json
{
  "type": "answer",
  "message_id": "msg-2",
  "text": "O lançamento foi movido para terça [1][2].",
  "evidence": [{ "number": 1, "meeting_id": "m-1", "caption_id": "m-1:42" }],
  "coverage": { "ready": 12, "total": 13, "complete": false },
  "warnings": ["1 meeting was still processing"]
}
```

O stream envia o primeiro evento em menos de um segundo. Abort do cliente marca o turno como `cancelled`; retry com o mesmo `client_turn_id` não duplica mensagens.

## 10. Grafo do agente

### Estado

```text
session_id, turn_id, question, conversation_context,
scope_snapshot, intent, retrieval_plan, candidate_meetings,
evidence_candidates, accepted_evidence, claims,
verification, answer, coverage, warnings
```

### Nodes

```text
START
  → classify_and_plan
  → route_by_intent
       ├─ targeted_retrieval
       └─ comprehensive_map_reduce
  → synthesize_claims
  → verify_grounding
  → render_answer
  → persist_turn
  → END
```

`classify_and_plan` retorna saída estruturada:

- `intent`: `targeted`, `comprehensive`, `follow_up`.
- Entidades, participantes, datas e tipos de brief necessários.
- Necessidade de transcript ou suficiência do Meeting Brief.
- Limites solicitados, sem poder expandir o scope.

### Pergunta direcionada

1. Filtrar tudo pelo snapshot persistido.
2. Buscar summaries/briefs por campos estruturados.
3. Executar FTS5 e KNN sobre chunks.
4. Combinar rankings com Reciprocal Rank Fusion.
5. Selecionar inicialmente até 8 reuniões e 24 chunks.
6. Permitir uma expansão limitada se as evidências forem insuficientes.

### Síntese abrangente

1. Ler Meeting Briefs de todas as reuniões `ready` no snapshot.
2. Agrupar cronologicamente em lotes com orçamento fixo.
3. Produzir resumos intermediários contendo Evidence IDs, não prosa sem origem.
4. Reduzir os lotes preservando decisões, mudanças, commitments, riscos e conflitos.
5. Buscar chunks somente para confirmar ou aprofundar alegações selecionadas.

Top-k nunca substitui cobertura em uma pergunta abrangente.

### Verificação

O node de síntese produz claims estruturados, cada um com Evidence IDs. O verificador:

1. Confirma deterministicamente que IDs pertencem ao snapshot e ao material recuperado.
2. Avalia se cada evidência sustenta semanticamente a claim.
3. Remove, enfraquece ou solicita uma única correção para claims sem suporte.
4. Impede a resposta final se fatos centrais ficarem sem evidência.

## 11. Tools determinísticas

| Tool | Função |
|---|---|
| `get_scope_catalog` | Metadados de todas as reuniões do snapshot |
| `search_meetings` | Busca em title, summary, participants, keywords e brief items |
| `search_evidence` | Busca híbrida em chunks dentro do snapshot |
| `get_meeting_brief` | Brief estruturado de reuniões selecionadas |
| `get_caption_evidence` | Captions exatas por IDs, speaker ou intervalo |
| `aggregate_scope_briefs` | Lotes completos para síntese abrangente |
| `find_participant_history` | Reuniões por identidade/alias confirmado |

Todas recebem o snapshot internamente; o modelo não fornece IDs arbitrários fora dele. Não existem tools externas neste grafo.

## 12. Memória conversacional

- Carregar últimas mensagens relevantes com limites de tokens.
- Manter um resumo conversacional versionado para sessões longas.
- Mensagens antigas ajudam a resolver “isso”, mas não contam como evidência.
- Ao mudar scope, entidades conversacionais continuam disponíveis; fatos são recuperados novamente.
- O `thread_id` do LangGraph usa namespace `quick-chat:{session_id}`, separado do Meeting Chat.

## 13. Frontend

### Estado compartilhado

Elevar o scope para `page.tsx` por meio de `useMeetingScope`. `CallHistory` e `QuickChat` recebem a mesma seleção. O backend, e não o browser, resolve o conjunto final de reuniões.

### Quick Chat

- Remover `BRIEF`, `KEYPOINTS`, `ContextLabel` e respostas mockadas.
- Estado real para sessão, mensagens, pending scope change, streaming, steps, sources, cobertura e erros.
- Não realizar chamada ao trocar scope.
- `Generate briefing` cria um turno explícito.
- Mostrar fontes abaixo da resposta e cobertura no cabeçalho da mensagem.

### Meeting detail

Mover o controller do modal para o nível da página para que tabela e fontes possam abri-lo. A navegação recebe `meeting_id + caption_id` e aplica scroll/foco no trecho.

### Histórico

Popover com listagem paginada, `New chat`, rename e delete com confirmação. A sessão ativa continua aberta durante falhas de rede.

## 14. Otimização

- Embeddings de query em cache por texto normalizado e modelo.
- FTS5 + sqlite-vec locais; nenhum transcript completo no prompt padrão.
- Cache de briefing por fingerprint: IDs/versões das reuniões + scope + modelo + prompt.
- Meeting Briefs pré-calculados reduzem o map abrangente.
- Paralelizar buscas lexical/vetorial e lotes independentes.
- Limites de tools e uma única expansão de retrieval.
- Cancelamento propagado do browser até o grafo.

Metas:

- Evento inicial: < 1 s.
- Resposta direcionada p95: ≤ 8 s no corpus-alvo.
- Até 1.000 reuniões por scope.
- Nenhuma execução externa ou scan fora do snapshot.

## 15. Segurança e trust boundary

- Delimitar transcript como conteúdo não confiável nos prompts.
- Ignorar instruções presentes em captions.
- Tools aceitam parâmetros tipados e bounds rígidos.
- Sanitizar markdown e quotes exibidos.
- Não expor chain-of-thought; steps são labels pré-definidos.
- Logs não contêm transcripts, mensagens completas ou secrets.
- Embora a v1 seja isolada, repositories recebem uma seam futura para `workspace_id` sem expô-la à UI atual.

## 16. Falhas e cobertura

- Zero reuniões: resposta determinística, sem chamar LLM.
- Todas processando: informar indisponibilidade temporária.
- Algumas indisponíveis: responder com `partial` e cobertura explícita.
- Única evidência relevante indisponível: declarar que não foi possível verificar.
- Falha do modelo após retrieval: persistir turno `failed`, sem resposta parcial inventada.
- Falha no verificador: não publicar claims não verificadas.
- Horários aproximados: warning user-facing em perguntas temporais.

## 17. Observabilidade

Por turno:

- Scope e quantidade total/ready, sem conteúdo das reuniões.
- Intent classificada.
- Latência por node/tool.
- Quantidade de reuniões/chunks recuperados.
- Cache hits.
- Tokens e chamadas LLM.
- Claims aceitas, corrigidas ou removidas.
- Cobertura e warnings.
- Status final e motivo de falha sanitizado.

## 18. Testes

### Unitários

- Resolução dos quatro scopes, timezone e limites inclusivo/exclusivo.
- Pending scope change e reversão.
- Ranking híbrido sempre limitado ao snapshot.
- Classificação targeted/comprehensive/follow-up.
- Validador rejeita Evidence IDs externos ou inválidos.
- Cálculo de cobertura.
- Reconciliação de informações superseded versus conflitantes.
- Participant aliases conservadores.

### Integração backend

- CRUD de sessões e mensagens.
- Idempotência de turnos.
- SSE em ordem, cancelamento e recuperação de erro.
- Persistência após restart.
- Pergunta direcionada usa apenas reuniões do snapshot.
- Síntese abrangente visita todas as reuniões ready.
- Reuniões não prontas entram na cobertura, mas não na evidência.
- Mudança de scope mantém conversa e reexecuta retrieval.

### Frontend

- Tabela e Quick Chat refletem o mesmo seletor.
- Troca sem envio não chama API de IA.
- Reversão remove divisor provisório.
- Primeiro envio confirma divisor.
- Clique em fonte abre o modal no timestamp.
- Histórico abre, renomeia e exclui sessões.
- Abort não deixa loading preso.

### Evals

Conjunto dourado com perguntas direcionadas, abrangentes, follow-ups, conflitos e scopes diferentes. Metas iniciais:

- Precisão de citações válidas: 100%.
- Claims factuais sem evidência: 0.
- Vazamento de reunião fora do scope: 0.
- Cobertura abrangente reportada corretamente: 100%.
- Respostas direcionadas consideradas corretas: ≥ 85%.

## 19. Fases de implementação

### Fase 0 — Fundação

Concluir o [Meeting Summary v2](./2026-08-26-meeting-summary-v2.md), backfill e índice híbrido.

### Fase 1 — Scope compartilhado

Contrato de scope backend/frontend, correção temporal, listagem e estado elevado para a página.

### Fase 2 — Sessões e UI real

CRUD persistente, remoção de mocks, pending scope change, SSE básico e histórico.

### Fase 3 — Retrieval direcionado

Tools, busca híbrida, síntese com fontes, verificação e navegação para evidência.

### Fase 4 — Síntese abrangente

Map-reduce sobre todos os briefs, cobertura parcial e `Generate briefing`.

### Fase 5 — Hardening

Evals, caching, observabilidade, cancelamento, prompt injection e testes de escala.

## 20. Critérios de aceitação

- [ ] Os quatro selectors controlam tabela e Quick Chat.
- [ ] Trocar scope sem perguntar não chama o agente.
- [ ] A conversa continua após mudanças de scope sem reutilizar evidência fora do novo snapshot.
- [ ] Perguntas direcionadas retornam Evidence references navegáveis.
- [ ] Sínteses abrangentes consideram todas as reuniões ready.
- [ ] Respostas incompletas mostram cobertura e reuniões indisponíveis.
- [ ] Conflitos e informações superseded permanecem distinguíveis.
- [ ] Sessões sobrevivem a restart e suportam create/list/rename/delete.
- [ ] Nenhuma fonte externa é chamada.
- [ ] O evento inicial chega em menos de um segundo e a meta p95 direcionada é validada.

## 21. Arquivos principais previstos

```text
resume-ai-service/app/
  graphs/quick_chat/{state,nodes,prompts,graph}.py
  schemas/quick_chat.py
  services/{quick_chat,meeting_scope,meeting_index,database}.py
  routers/quick_chat.py
src/
  app/page.tsx
  entities/meeting/model/types.ts
  features/meeting-scope/*
  features/quick-chat/{model,ui}/*
  features/call-detail/*
  shared/api/meetings.ts
```

O Meeting Chat por reunião permanece um grafo separado; compartilhará repositories de captions/evidências, não seu state ou suas tools externas.
