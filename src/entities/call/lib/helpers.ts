import { colors } from '@/shared/config/tokens';
import type { Call, Priority, SortKey } from '../model/types';

/**
 * Returns the dot / accent colour for a given priority tier.
 */
export function tierColor(tier: Priority): string {
  switch (tier) {
    case 'urgent': return colors.urgent;
    case 'high':   return colors.high;
    default:       return colors.textDimmest;
  }
}

/**
 * Returns the human-readable label for a priority tier.
 */
export function tierLabel(tier: Priority): string {
  switch (tier) {
    case 'urgent': return 'Urgent';
    case 'high':   return 'High';
    default:       return 'Routine';
  }
}

/**
 * Filter calls by the maximum "ago" (minutes since now).
 */
export function filterByPeriod(calls: Call[], maxMinutes: number): Call[] {
  return calls.filter(c => c.ago <= maxMinutes);
}

/**
 * Sort calls by the given key.
 */
export function sortCalls(calls: Call[], key: SortKey): Call[] {
  const sorted = [...calls];
  switch (key) {
    case 'priority':
      return sorted.sort((a, b) => b.score - a.score);
    case 'mentions':
      return sorted.sort(
        (a, b) => b.mentions - a.mentions || b.score - a.score,
      );
    case 'time':
      return sorted.sort((a, b) => a.ago - b.ago);
    default:
      return sorted;
  }
}

/**
 * Generate a mock AI answer for a call-detail question.
 */
export function generateAnswer(call: Call, scopedRange: string | null): string {
  if (scopedRange) {
    return `In the selected range (${scopedRange}), ${call.cp} is pressing on one point only: they need a level and a deadline confirmation. Nothing else in that window is actionable.`;
  }
  return `On this call: ${call.summary.charAt(0).toLowerCase()}${call.summary.slice(1).replace(/\.$/, '')}. You were named ${call.mentions}× and the desk expects a response before the next fix.`;
}
