import { colors } from '@/shared/config/tokens';
import type {
  CallTypeFilter,
  MeetingSummary,
  Priority,
  PriorityFilter,
  SortColumn,
  SortDirection,
  SortKey,
} from '../model/types';

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

export function getCallType(meeting: Pick<MeetingSummary, 'meeting_id'> & Partial<Pick<MeetingSummary, 'participants' | 'call_type'>>): {
  type: 'hoot' | 'group';
  label: 'Hoot Call' | 'Group Call';
} {
  const rawType = (meeting.call_type || '').toLowerCase();
  if (rawType.includes('hoot')) return { type: 'hoot', label: 'Hoot Call' };
  if (rawType.includes('group') || rawType.includes('convo')) return { type: 'group', label: 'Group Call' };

  const id = (meeting.meeting_id || '').toLowerCase();
  const isHoot = id.includes('hoot') || (!id.includes('convo') && (meeting.participants?.length ?? 0) === 1);
  return {
    type: isHoot ? 'hoot' : 'group',
    label: isHoot ? 'Hoot Call' : 'Group Call',
  };
}

export function formatMeetingDate(dateStr: string): string {
  if (!dateStr) return '';
  const cleanDate = dateStr.split('T')[0];
  const parts = cleanDate.split('-');
  if (parts.length === 3) {
    const [year, month, day] = parts;
    return `${month.padStart(2, '0')}/${day.padStart(2, '0')}/${year}`;
  }
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return dateStr;
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  const yyyy = d.getFullYear();
  return `${mm}/${dd}/${yyyy}`;
}

export function filterMeetings(
  meetings: MeetingSummary[],
  typeFilter: CallTypeFilter = 'all',
  priorityFilter: PriorityFilter = 'all',
): MeetingSummary[] {
  return meetings.filter((meeting) => {
    if (typeFilter !== 'all') {
      const callType = getCallType(meeting).type;
      if (callType !== typeFilter) return false;
    }
    if (priorityFilter !== 'all') {
      const tier = meeting.priority_tier ?? 'normal';
      if (tier !== priorityFilter) return false;
    }
    return true;
  });
}

export function sortMeetings(
  meetings: MeetingSummary[],
  sortOrColumn: SortKey | SortColumn = 'date',
  direction: SortDirection = 'desc',
): MeetingSummary[] {
  const sorted = [...meetings];
  return sorted.sort((a, b) => {
    let comparison = 0;
    if (sortOrColumn === 'date' || sortOrColumn === 'time') {
      comparison = a.meeting_date.localeCompare(b.meeting_date);
    } else if (sortOrColumn === 'type') {
      const typeA = getCallType(a).label;
      const typeB = getCallType(b).label;
      comparison = typeA.localeCompare(typeB);
    } else if (sortOrColumn === 'priority') {
      const scoreA = a.priority_score ?? -1;
      const scoreB = b.priority_score ?? -1;
      comparison = scoreA - scoreB;
    }
    return direction === 'asc' ? comparison : -comparison;
  });
}
