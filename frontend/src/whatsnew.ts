/**
 * What Sketch can do now (decision 72), newest first.
 *
 * One list feeds the modal on the gallery, its corner card and /whats-new. The first entry is the newest: its `id` is
 * what a browser stores once it has seen the release. `video` is a silent clip in `sketch/public/whatsnew/`; an entry
 * without one, or whose file is missing, draws its icon in the clip's frame instead.
 */
export interface WhatsNewEntry {
  id: string
  /** The release, as an ISO date. */
  date: string
  title: string
  line: string
  /** A lucide class: the frame's picture when there is no clip. */
  icon: string
  video?: string
}

const clip = (id: string) => `/assets/sketch/whatsnew/${id}.mp4`

export const whatsNew: WhatsNewEntry[] = [
  {
    id: 'comments',
    date: '2026-10-30',
    title: 'Comments on prototypes',
    line: 'Pin a comment anywhere on a page, reply, @mention, resolve.',
    icon: 'lucide-message-circle',
    video: clip('comments'),
  },
  {
    id: 'invite',
    date: '2026-10-30',
    title: 'Invite teammates',
    line: 'Invite by GitHub username. Editors can add their own options and notes.',
    icon: 'lucide-user-plus',
    video: clip('invite'),
  },
  {
    id: 'teammates-options',
    date: '2026-10-30',
    title: "Teammates' options",
    line: 'See whose option is whose, then make the best one the default.',
    icon: 'lucide-users',
    video: clip('teammates-options'),
  },
  {
    id: 'canvas',
    date: '2026-10-30',
    title: 'Canvas',
    line: 'See every option of a component side by side, and comment on any of them.',
    icon: 'lucide-layout-grid',
    video: clip('canvas'),
  },
  {
    id: 'page-states',
    date: '2026-10-30',
    title: 'Page states',
    line: 'Flip a page to Loading, Empty or Error from the Demo pill, or see them all on the canvas.',
    icon: 'lucide-layers',
    video: clip('page-states'),
  },
  {
    id: 'annotations',
    date: '2026-10-30',
    title: 'Annotations',
    line: 'Leave notes and tweaks on the page, then hand them to your agent in one prompt.',
    icon: 'lucide-pencil',
    video: clip('annotations'),
  },
]

/** The newest entry's id: what "seen" means for a browser. */
export const newestId = whatsNew[0].id

const SEEN = 'sketch.whatsnew.seen'
const CARD = 'sketch.whatsnew.card'

/** Storage can be off (private windows, blocked cookies). Then nothing is remembered and nothing throws. */
function read(key: string): string {
  try {
    return window.localStorage.getItem(key) ?? ''
  } catch {
    return ''
  }
}

function write(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value)
  } catch {
    // Not remembered. The modal comes back next visit, which is the safe way to fail.
  }
}

export const seenRelease = (): boolean => read(SEEN) === newestId
export const markSeen = (): void => write(SEEN, newestId)
export const cardDismissed = (): boolean => read(CARD) === newestId
export const dismissCard = (): void => write(CARD, newestId)

/** "2026-10-30" as "30 October 2026", the way the page heads a release. */
export function releaseDate(date: string): string {
  return new Date(`${date}T00:00:00`).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
}
