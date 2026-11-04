// Two small helpers both documents use: the shell (its toolbar and Tweak panel) and the frame agent (runtime/agent).
export const clamp = (n: number, lo: number, hi: number) => Math.max(lo, Math.min(n, hi))
// The person is typing in a field, so a letter is text, not a shortcut.
export const typing = (t: EventTarget | null) => {
  const el = t as HTMLElement | null
  return !!el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT' || el.isContentEditable)
}
