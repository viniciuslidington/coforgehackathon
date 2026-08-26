---
status: accepted
---

# Meeting scopes temporais exigem proveniência explícita do horário

Os seletores `Last 2 hours`, `Full shift` e `Custom range` só são confiáveis quando o horário da reunião tem origem conhecida. Escolhemos persistir `started_at`, `ended_at`, timezone e proveniência temporal; novas reuniões devem fornecer um `started_at` ISO-8601 na origem, enquanto registros legados podem usar o horário de upload apenas como aproximação identificada. O trade-off aceito é regenerar dados de demonstração e carregar metadados adicionais, em vez de tratar silenciosamente upload ou sync como horário da reunião.

## Consequences

- A ingestão calcula `ended_at` a partir de `started_at` e da duração quando não recebe um término explícito.
- Respostas dependentes de tempo sinalizam quando o meeting scope inclui horários aproximados.
- O corpus de demonstração deve ser regenerado ou reenviado com timestamps completos para validar janelas por hora e turno.
- `refreshed_at`, nomes de arquivos e offsets internos do VTT não podem ser usados como horário real da reunião.
