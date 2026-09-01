import type { ReactNode } from 'react';

/**
 * A dependency-free renderer for the small Markdown subset the agents emit,
 * with a seam for callers to claim their own inline spans.
 *
 * Everything here produces React elements — never `dangerouslySetInnerHTML` —
 * so model output cannot inject markup no matter what it contains. That is the
 * whole reason this is hand-rolled rather than delegated to a Markdown
 * library: the SDD requires displayed Markdown to be sanitized, and "we never
 * build HTML" is a stronger guarantee than "we strip the dangerous parts".
 */

/**
 * One inline construct a caller wants to own — a meeting citation, a
 * timestamp — scanned alongside the built-in emphasis rules rather than in a
 * separate pass over the same string.
 *
 * A rule may hold mutable state (see `onText`), so rules must be built fresh
 * per render. Do not memoize them: a rule that survives into the next render
 * carries a run counter that no longer matches the text being scanned.
 */
export interface InlineRule {
  /** Must carry the `g` flag; the scanner drives `lastIndex` itself. */
  pattern: RegExp;
  /**
   * Build the node for a match. Return `null` to disclaim the match and leave
   * its raw text in place; return `''` to consume it and emit nothing.
   */
  render: (match: RegExpExecArray, key: string) => ReactNode | null;
  /**
   * Called when text — or another rule's node — was emitted since this rule
   * last matched, and at every block boundary. Only rules whose output depends
   * on adjacency need it.
   */
  onText?: () => void;
}

const CODE_SPAN = /`([^`\n]+)`/g;
const BOLD = /\*\*([^\n]+?)\*\*/g;
const EMPHASIS = /(\*|_)([^*_\n]+?)\1/g;
// A model-supplied URL is a phishing vector and the SDD forbids trusting it,
// so a link keeps its label and loses its destination. An empty label is
// consumed outright rather than falling back to showing the URL.
const LINK = /\[([^\]\n]*)\]\([^)\s]*\)/g;

/**
 * CommonMark-lite flanking: a delimiter run must hug its content. Without this
 * `2 * 3 * 4` italicizes the 3, which is far more common in model output than
 * any emphasis it would otherwise catch.
 */
function isTight(content: string): boolean {
  return content.length > 0 && !/^\s/.test(content) && !/\s$/.test(content);
}

/**
 * `_` inside a word is almost always an identifier, not emphasis — without
 * this, `some_var_name` renders "var" in italics.
 *
 * Checked in JS against `match.input` rather than with a lookbehind, which
 * older Safari does not support.
 */
function isIntraword(match: RegExpExecArray): boolean {
  if (match[1] !== '_') return false;
  const before = match.input[match.index - 1] ?? '';
  const after = match.input[match.index + match[0].length] ?? '';
  return /\w/.test(before) || /\w/.test(after);
}

/**
 * `all` is a thunk because these rules are appended to the very array they
 * need in order to re-scan their own content — so nested emphasis and a
 * citation inside bold both work. Each nesting level strips at least two
 * delimiters, so the recursion is bounded by the input length.
 */
function emphasisRules(all: () => InlineRule[]): InlineRule[] {
  const nest = (source: string, key: string) => renderInline(source, all(), key);

  return [
    // Code first: whatever it wraps must survive untouched. Because the
    // scanner takes the earliest match and this renderer alone does not
    // recurse, a code span suppresses everything inside it without a mode
    // flag — `` `**x**` `` stays literal.
    { pattern: CODE_SPAN, render: (m, key) => <code key={key}>{m[1]}</code> },
    {
      pattern: BOLD,
      render: (m, key) => (isTight(m[1]) ? <strong key={key}>{nest(m[1], key)}</strong> : null),
    },
    {
      pattern: EMPHASIS,
      render: (m, key) =>
        isTight(m[2]) && !isIntraword(m) ? <em key={key}>{nest(m[2], key)}</em> : null,
    },
    { pattern: LINK, render: (m, key) => (m[1] ? <span key={key}>{nest(m[1], key)}</span> : '') },
  ];
}

/**
 * Scan `text` once, letting whichever rule matches earliest claim each span.
 *
 * Only the rules passed in are applied — there are no implicit built-ins, so a
 * caller that wants plain text with citations gets exactly that.
 */
export function renderInline(text: string, rules: InlineRule[], keyPrefix = ''): ReactNode[] {
  if (rules.length === 0) return [text];

  const nodes: ReactNode[] = [];
  let cursor = 0;

  // Emitting anything that is not `rule`'s own node breaks that rule's run.
  const notifyOthers = (rule: InlineRule | null) => {
    for (const candidate of rules) {
      if (candidate !== rule) candidate.onText?.();
    }
  };

  while (cursor < text.length) {
    let bestRule: InlineRule | null = null;
    let bestMatch: RegExpExecArray | null = null;

    // Every rule is re-queried from the cursor each pass, so a match that a
    // longer, earlier match swallowed is never reused.
    for (const rule of rules) {
      rule.pattern.lastIndex = cursor;
      const match = rule.pattern.exec(text);
      // Ties go to the earlier rule in the array, which is how callers give
      // their own constructs precedence over emphasis.
      if (match && (bestMatch === null || match.index < bestMatch.index)) {
        bestRule = rule;
        bestMatch = match;
      }
    }

    if (bestRule === null || bestMatch === null) break;

    if (bestMatch.index > cursor) {
      nodes.push(text.slice(cursor, bestMatch.index));
      notifyOthers(null);
    }

    const node = bestRule.render(bestMatch, `${keyPrefix}i${bestMatch.index}`);
    if (node === null) {
      // Disclaimed: the rule matched shape but not meaning, so this is prose.
      nodes.push(bestMatch[0]);
      notifyOthers(null);
    } else {
      nodes.push(node);
      notifyOthers(bestRule);
    }

    // A zero-length match would spin forever.
    cursor = bestMatch.index + Math.max(bestMatch[0].length, 1);
  }

  if (cursor < text.length) nodes.push(text.slice(cursor));
  return nodes;
}

type Block =
  | { kind: 'p'; lines: string[] }
  | { kind: 'ul' | 'ol'; items: string[] }
  | { kind: 'h'; level: number; text: string }
  | { kind: 'code'; text: string };

const FENCE = /^\s*```/;
const HEADING = /^\s{0,3}(#{1,6})\s+(.*)$/;
const BULLET = /^\s*[-*+]\s+(.*)$/;
const ORDERED = /^\s*\d+[.)]\s+(.*)$/;
const INDENTED = /^\s+\S/;

/**
 * Split into blocks line by line.
 *
 * Doing this before any inline scanning is what disambiguates `*`: a leading
 * `* ` is consumed here as a list marker, so the emphasis rules never see it.
 * `**bold at line start**` is not a bullet, because no space follows the run.
 */
function parseBlocks(text: string): Block[] {
  const blocks: Block[] = [];
  const lines = text.split('\n');
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];

    if (FENCE.test(line)) {
      const body: string[] = [];
      index += 1;
      while (index < lines.length && !FENCE.test(lines[index])) {
        body.push(lines[index]);
        index += 1;
      }
      // Skips the closing fence, or lands past the end when it was never
      // written — an unterminated fence renders as code rather than leaking.
      index += 1;
      blocks.push({ kind: 'code', text: body.join('\n') });
      continue;
    }

    if (!line.trim()) {
      index += 1;
      continue;
    }

    const heading = HEADING.exec(line);
    if (heading) {
      blocks.push({ kind: 'h', level: heading[1].length, text: heading[2].trim() });
      index += 1;
      continue;
    }

    const listKind = BULLET.test(line) ? 'ul' : ORDERED.test(line) ? 'ol' : null;
    if (listKind) {
      const items: string[] = [];
      while (index < lines.length) {
        const current = lines[index];
        const match = listKind === 'ul' ? BULLET.exec(current) : ORDERED.exec(current);
        if (match) {
          items.push(match[1].trim());
        } else if (items.length > 0 && INDENTED.test(current)) {
          // Nested lists are out of scope; a wrapped line joins the item above.
          items[items.length - 1] += ` ${current.trim()}`;
        } else {
          break;
        }
        index += 1;
      }
      blocks.push({ kind: listKind, items });
      continue;
    }

    const paragraph: string[] = [];
    while (index < lines.length) {
      const current = lines[index];
      if (
        !current.trim() ||
        FENCE.test(current) ||
        HEADING.test(current) ||
        BULLET.test(current) ||
        ORDERED.test(current)
      ) {
        break;
      }
      paragraph.push(current.trim());
      index += 1;
    }
    blocks.push({ kind: 'p', lines: paragraph });
  }

  return blocks;
}

/**
 * Render Markdown blocks, applying `extraRules` ahead of the built-in emphasis
 * rules so a caller's constructs win ties.
 */
export function renderRichText(text: string, extraRules: InlineRule[] = []): ReactNode[] {
  const rules: InlineRule[] = [...extraRules];
  rules.push(...emphasisRules(() => rules));

  // A run of adjacent matches never spans a block. Without this, one rule
  // instance shared across blocks would carry its counter into the next
  // paragraph — where the caller that split per paragraph got a fresh one.
  const startBlock = () => {
    for (const rule of rules) rule.onText?.();
  };

  return parseBlocks(text).map((block, index) => {
    const key = `b${index}`;
    startBlock();

    switch (block.kind) {
      case 'code':
        return (
          <pre key={key}>
            <code>{block.text}</code>
          </pre>
        );
      case 'h': {
        // Headings inside a chat bubble must not outrank the page's own, so
        // the six Markdown levels clamp into h4–h6.
        const Tag = (block.level <= 2 ? 'h4' : block.level === 3 ? 'h5' : 'h6') as 'h4' | 'h5' | 'h6';
        return <Tag key={key}>{renderInline(block.text, rules, key)}</Tag>;
      }
      case 'ul':
      case 'ol': {
        const Tag = block.kind;
        return (
          <Tag key={key}>
            {block.items.map((item, itemIndex) => (
              <li key={`${key}l${itemIndex}`}>{renderInline(item, rules, `${key}l${itemIndex}`)}</li>
            ))}
          </Tag>
        );
      }
      default:
        return <p key={key}>{renderInline(block.lines.join(' '), rules, key)}</p>;
    }
  });
}
