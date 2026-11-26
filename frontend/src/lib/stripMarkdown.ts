/**
 * Strips basic Markdown formatting tokens (**, __, *, _, `, #) and extra whitespace.
 * Optionally cleans up inline bullet metadata prefixes like "Category: ..." or "• Category: ...".
 */
export function stripMarkdown(text?: string | null): string {
  if (!text) return ''

  return text
    // Remove bold and italic markers: **text**, __text__, *text*, _text_
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/__([^_]+)__/g, '$1')
    .replace(/(^|[^\*])\*([^\*]+)\*([^\*]|$)/g, '$1$2$3')
    .replace(/(^|[^_])_([^_]+)_([^_]|$)/g, '$1$2$3')
    // Remove inline code ticks
    .replace(/`([^`]+)`/g, '$1')
    // Remove markdown header tokens at line beginnings
    .replace(/^#{1,6}\s+/gm, '')
    // Normalize bullets
    .replace(/^[•\-\*]\s+/gm, '• ')
    // Collapse any leftover stray double asterisks or backticks
    .replace(/\*\*/g, '')
    .replace(/``/g, '')
    // Normalize spaces and multiple blank lines
    .replace(/[ \t]+/g, ' ')
    .replace(/\n\s*\n\s*\n+/g, '\n\n')
    .trim()
}
