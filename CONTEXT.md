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
