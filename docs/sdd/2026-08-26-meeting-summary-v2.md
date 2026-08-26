# SDD — Meeting Summary v2 e síntese de next steps

**Status:** Pronto para implementação  
**Data:** 2026-08-26  
**Dependentes:** Quick Chat global  
**Decisões relacionadas:** [ADR 0002](../adr/0002-pre-indexed-evidence-for-quick-chat.md), [ADR 0003](../adr/0003-explicit-temporal-provenance-for-meeting-scopes.md), [Glossário](../../CONTEXT.md)

## 1. Resumo

Evoluir o processamento de reuniões de uma linha de listagem (`title`, `simple_summary`, `keywords`) para um artefato auditável e pesquisável. Cada reunião passará a ter horário com proveniência, captions persistidas, chunks híbridos, Meeting Brief estruturado e dois tipos claramente separados de next steps:

- **Recorded next steps:** ações explicitamente combinadas na reunião.
- **Suggested next steps:** recomendações geradas pelo sistema a partir de evidências da reunião.

O transcript continua sendo a evidência primária. Resumos, briefs e sugestões são derivados versionados, nunca fontes autônomas de verdade.

## 2. Estado atual e problemas

- `meeting_summaries` guarda participantes e keywords como strings separadas por vírgula.
- O sync grava `date.today()` como `meeting_date`, independentemente da reunião.
- Somente 10 dos 102 VTTs atuais têm `Note Date`; os demais não permitem recuperar o horário original.
- Captions são baixadas do R2 e mantidas apenas em cache de processo.
- Existe um embedding por reunião, formado por título, resumo e keywords; não existem embeddings de transcript.
- O overview usa parsing textual de três linhas em vez de saída estruturada validada.
- O resumo detalhado menciona next steps apenas em prosa; não existe contrato, evidência, estado ou UI para eles.
- `list_objects_v2` não pagina, podendo omitir objetos após o limite da primeira página.

## 3. Objetivos

1. Tornar data e hora utilizáveis por scopes temporais sem esconder aproximações.
2. Persistir captions e chunks para eliminar downloads repetidos e habilitar busca híbrida.
3. Produzir Meeting Brief estruturado com evidências verificáveis.
4. Extrair recorded next steps e sintetizar suggested next steps sem misturá-los.
5. Expor estado e cobertura do pipeline na API e na interface.
6. Permitir reprocessamento idempotente e versionado.
7. Servir como read model otimizado para o Quick Chat global.

## 4. Fora de escopo

- Sincronização bidirecional com gerenciadores de tarefas.
- Marcar um compromisso como concluído usando fontes externas às reuniões.
- Identificação probabilística silenciosa de participantes.
- Análise de sentimento ou intenção.
- Autenticação e multi-workspace na v1 isolada.
- Vector database externo.

## 5. Regras de confiança

1. Todo item derivado referencia uma ou mais captions persistidas.
2. Uma evidência inválida faz o item ser descartado ou marcar o processamento como parcial; nunca é publicada silenciosamente.
3. Recorded next steps exigem linguagem explícita de ação futura no transcript.
4. Suggested next steps não podem inventar responsável, prazo ou decisão.
5. Ausência de encerramento posterior cria um `potentially_open` apenas no Quick Chat; não transforma automaticamente um compromisso da reunião em tarefa pendente.
6. Conteúdo de transcript é dado não confiável e nunca instrução para o agente.

## 6. Arquitetura

```text
R2 VTT + metadata
        │
        ▼
ingestion service
  ├─ parse metadata/captions
  ├─ resolve temporal provenance
  ├─ persist captions
  ├─ create overview + Meeting Brief
  ├─ synthesize suggested next steps
  ├─ validate evidence deterministically
  ├─ build chunks + lexical index
  ├─ batch embeddings
  └─ publish processing status
        │
        ▼
SQLite read model
  ├─ meeting_summaries
  ├─ meeting_captions
  ├─ meeting_chunks + FTS5 + sqlite-vec
  ├─ meeting_brief_items
  └─ brief_item_evidence
        │
        ├─ Meeting list/detail UI
        └─ Quick Chat retrieval
```

O R2 continua sendo o arquivo de origem. O SQLite passa a ser o read model completo utilizado pela aplicação.

## 7. Modelo de dados

### 7.1 `meeting_summaries`

Manter a tabela existente e adicionar:

| Campo | Tipo | Regra |
|---|---|---|
| `started_at` | TEXT nullable | ISO-8601 com offset |
| `ended_at` | TEXT nullable | Explícito ou calculado pela duração |
| `source_timezone` | TEXT nullable | Timezone original quando conhecido |
| `time_source` | TEXT | `object_metadata`, `vtt_header`, `r2_last_modified`, `legacy_sync` |
| `time_precision` | TEXT | `instant`, `date` ou `unknown` |
| `time_is_approximate` | INTEGER | Booleano; `1` para fallback |
| `processing_status` | TEXT | `pending`, `processing`, `ready`, `partial`, `failed` |
| `processing_error` | TEXT nullable | Mensagem sanitizada |
| `pipeline_version` | INTEGER | Versão integral do pipeline |
| `processed_at` | TEXT nullable | Final da última execução |
| `brief_item_count` | INTEGER | Contador desnormalizado |
| `recorded_next_step_count` | INTEGER | Contador desnormalizado |
| `suggested_next_step_count` | INTEGER | Contador desnormalizado |

`participants` e `keywords` permanecem temporariamente em colunas TEXT, mas a migração converte os valores separados por vírgula para JSON arrays e novos writes usam apenas JSON válido. O reader aceita os dois formatos durante o rollout e remove o fallback depois do backfill.

### 7.2 `meeting_captions`

| Campo | Tipo | Regra |
|---|---|---|
| `caption_id` | TEXT PK | `{meeting_id}:{sequence}` estável |
| `meeting_id` | TEXT FK | `ON DELETE CASCADE` |
| `sequence` | INTEGER | Ordem original, unique por reunião |
| `start_ms` / `end_ms` | INTEGER | Offset dentro da reunião |
| `speaker` | TEXT | Vazio quando desconhecido |
| `text` | TEXT | Texto normalizado sem speaker duplicado |

### 7.3 `meeting_chunks`

| Campo | Tipo | Regra |
|---|---|---|
| `chunk_id` | TEXT PK | Estável por reunião e versão do chunker |
| `meeting_id` | TEXT FK | Filtro obrigatório antes da busca |
| `start_caption_id` / `end_caption_id` | TEXT | Limites navegáveis |
| `start_ms` / `end_ms` | INTEGER | Intervalo agregado |
| `speakers_json` | TEXT | JSON array |
| `text` | TEXT | Conteúdo do chunk |
| `embedding` | BLOB/vector | Modelo multilíngue local |
| `embedding_model` | TEXT | Nome e versão |
| `chunker_version` | INTEGER | Reindexação explícita |

Criar uma tabela FTS5 para `text` e declarar `sqlite-vec` como dependência direta para KNN local. O ranking híbrido usa Reciprocal Rank Fusion entre FTS5 e similaridade vetorial.

### 7.4 `meeting_brief_items`

| Campo | Tipo | Regra |
|---|---|---|
| `item_id` | TEXT PK | UUID |
| `meeting_id` | TEXT FK | `ON DELETE CASCADE` |
| `kind` | TEXT | `decision`, `commitment`, `risk`, `blocker`, `open_question`, `change`, `fact`, `next_step` |
| `origin` | TEXT | `recorded` ou `suggested` |
| `text` | TEXT | Formulação curta e autossuficiente |
| `owner` | TEXT nullable | Somente quando explícito |
| `due_text` | TEXT nullable | Forma original, como “sexta” |
| `due_at` | TEXT nullable | Apenas quando resolvível com segurança |
| `state` | TEXT nullable | `stated`, `completed`, `cancelled`, `superseded`; sugestões usam `suggested` |
| `confidence` | REAL | Confiança da extração, não da verdade externa |
| `sequence` | INTEGER | Ordem de apresentação |
| `extractor_version` | INTEGER | Auditoria e reprocessamento |

`origin=recorded` exige evidência direta. `origin=suggested` exige evidência de motivação e nunca recebe `owner` ou `due_at` inventados.

### 7.5 `brief_item_evidence`

| Campo | Tipo | Regra |
|---|---|---|
| `item_id` | TEXT FK | Item derivado |
| `caption_id` | TEXT FK | Evidência primária |
| `quote` | TEXT | Substring validada da caption |
| `rank` | INTEGER | Ordem das evidências |

PK composta por `(item_id, caption_id, rank)`.

## 8. Proveniência temporal

Ordem de confiança:

1. `started_at` ISO-8601 em metadata explícita do objeto.
2. Header VTT com data/hora e timezone.
3. Header VTT apenas com data, marcado com precisão de dia.
4. `R2 LastModified`, marcado como aproximação de upload.
5. `legacy_sync`, apenas para compatibilidade e sempre aproximado.

O gerador de transcripts passa a escrever o mesmo `started_at` no header e na metadata do R2. O listador R2 deve usar paginator e devolver `Key`, `LastModified`, `ETag`, tamanho e metadata temporal.

Scopes por hora usam registros com precisão `instant`. Para o corpus legado da demonstração, `R2 LastModified` pode preencher um instante aproximado e deve produzir warning; uma data sem horário não é silenciosamente transformada em meia-noite.

## 9. Pipeline de processamento

### 9.1 Grafo `meeting_analysis`

```text
START
  → parse_and_persist_captions        deterministic
  → resolve_time                     deterministic
  → create_structured_overview        LLM structured output
  → extract_recorded_brief            LLM structured output
  → synthesize_suggested_next_steps   LLM structured output
  → validate_evidence                 deterministic
  → persist_brief                     transaction
  → build_chunks                      deterministic
  → embed_chunks                      local batch
  → mark_ready
  → END
```

O overview e o brief podem compartilhar uma chamada estruturada se medição real demonstrar ganho de latência sem reduzir a qualidade. O node de sugestões continua separado para impedir que recomendações contaminem fatos registrados.

### 9.2 Saída estruturada

Substituir o parser `TITLE:/SUMMARY:/KEYWORDS:` por modelos Pydantic e `with_structured_output`. O LLM retorna IDs de captions e quotes; o validador confirma:

- Caption pertence à reunião.
- Quote normalizada é substring da caption.
- Owner e prazo aparecem na evidência quando preenchidos.
- Suggested next step possui ao menos uma evidência motivadora.
- Nenhum campo contém instrução executável ou URL externa inserida pelo transcript.

Uma única correção limitada pode ser solicitada ao modelo. Persistindo a falha, o item é removido e a reunião fica `partial`; o restante não é perdido.

### 9.3 Chunking

- Preservar fronteiras de fala sempre que possível.
- Alvo inicial: 350–500 tokens, overlap máximo de uma caption.
- Nunca misturar reuniões.
- Guardar caption IDs de início e fim.
- Recriar apenas quando `chunker_version` ou conteúdo mudar.
- Embeddings executados em batch, usando o modelo local multilíngue já adotado pelo projeto.

## 10. API

### 10.1 Lista

`GET /meeting-summaries` passa a aceitar o contrato de scope compartilhado e retorna, por item:

```json
{
  "meeting_id": "m-123",
  "title": "Budget launch review",
  "started_at": "2026-08-26T09:00:00-03:00",
  "ended_at": "2026-08-26T09:28:00-03:00",
  "time_source": "object_metadata",
  "time_precision": "instant",
  "time_is_approximate": false,
  "processing_status": "ready",
  "simple_summary": "...",
  "participants": ["Nina"],
  "keywords": ["budget"],
  "recorded_next_step_count": 2,
  "suggested_next_step_count": 1
}
```

### 10.2 Detalhe

Adicionar `GET /meeting-summaries/{meeting_id}` com overview, Meeting Brief completo, next steps e Evidence references. O transcript permanece em `GET /meeting-summaries/{meeting_id}/transcript`.

### 10.3 Reprocessamento

- `POST /meeting-summaries/{meeting_id}/reprocess`: idempotente; aceita componentes opcionais (`overview`, `brief`, `chunks`, `embeddings`).
- `POST /meeting-summaries/reprocess`: operação administrativa em lote por `pipeline_version`, com limite explícito.
- Reprocessamento mantém a versão anterior visível até a nova transação ser validada.

## 11. Frontend

### Lista

- Mostrar data/hora real e indicador de aproximação quando aplicável.
- Exibir `Processing`, `Partial` ou `Failed` sem apresentar dados derivados como prontos.
- Adicionar contadores compactos de recorded e suggested next steps.

### Modal de reunião

- Seção `Overview` com o resumo atual.
- Seção `Recorded next steps` antes de `Suggested next steps`.
- Sugestões usam tratamento visual e texto inequívocos: “Suggested by AI”.
- Cada item abre a transcript no primeiro timestamp de evidência.
- Owner ou prazo ausentes aparecem como desconhecidos, nunca inferidos.

## 12. Falhas e consistência

- Persistência de cada versão do brief ocorre em transação única.
- Falha de LLM não remove a última versão pronta.
- Falha de embedding deixa a reunião `partial` e fora do Quick Chat até reprocessamento.
- Exclusão de reunião remove captions, chunks, itens e evidências em cascata.
- Sync é idempotente por `meeting_id + source_etag + pipeline_version`.
- Alteração no VTT invalida overview, brief, chunks e embeddings.

## 13. Observabilidade

Registrar por reunião:

- Duração de cada estágio.
- Quantidade de captions, chunks, brief items e next steps.
- Tokens/chamadas LLM.
- Itens rejeitados pelo validador e motivo.
- Fonte/qualidade temporal.
- Versões de pipeline, chunker, extractor e embedding.

Nunca registrar transcript completo, prompts completos ou secrets.

## 14. Migração e rollout

1. Criar tabelas e colunas de forma compatível.
2. Atualizar parser VTT e adapter R2 paginado.
3. Implementar persistência de captions e proveniência temporal.
4. Migrar overview para saída estruturada.
5. Implementar brief, evidence validation e next steps.
6. Implementar chunks, FTS5 e sqlite-vec.
7. Atualizar APIs e UI.
8. Regenerar/reenviar corpus de demonstração com timestamps completos.
9. Backfill idempotente das reuniões legadas.
10. Só então habilitar o Quick Chat global.

## 15. Testes

### Unitários

- Parsing de metadata temporal e precedência das fontes.
- Cálculo de `ended_at`.
- IDs estáveis de captions e chunks.
- Validação de quotes, owners e prazos.
- Separação entre recorded e suggested next steps.
- Chunking sem cruzar reuniões.
- Fusão de ranking lexical e vetorial.

### Integração

- Sync paginado com mais de 100 objetos.
- Reprocessamento idempotente e por versão.
- Falha parcial preserva última versão pronta.
- Exclusão em cascata.
- API lista e detalhe serializam todos os campos.
- Clique em evidência chega ao timestamp correto.

### Evals de LLM

Corpus dourado com pelo menos 20 reuniões e anotações de decisões, commitments, riscos e next steps. Medir:

- Precisão de evidência: 100% das referências existem e contêm o suporte citado.
- Owner/prazo inventado: 0 ocorrências aceitas.
- Separação recorded/suggested: 100%.
- Recall de recorded next steps: meta inicial ≥ 85%.

## 16. Critérios de aceitação

- [ ] Novas reuniões possuem horário com proveniência explícita.
- [ ] O sync percorre todos os objetos do R2.
- [ ] Captions e chunks sobrevivem a restart do backend.
- [ ] Meeting Brief retorna itens estruturados com Evidence references válidas.
- [ ] Recorded e suggested next steps nunca aparecem misturados.
- [ ] Sugestões não inventam owner ou prazo.
- [ ] Reuniões não prontas são identificadas e ficam fora do Quick Chat.
- [ ] Reprocessamento é idempotente e não apaga a última versão válida em caso de falha.
- [ ] A UI abre a evidência no trecho correto.

## 17. Arquivos principais previstos

```text
resume-ai-service/app/
  graphs/meeting_analysis/{state,nodes,prompts,graph}.py
  schemas/{meetings,meeting_brief}.py
  services/{database,ingestion,meeting_index,r2_storage}.py
  routers/meeting_summaries.py
src/
  entities/meeting/model/types.ts
  entities/meeting/ui/CallRow.tsx
  features/call-detail/*
transcript_generator/app/generator.py
```

Renomear componentes legados `Call*` é desejável, mas não bloqueia este SDD.
