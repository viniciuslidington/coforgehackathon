# Feature Spec: Handoff Alertas → Chat + Evidence Rail

**Projeto:** Shift Briefing — Meeting Insights (FastAPI + LangGraph / Next.js)
**Status:** Draft para hackathon (MVP, frontend-only)
**Páginas afetadas:** `src/app/alerts/page.tsx`, `src/app/chat/page.tsx`

---

## Objetivo

Hoje `/alerts` e `/chat` são duas páginas mockadas que não se conversam: o botão "Investigar com IA" de um alerta leva a um chat genérico e vazio, e a resposta da IA nunca sabe por que o usuário chegou ali. Esta spec resolve duas coisas, ambas dentro da ficção mockada já existente (sem tocar o backend real):

1. **Handoff de contexto**: clicar em "Investigar com IA" num alerta leva para `/chat` já com a pergunta e a resposta inicial contextualizadas com aquele alerta específico (reunião, tags, diagnóstico).
2. **Evidence rail**: as "Fontes Citadas & Evidências" — hoje um acordeão escondido dentro da bolha da IA — viram um painel sempre visível ao lado da conversa, refletindo a última resposta da IA, com o score de relevância traduzido em rótulo qualitativo além do número.

## Fora de escopo (este MVP)

- Conectar `/chat` ao backend real (`POST /meeting-summaries/{meeting_id}/questions`) — o backend hoje só responde perguntas escopadas a **uma** reunião via streaming SSE, sem citações estruturadas; `/chat` continua mockando um RAG multi-reunião fictício, sem chamada de API nenhuma
- Unificar `/chat`, `features/quick-chat` e `features/call-detail/DetailChat` num único componente/hook de chat — cada um continua como está
- Fix do toggle "ciente vs. resolvido" nos alertas — spec própria, será feita separadamente
- Persistir o alerta/contexto entre reloads (é handoff de navegação única, não estado salvo)
- Rail com histórico de fontes de mensagens antigas — mostra sempre a última resposta da IA, nunca uma seleção do usuário

---

## Arquitetura

```
AlertsPage                              ChatPage
──────────                              ────────
"Investigar com IA"
  <Link href={`/chat
     ?alertId=...
     &meetingTitle=...
     &tags=...
     &diagnostic=...`}>
        │
        │  navegação (query string, sem estado global)
        ▼
                                    useSearchParams() [Suspense boundary]
                                         │
                                         ├─ params presentes?
                                         │     └─ seedFromAlert(params)
                                         │           → 1ª mensagem "user" = pergunta derivada do alerta
                                         │           → 1ª resposta "ai" = diagnóstico + sources mockados
                                         │           → contextScope = 'urgent' (reflete a origem)
                                         │
                                         └─ params ausentes → INITIAL_MESSAGES atual (comportamento hoje)
                                         ▼
                              ┌─────────────────────┬───────────────────┐
                              │   Conversa (esq.)    │  Evidence Rail    │
                              │   messagesList       │  (dir., sticky)   │
                              │                      │  fontes da        │
                              │                      │  ÚLTIMA resposta  │
                              │                      │  da IA            │
                              └─────────────────────┴───────────────────┘
                                    ↓ (viewport estreito)
                              ┌─────────────────────┐
                              │   Conversa           │
                              ├─────────────────────┤
                              │   Evidence Rail      │  (empilhado, mesma ordem de leitura)
                              └─────────────────────┘
```

Sem novo estado global, sem dependência nova: `useSearchParams` do `next/navigation`, que hoje não é usado em nenhum lugar do app — primeira vez que a URL carrega estado entre páginas.

---

## 1. Handoff Alertas → Chat

### `src/app/alerts/page.tsx`

Troca o `<Link href="/chat">` estático (linha 299) por um link com query string, montada a partir dos campos que o `AnomalyAlert` já tem:

```tsx
<Link
  href={`/chat?${new URLSearchParams({
    alertId: alert.id,
    meetingTitle: alert.meetingTitle,
    tags: alert.tags.join(','),
    diagnostic: alert.diagnostic,
    severity: alert.severity,
  })}`}
  className={...}
>
```

Nenhuma mudança no modelo de dados do alerta — `id`, `meetingTitle`, `tags`, `diagnostic`, `severity` já existem na interface `AnomalyAlert`.

### `src/app/chat/page.tsx`

- Componente principal precisa de um `<Suspense>` (exigência do Next.js App Router para `useSearchParams` em client component) — extrai o conteúdo atual para um `ChatPageContent` interno, `ChatPage` vira só o wrapper com `<Suspense fallback={null}>`.
- Nova função `seedFromAlert(params: URLSearchParams): Message[]` que, quando `alertId` está presente, gera:
  - mensagem `user`: `"O que você pode me dizer sobre: ${diagnostic}"` (ou frase equivalente que referencia o diagnóstico do alerta)
  - mensagem `ai`: reaproveita o formato de `bullets`/`sources` já usado em `INITIAL_MESSAGES`, mas com o `meetingTitle` e as `tags` do alerta citados no texto e nas fontes mockadas (mesma forma de `handleSend`, só trocando o texto de entrada)
- Quando `alertId` **não** está presente na URL, comportamento idêntico ao atual (`INITIAL_MESSAGES`) — zero regressão para quem abre `/chat` direto pela sidebar.
- `contextScope` inicial reflete a `severity` do alerta: `critical`/`high` → `'urgent'` (opção existente "Reuniões com Prioridade Alta/Urgente"); `medium` → mantém `'all'` (opção padrão), já que um alerta médio não justifica restringir o escopo do chat.

---

## 2. Evidence Rail

### Layout (`chat.module.css` + `chat/page.tsx`)

- `.chatContainer` deixa de ser uma coluna centrada de 820px e vira um grid de duas colunas em telas largas (`grid-template-columns: 1fr 320px`) — conversa à esquerda, rail à direita, `position: sticky` no rail para acompanhar o scroll da conversa.
- Breakpoint em `960px`: abaixo disso volta a uma coluna, rail empilha **depois** da lista de mensagens, ordem de leitura natural, sem toggle nem aba. **Nota:** hoje não existe nenhum `@media` query no codebase (app é desktop-only) — este é o primeiro breakpoint responsivo introduzido; `960px` é uma estimativa (conversa precisa de ~600px de largura confortável + 320px do rail + gaps) a validar visualmente durante a implementação, mas não deve ficar em aberto como decisão pendente.
- O acordeão "Fontes Citadas & Evidências" (`sourcesWrapper`, `sourcesHeader`, `sourcesList`, `sourceCard`) sai de dentro de `messageBubble` e vira o conteúdo do rail — mesmos `sourceCard`s, reaproveitando os estilos existentes, só mudando o contêiner pai.
- `openSources`/`toggleSources` (estado de expandir/recolher por mensagem) deixam de existir — o rail está sempre visível, não precisa de show/hide por mensagem.

### Conteúdo do rail

- Mostra as `sources` da **última mensagem `role: 'ai'`** da lista (`messages.filter(m => m.role === 'ai').at(-1)`), recalculado a cada novo `messages`.
- Estado vazio (nenhuma resposta da IA ainda, ou última resposta sem `sources`): texto simples tipo "As fontes da próxima resposta aparecem aqui." — segue o princípio de "tela vazia como convite a agir", não um espaço em branco sem explicação.
- **Rótulo qualitativo de relevância**: cada `sourceCard` ganha um badge ao lado do `relevance: number`, usando os mesmos cortes de tier já usados no resto do app (`urgent`/`high`/`normal`, reaproveitando as cores `--urgent`/`--high`/`--teal-light` de `alerts.module.css` para não inventar uma paleta nova):
  - `≥ 90` → "Alta relevância"
  - `≥ 75` → "Relevância média"
  - `< 75` → "Relevância baixa"

### `features/quick-chat` e `features/call-detail/DetailChat`

Sem mudanças — nenhum dos dois tem conceito de `sources`/citações hoje, então não há acordeão para migrar nesses componentes.

---

## Critérios de aceitação

- [ ] Clicar em "Investigar com IA" num alerta abre `/chat` com uma pergunta e resposta já preenchidas referenciando aquele alerta (título da reunião, diagnóstico) — não a conversa genérica atual
- [ ] Abrir `/chat` direto pela sidebar (sem query params) continua mostrando exatamente a conversa mockada de hoje
- [ ] Em tela larga, a conversa e o evidence rail aparecem lado a lado; o rail acompanha o scroll (sticky)
- [ ] Em tela estreita, o rail aparece empilhado abaixo da conversa, sem exigir toggle
- [ ] O rail sempre reflete as fontes da resposta mais recente da IA, sem exigir clique
- [ ] Antes de qualquer resposta ter `sources`, o rail mostra uma mensagem de estado vazio, nunca fica em branco
- [ ] Cada fonte no rail mostra o número de relevância **e** um rótulo qualitativo (Alta/Média/Baixa)
- [ ] Acordeão "Fontes Citadas & Evidências" antigo (dentro da bolha) não existe mais no DOM

## Testes

Sem suíte automatizada neste MVP (mock puro, sem lógica de negócio a testar) — verificação manual:

- Clicar em "Investigar com IA" em alertas de severidades diferentes (crítico, alto, médio) e conferir que o texto inicial do chat muda conforme o alerta
- Abrir `/chat` pela sidebar e confirmar que nada mudou em relação ao comportamento atual
- Redimensionar a janela do navegador cruzando o breakpoint e confirmar a transição de lado-a-lado para empilhado
- Enviar múltiplas perguntas em sequência no chat e confirmar que o rail troca de conteúdo a cada resposta nova, sempre mostrando a mais recente
- Conferir visualmente o rótulo de relevância nos três buckets (testar com scores mockados ≥90, 75-89, <75)
