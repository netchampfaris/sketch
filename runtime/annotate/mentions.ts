// @mentions in a comment. The words box stays plain text: picking someone writes "@Full Name" into it, and when the
// comment is sent each one that was picked becomes "@[username]", the form the server stores (sketch/comments.py). So does
// a "@username" or an exact "@Full Name" typed by hand. The server keeps a mention only for someone on the list the page
// was given; any other "@xyz" stays plain text.
import { TOKEN, mentionable, type Mentionable } from './comments'

// Two people on the list share a name: only then does the list and the box show a username beside it.
export const hasTwin = (p: Mentionable) => mentionable.value.some((o) => o.username !== p.username && o.name === p.name)

// The label picked people go by in the box. Two people with one name tell apart by username.
export function labelOf(p: Mentionable): string {
  return `@${p.name}${hasTwin(p) ? ` (${p.username})` : ''}`
}

// What was picked in the box, by label. Cleared when the words are sent or the box is closed.
const picks = new Map<string, string>()
export const remember = (p: Mentionable) => picks.set(labelOf(p), p.username)
export const forget = () => picks.clear()

const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

// What is typed by hand counts as a pick: "@username", or "@Full Name" exactly, of someone on the list. A name two people
// share stays plain text unless it was picked, since typing it does not say which of them.
function typed(): Map<string, string> {
  const found = new Map<string, string>()
  for (const p of mentionable.value) {
    found.set(`@${p.username}`, p.username)
    if (!hasTwin(p)) found.set(`@${p.name}`, p.username)
  }
  return found
}

// The words as they are sent: each picked or typed label, where it still stands in the text, as @[username].
export function encode(text: string): string {
  let out = text
  const all = new Map([...typed(), ...picks])
  for (const [label, username] of [...all].sort((a, b) => b[0].length - a[0].length)) {
    out = out.replace(new RegExp(`(^|\\s)${escape(label)}(?![\\w-])`, 'g'), `$1@[${username}]`)
  }
  return out
}

// The words as they are edited: each @[username] as its label again, and picked again.
export function decode(text: string): string {
  return text.replace(TOKEN, (_, username: string) => {
    const p = mentionable.value.find((m) => m.username === username)
    if (!p) return `@${username}`
    remember(p)
    return labelOf(p)
  })
}

// The people a partial word names: by name or username, people whose name starts with it first.
export function match(query: string): Mentionable[] {
  const q = query.trim().toLowerCase()
  const all = mentionable.value
  if (!q) return all
  const starts = (s: string) => s.toLowerCase().split(/\s+/).some((w) => w.startsWith(q))
  const first = all.filter((p) => starts(p.name) || p.username.startsWith(q))
  const rest = all.filter((p) => !first.includes(p) && (p.name.toLowerCase().includes(q) || p.username.includes(q)))
  return [...first, ...rest]
}

// The open "@word" at the caret: where it starts and the word after the @, or null.
export function openMention(text: string, caret: number): { start: number; query: string } | null {
  const m = /(^|\s)@([^\s@]*)$/.exec(text.slice(0, caret))
  return m ? { start: caret - m[2].length - 1, query: m[2] } : null
}
