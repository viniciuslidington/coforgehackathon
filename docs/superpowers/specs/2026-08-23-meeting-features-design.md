# Feature Spec: Meeting Chat & Thread Continuity

**Projeto:** Shift Briefing — Meeting Insights (FastAPI + LangGraph / Next.js)
**Status:** Draft para hackathon (MVP)
**Stack confirmada:** backend de IA em FastAPI (`resume-ai-service`), frontend em Next.js (`src`), mantendo a base já existente.

---

## Contexto e origem

Este documento consolida três features que se apoiam na mesma arquitetura:

1. **Chat por reunião** — abrir uma reunião e conversar sobre o conteúdo dela.
2. **Chat global** — conversar sobre todas as reuniões de um período.
3. **Counterparty Thread** — continuidade de contexto quando a mesma pessoa aparece em mais de uma reunião.

A Feature 3 nasceu de uma spec anterior ("Counterparty Thread") escrita para um domínio de mesa de trading (chamadas em tempo real, `counterparty_id` vindo de CTI/turret, traders "online" atendendo contrapartes). Esse domínio ainda não existe no sistema — o MVP atual processa **reuniões gravadas via VTT**, não chamadas ao vivo. Este spec adapta os nomes e o gatilho da feature para o domínio real, mantendo a visão de produto (quando a identificação de chamada em tempo real existir, o mapeamento abaixo se estende naturalmente).

### Tabela de mapeamento (spec antiga → sistema real)

| Termo na spec original | Não existe hoje porque... | Equivalente real usado neste spec |
|---|---|---|
| `counterparty_id` estável (CTI) | Não há telefonia/identificação de chamada em tempo real | Nome do participante extraído do VTT (`meeting_participants()`) — não é um ID estável, é matching por string |
| Call History Table | — | `CallHistory` (`src/widgets/call-history/ui/CallHistory.tsx`), já existente |
| Call detail panel | — | `CallDetailModal` (revivido de `features/call-detail`, ver Feature 1) |
| Status atendida/não atendida | Reunião não tem esse conceito | Removido do MVP. Vira Future Consideration quando houver chamada real |
| `desk`, `trader_id` | Não existe dono/mesa por reunião no modelo atual | Fora de escopo — não usado para agrupamento |
| Synthesis Agent | — | `graph.py` (LangGraph). Cada feature usa um node dedicado |
| Dado sintético via Faker | Já existe pipeline real com VTT | Amostras `.vtt` em `resume-ai-service/samples/`, expandidas pelo time para conter participantes recorrentes (necessário para demonstrar thread) |
| Quick Chat | — | `features/quick-chat` (revivido, ver Feature 2) |

---

## Arquitetura comum às três features

```
Next.js (client)                              FastAPI (resume-ai-service)
─────────────────                             ───────────────────────────
CallHistory ──click row──▶ call-detail ───┐
QuickChat ──pergunta──────────────────────┤──▶ shared/api/meetings.ts ──▶ main.py (rotas, orquestração)
CallDetailModal ──thread section──────────┘                                 │        │        │
                                                                              ▼        ▼        ▼
                                                                        database.py meetings.py graph.py
                                                                        (adapter    (catálogo   (único módulo
                                                                        SQLite)      de amostras) que fala com o LLM)
                                                                                                    │
                                                                                                    ▼
                                                                                              OpenRouter (LLM)
```

**Regra de seam única por responsabilidade:**
- `shared/api/meetings.ts` é o único módulo do frontend que sabe que existe HTTP.
- `graph.py` é o único módulo do backend que sabe que existe um LLM.
- `database.py` é o único módulo que conhece o formato de armazenamento (inclusive `captions_json` e a query de agrupamento por participante).

### Mudança de schema (uma vez, serve as três features)

`meeting_summaries` ganha:
- `captions_json TEXT NOT NULL DEFAULT '[]'` — lista serializada de `{start, end, text}`, parseada uma vez no upload/sync e reaproveitada para timeline, transcript e todos os chats grounded em transcript.

`database.py` (`list_summaries` e afins) para de devolver `participants`/`keywords` como string com vírgula — passa a devolver `list[str]` já parseado. Isso resolve de uma vez o vazamento identificado no relatório de arquitetura (Candidato 3) e é pré-requisito para a query de agrupamento da Feature 3.

---

## Feature 1 — Chat por reunião

### Objetivo
Abrir uma reunião da lista e ver conteúdo real (timeline/transcript) + conversar especificamente sobre ela.

### Backend
- `POST /summaries` (upload de `.vtt`) passa a persistir via `upsert_summary`, incluindo `captions_json`. Hoje esse endpoint só devolve o resultado e não salva nada.
- `refresh_meetings` (sync das amostras) também grava `captions_json`.
- `GET /meeting-summaries/{meeting_id}` (novo): devolve `MeetingSummary` + `captions` estruturadas.
- `POST /meeting-summaries/{meeting_id}/questions` (novo): pergunta grounded no transcript salvo no banco — funciona para qualquer reunião persistida (amostra ou upload), diferente do `/meetings/{id}/questions` atual, que só enxerga o catálogo fixo `MEETINGS`.

### Frontend
- `features/call-detail` revivido: `Call` → `MeetingSummary`/`MeetingDetail`; `useCallDetail` → `useMeetingDetail`, busca detalhe sob demanda ao abrir; chat interno chama o endpoint novo em vez do mock `generateAnswer`.
- `CallRow` ganha `onClick` para abrir o modal.
- `CallDetailModal`, `CallTimeline`, `CallTranscript`, `DetailChat` são reaproveitados como estão (já usam os tokens de design do sistema) — só trocam a fonte de dados.

### Critérios de aceitação
- [ ] Clicar numa linha da tabela abre o modal com timeline/transcript reais daquela reunião
- [ ] Perguntas no chat do modal são respondidas com base no transcript daquela reunião especificamente
- [ ] Funciona tanto para as reuniões de amostra quanto para uploads persistidos

---

## Feature 2 — Chat global (todas as reuniões)

### Objetivo
Perguntar algo no chat lateral e receber resposta considerando todas as reuniões do período ativo, não uma reunião isolada.

### Backend
- `POST /meeting-summaries/questions` (novo): recebe `{question, period}`, filtra summaries pelo mesmo critério de período já usado em `get_stored_summaries`, monta contexto agregado (`title + simple_summary + keywords + participants` de cada reunião no período).
- `graph.py` ganha um node novo, `answer_across_meetings`, que responde citando de qual reunião veio cada informação.

### Frontend
- `features/quick-chat` revivido: `useChat` perde `BRIEF`/`ContextLabel` mockados, recebe `period` — **estado levantado para `page.tsx`**, compartilhado com `CallHistory`, para que o chat global sempre respeite o mesmo filtro visível na tabela.

### Critérios de aceitação
- [ ] Uma pergunta no chat global responde com base nas reuniões do período selecionado, não em texto fixo
- [ ] Trocar o período na tabela também muda o escopo do chat global (mesmo estado)
- [ ] A resposta referencia reuniões específicas quando relevante

---

## Feature 3 — Counterparty Thread (continuidade por participante recorrente)

### Problem Statement

Quando a mesma pessoa aparece em mais de uma reunião numa janela de tempo, quem abre a reunião mais recente não tem visibilidade automática do que já foi discutido antes com ela — precisa lembrar, perguntar a um colega, ou reconstruir manualmente. Isso é o mesmo problema de perda de contexto que o sistema já ataca no nível "o que aconteceu", mas ainda não resolvido no nível "o que já aconteceu **com essa pessoa especificamente**".

A visão de produto de longo prazo é chamadas em tempo real identificadas automaticamente (`counterparty_id` via CTI/turret), com um trader diferente do anterior podendo atender e precisar do contexto instantaneamente. Essa infraestrutura não existe ainda — este MVP simula o gatilho usando o participante extraído do transcript, dentro do que o pipeline atual já processa.

### Goals
1. Identificar em menos de 3 segundos, ao abrir uma reunião, se ela faz parte de uma sequência com um participante recorrente
2. Receber um recap sintetizado conectando as reuniões anteriores com essa pessoa à atual, com sugestão de retomada
3. Funcionar tanto no modal de detalhe (Feature 1) quanto no chat global (Feature 2), sem endpoint duplicado nesse segundo caso
4. Agrupamento automático — zero configuração manual

### Non-Goals
- Não é CRM de relacionamento de longo prazo — janela de agrupamento é curta (dias), não histórico permanente
- Não resolve identificação de chamada em tempo real (CTI) — fica em Future Considerations
- Não reprocessa áudio — usa apenas `captions_json` e summaries já persistidos
- Não faz recomendação de trading — a sugestão de retomada é conversacional
- Não notifica proativamente nesta v1 — só aparece quando o trader abre a reunião ou pergunta no chat

### Requirements

**P0.1 — Agrupamento determinístico por participante (sem LLM)**
- `database.py` ganha `find_related_meetings(meeting_id, window_days=1) -> list[MeetingSummary]`
- Casa por interseção de `participants` (já parseado como lista, não mais string com vírgula) dentro da janela
- Query pura, determinística — não passa por LLM
- Janela configurável via parâmetro (`window_days`), default 1 dia — é a granularidade máxima possível hoje porque `meeting_date` não tem hora

*Critérios de aceitação:*
- [ ] Duas reuniões com participante em comum na mesma janela são identificadas como relacionadas
- [ ] Uma reunião sem participante em comum com nenhuma outra não forma thread
- [ ] A janela é configurável, não hardcoded

**P0.2 — Indicador visual no CallRow**
- `GET /meeting-summaries` passa a incluir `related_count` por item (calculado server-side, não depende de paginação para estar correto)
- `related_count > 0` → badge (ex: "🔁 2ª reunião com Nina hoje")

*Critérios de aceitação:*
- [ ] Reunião com `related_count > 0` exibe o indicador
- [ ] Reunião com `related_count == 0` não exibe nada

**P0.3 — Recap sintetizado no modal de detalhe**
- `GET /meeting-summaries/{meeting_id}/thread` (novo): devolve `{related: MeetingSummary[], recap: str}`
- `recap` é gerado pelo node `summarize_thread` em `graph.py`, grounded nos summaries das reuniões relacionadas (não no transcript completo, não na mesa inteira)
- `CallDetailModal` renderiza uma seção de thread no topo, só quando `related_count > 0` — sem espaço reservado vazio

*Critérios de aceitação:*
- [ ] Reunião com thread mostra a seção de recap antes dos demais detalhes
- [ ] Reunião sem thread não mostra a seção
- [ ] O recap cita quantas reuniões relacionadas houve e quando foi a última

**P0.4 — Suporte no chat global**
- Já coberto pela Feature 2 — o contexto agregado enviado para `answer_across_meetings` já inclui `participants` por reunião. Nenhum endpoint novo é necessário; só garantir que o campo está presente no contexto montado.

*Critérios de aceitação:*
- [ ] Uma pergunta no chat global mencionando um nome retorna contexto de todas as reuniões daquela pessoa no período, não só a mais recente

### Nice-to-Have (P1)
- Filtro "mostrar só reuniões com thread ativa" na tabela

### Future Considerations (P2)
- Identificação de chamada em tempo real (CTI/turret) substituindo o matching por nome
- `counterparty_id` estável quando a infraestrutura de telefonia existir
- Janela de agrupamento configurável em horas, não só dias (requer `meeting_date` com granularidade de hora)
- Pré-computar o recap no momento do sync/upload em vez de sob demanda, se o custo de latência por abertura for um problema

### Dados necessários para a demo
As duas amostras atuais não compartilham participantes (`product-planning.vtt`: Leo/Maya/Nina; `customer-feedback.vtt`: Iris/Sam). O time vai alimentar a base com mais reuniões de demonstração contendo participantes recorrentes, para que o cenário de thread apareça na apresentação.

---

## Tratamento de erro

Segue o padrão já existente em `main.py`: `RuntimeError` → 503 (config ausente), `APIStatusError` → 429 (rate limit) ou 502 (falha upstream), preservando a mensagem do provedor.

## Testes

Sem suíte automatizada neste MVP — verificação manual via UI com o backend local rodando: abrir modal de reunião com e sem thread, perguntar no chat por reunião, perguntar no chat global, trocar período e confirmar que o chat global acompanha.

## Fora de escopo (todas as features)

- CRM/relacionamento de longo prazo
- Identificação de chamada em tempo real
- Reprocessamento de áudio
- Recomendação de trading
- Notificação proativa
