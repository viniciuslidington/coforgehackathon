import { colors } from '@/shared/config/tokens';
import type { MeetingSummary, Priority, SortKey } from '../model/types';

export function tierColor(tier: Priority): string {
  switch (tier) {
    case 'urgent': return colors.urgent;
    case 'high':   return colors.high;
    default:       return colors.textDimmest;
  }
}

export function tierLabel(tier: Priority): string {
  switch (tier) {
    case 'urgent': return 'Urgent';
    case 'high':   return 'High';
    default:       return 'Routine';
  }
}

export function sortMeetings(meetings: MeetingSummary[], key: SortKey): MeetingSummary[] {
  const sorted = [...meetings];
  if (key === 'priority') {
    return sorted.sort((a, b) => (b.priority_score ?? -1) - (a.priority_score ?? -1));
  }
  return sorted.sort((a, b) => (a.meeting_date < b.meeting_date ? 1 : -1));
}
