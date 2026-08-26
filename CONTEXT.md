# Shift Briefing — Meeting Insights

Processa reuniões gravadas (VTT) e produz resumos, chat grounded em transcript, e priorização determinística por tópico de interesse do usuário.

## Language

**Meeting** (`MeetingSummary`):
Uma reunião gravada, sincronizada via VTT do R2 e persistida com título, data, participantes, resumo e keywords.
_Avoid_: Call, chamada (termo legado de um domínio anterior de trading ao vivo que não existe no sistema; hoje só existe reunião gravada)

**Topic**:
Um termo ou frase de interesse definido pelo usuário na sessão atual (não persistido no backend), usado para calcular a relevância de cada reunião.
_Avoid_: Query, keyword (keyword já é um campo existente gerado por LLM no resumo da reunião — não confundir com tópico de busca do usuário)

**Priority score**:
Um valor 0–100, derivado da similaridade de cosseno entre o embedding de um tópico e o embedding de uma reunião, calculado de forma determinística (sem LLM, sem chamada externa). Quando o usuário define vários tópicos, o score de uma reunião é o **máximo** entre os matches individuais — cada tópico que ela satisfaz bem já basta.
_Avoid_: Relevance, match score

**Priority tier**:
A classificação discreta (`urgent` | `high` | `normal`) derivada do priority score por cortes fixos (`urgent ≥ 70`, `high ≥ 40`). Só existe quando há ao menos um tópico ativo — sem tópico, não há tier, não há badge.
_Avoid_: Urgency level

**Meeting embedding**:
Vetor pré-calculado (modelo multilíngue local, offline) a partir de `title` + `simple_summary` + `keywords` de uma reunião. Persistido junto com a reunião; recalculado quando o conteúdo desses campos muda.
_Avoid_: Vector, encoding

**Quick Chat**:
Conversa global usada para produzir briefings, oferecer direcionamento e investigar evidências em várias reuniões pertencentes ao meeting scope selecionado.
_Avoid_: Meeting Chat (conversa restrita a uma única reunião), chat geral

**Meeting scope**:
Conjunto de reuniões incluídas como fontes para uma pergunta do Quick Chat, definido pelo seletor ativo no momento em que a pergunta é enviada. Pode ser baseado em quantidade de reuniões ou em uma janela de tempo.
_Avoid_: Context (também pode significar histórico da conversa ou janela do modelo), todas as reuniões

**Scope change**:
Transição confirmada entre dois meeting scopes dentro da mesma conversa, registrada quando o usuário envia a primeira pergunta com um novo seletor ativo.
_Avoid_: Nova conversa, filtro silencioso

**Scope preset**:
Regra nomeada que resolve um meeting scope no instante da pergunta: `Last 5 meetings`, `Last 2 hours`, `Full shift` ou `Custom range`.
_Avoid_: Context pill, filtro de calls

**Quick Chat session**:
Uma conversa persistida do Quick Chat, contendo seu histórico e os meeting scopes usados em cada pergunta. Uma nova sessão só começa por ação explícita do usuário.
_Avoid_: Meeting Chat session, sessão de range

**Superseded information**:
Informação de uma reunião anterior substituída explicitamente por uma atualização encontrada em uma reunião posterior.
_Avoid_: Conflito (quando não está claro se a informação anterior foi substituída), informação apagada

**Meeting Brief**:
Representação estruturada derivada de uma reunião, contendo fatos como decisões, compromissos, riscos e questões em aberto, sempre ligados às evidências que os sustentam.
_Avoid_: Meeting summary (narrativa livre), transcript (registro integral), fonte de verdade autônoma

**Commitment**:
Declaração registrada em uma reunião na qual uma pessoa assume uma ação ou entrega, possivelmente com prazo.
_Avoid_: Task (pode existir em outro sistema), pendência confirmada

**Potentially open commitment**:
Commitment para o qual o meeting scope consultado não contém evidência posterior de conclusão ou cancelamento. Não afirma que o trabalho continua aberto fora das reuniões.
_Avoid_: Overdue task, pendência, compromisso não cumprido

**Recorded next step**:
Ação futura explicitamente combinada ou atribuída durante uma reunião, ligada ao trecho que comprova sua origem. Pode ser um commitment quando houver responsável.
_Avoid_: Suggested next step, tarefa importada

**Suggested next step**:
Recomendação de acompanhamento sintetizada pelo sistema a partir de riscos, bloqueios ou questões em aberto, sempre rotulada como sugestão e ligada às evidências que motivaram a recomendação.
_Avoid_: Recorded next step, commitment, decisão da reunião

**Participant alias**:
Forma alternativa confirmada de identificar o mesmo participante em diferentes reuniões.
_Avoid_: Correspondência inferida silenciosamente, nome parecido

**Pending scope change**:
Meeting scope selecionado, mas ainda não confirmado por uma pergunta ou pela geração de um briefing. Pode ser revertido sem alterar o histórico da conversa.
_Avoid_: Scope change, nova sessão

**Quick Chat coverage**:
Relação entre as reuniões consultadas com sucesso e todas as reuniões pertencentes ao meeting scope de uma resposta. Deve acompanhar respostas incompletas.
_Avoid_: Confidence score, quantidade de citações

**Evidence reference**:
Ligação entre uma afirmação da resposta e sua origem em uma reunião, identificando a reunião e, quando disponível, o trecho ou timestamp que sustenta a afirmação.
_Avoid_: Source genérica, referência sem origem
