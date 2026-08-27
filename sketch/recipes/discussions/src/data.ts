// Fixture data for the Discussions prototype. There is no server.
import { computed, ref } from 'vue'

export interface Community {
  id: string
  name: string
  image: string
  unread?: number
}

export interface Space {
  name: string
  slug: string
  icon: string
  unread: number
}

export interface Discussion {
  id: number
  space: string
  title: string
  author: string
  image: string
  excerpt: string
  comments: number
  lastActivity: string
  unread: number
}

export interface Reply {
  author: string
  image: string
  time: string
  text: string
}

export const communities: Community[] = [
  {
    id: 'design',
    name: 'Design',
    image: 'https://github.com/figma.png?size=200',
  },
  {
    id: 'engineering',
    name: 'Engineering',
    unread: 4,
    image: 'https://avatars.githubusercontent.com/u/6128107?v=4',
  },
  {
    id: 'marketing',
    name: 'Marketing',
    image: 'https://avatars.githubusercontent.com/u/9919?v=4',
  },
]

/** The rail switches community in place. Shared, so every route reads one value. */
export const activeCommunity = ref('design')

/** The Settings dialog is opened from the rail and from the sidebar menu. */
export const showSettings = ref(false)
export const settingsTab = ref('profile')

export const spaces: Space[] = [
  { name: 'Announcements', slug: 'announcements', icon: 'lucide-megaphone', unread: 2 },
  { name: 'Design System', slug: 'design-system', icon: 'lucide-shapes', unread: 3 },
  { name: 'Website', slug: 'website', icon: 'lucide-globe', unread: 0 },
  { name: 'Brand', slug: 'brand', icon: 'lucide-sparkles', unread: 0 },
  { name: 'Illustrations', slug: 'illustrations', icon: 'lucide-pen-tool', unread: 1 },
  { name: 'Research', slug: 'research', icon: 'lucide-flask-conical', unread: 0 },
  { name: 'Archive', slug: 'archive', icon: 'lucide-archive', unread: 0 },
]

const rawDiscussions = [
  {
    title: 'Design review: new onboarding flow',
    author: 'Evan You',
    image: 'https://avatars.githubusercontent.com/u/499550?v=4',
    excerpt:
      'I went through the latest prototype and left comments on the empty states…',
    comments: 14,
    lastActivity: '2h',
    unread: 3,
  },
  {
    title: 'Proposal: consolidate icon sizes to a 4px grid',
    author: 'Priya Nair',
    image: 'https://i.pravatar.cc/150?img=5',
    excerpt:
      'We currently ship icons in 7 sizes. I propose we standardize on 16 / 20 / 24…',
    comments: 32,
    lastActivity: '5h',
    unread: 1,
  },
  {
    title: 'Dark mode tokens are ready for review',
    author: 'Sam Rivera',
    image: 'https://i.pravatar.cc/150?img=12',
    excerpt:
      'All semantic tokens now have dark values. The contrast checks pass except…',
    comments: 21,
    lastActivity: '1d',
    unread: 5,
  },
  {
    title: 'Q3 roadmap discussion',
    author: 'Ana Costa',
    image: 'https://i.pravatar.cc/150?img=20',
    excerpt:
      'Carrying over from the planning call — here are the three themes we agreed on…',
    comments: 8,
    lastActivity: '2d',
    unread: 0,
  },
  {
    title: 'Weekly design crit — notes and action items',
    author: 'Maya Iyer',
    image: 'https://i.pravatar.cc/150?img=27',
    excerpt:
      'Thanks everyone for joining. Summary of the feedback on the settings redesign…',
    comments: 5,
    lastActivity: '3d',
    unread: 0,
  },
  {
    title: 'Rethinking the empty state illustrations',
    author: 'Leo Martins',
    image: 'https://i.pravatar.cc/150?img=33',
    excerpt:
      'The current set feels dated. I sketched a lighter, more geometric direction…',
    comments: 17,
    lastActivity: '4h',
    unread: 2,
  },
  {
    title: 'Naming convention for spacing tokens',
    author: 'Nadia Haddad',
    image: 'https://i.pravatar.cc/150?img=40',
    excerpt:
      'Are we going with t-shirt sizes or numeric steps? Both have tradeoffs for…',
    comments: 26,
    lastActivity: '6h',
    unread: 4,
  },
  {
    title: 'Accessibility audit results are in',
    author: 'Tom Becker',
    image: 'https://i.pravatar.cc/150?img=47',
    excerpt:
      'We failed 6 of the WCAG AA checks, mostly around focus visibility and…',
    comments: 41,
    lastActivity: '8h',
    unread: 7,
  },
  {
    title: 'Should tooltips have a max width?',
    author: 'Yuki Tanaka',
    image: 'https://i.pravatar.cc/150?img=53',
    excerpt:
      'Long labels wrap awkwardly right now. I think capping at 240px reads better…',
    comments: 9,
    lastActivity: '10h',
    unread: 0,
  },
  {
    title: 'Migrating buttons to the new variant API',
    author: 'Chris Doyle',
    image: 'https://i.pravatar.cc/150?img=60',
    excerpt:
      'Codemod is ready. It covers ~90% of call sites; the rest need a manual pass…',
    comments: 18,
    lastActivity: '12h',
    unread: 1,
  },
  {
    title: 'Feedback wanted: revised color ramp',
    author: 'Isabel Ortiz',
    image: 'https://i.pravatar.cc/150?img=64',
    excerpt:
      'Bumped the mid-tones for better contrast. Take a look at gray-5 through 7…',
    comments: 23,
    lastActivity: '1d',
    unread: 0,
  },
  {
    title: 'Motion guidelines — first draft',
    author: 'Omar Farouk',
    image: 'https://i.pravatar.cc/150?img=68',
    excerpt:
      'Durations, easing curves, and when not to animate. Would love a sanity check…',
    comments: 12,
    lastActivity: '1d',
    unread: 3,
  },
  {
    title: 'Consolidating our avatar sizes',
    author: 'Evan You',
    image: 'https://avatars.githubusercontent.com/u/499550?v=4',
    excerpt:
      'We have nine avatar sizes across the app. Proposing we trim to five…',
    comments: 15,
    lastActivity: '1d',
    unread: 0,
  },
  {
    title: 'New illustration style exploration',
    author: 'Priya Nair',
    image: 'https://i.pravatar.cc/150?img=5',
    excerpt:
      'Playing with a two-tone approach that scales down cleanly to 16px marks…',
    comments: 7,
    lastActivity: '2d',
    unread: 2,
  },
  {
    title: 'Form validation patterns need a rethink',
    author: 'Sam Rivera',
    image: 'https://i.pravatar.cc/150?img=12',
    excerpt:
      'Inline vs. on-submit is inconsistent. Here is a proposal to unify the rules…',
    comments: 29,
    lastActivity: '2d',
    unread: 1,
  },
  {
    title: 'Grid system: 12 columns or 16?',
    author: 'Ana Costa',
    image: 'https://i.pravatar.cc/150?img=20',
    excerpt:
      'Marketing pages want 16 for flexibility; app screens are fine with 12…',
    comments: 34,
    lastActivity: '2d',
    unread: 0,
  },
  {
    title: 'Deprecating the old card component',
    author: 'Maya Iyer',
    image: 'https://i.pravatar.cc/150?img=27',
    excerpt:
      'Usage is down to a handful of pages. Plan and timeline for removal inside…',
    comments: 11,
    lastActivity: '3d',
    unread: 4,
  },
  {
    title: 'Typography scale is drifting',
    author: 'Leo Martins',
    image: 'https://i.pravatar.cc/150?img=33',
    excerpt:
      'Found four one-off font sizes shipped last month. We should lock the scale…',
    comments: 20,
    lastActivity: '3d',
    unread: 0,
  },
  {
    title: 'Redesigning the notification center',
    author: 'Nadia Haddad',
    image: 'https://i.pravatar.cc/150?img=40',
    excerpt:
      'Grouping by source instead of time tested much better with the research group…',
    comments: 16,
    lastActivity: '3d',
    unread: 2,
  },
  {
    title: 'Loading states: skeletons vs. spinners',
    author: 'Tom Becker',
    image: 'https://i.pravatar.cc/150?img=47',
    excerpt:
      'For lists, skeletons feel faster. For actions, a spinner is clearer. Thoughts?',
    comments: 13,
    lastActivity: '4d',
    unread: 0,
  },
  {
    title: 'Standardizing our elevation shadows',
    author: 'Yuki Tanaka',
    image: 'https://i.pravatar.cc/150?img=53',
    excerpt:
      'We have five ad-hoc shadow values. Proposing a three-step elevation scale…',
    comments: 10,
    lastActivity: '4d',
    unread: 1,
  },
  {
    title: 'Rewriting the getting-started docs',
    author: 'Chris Doyle',
    image: 'https://i.pravatar.cc/150?img=60',
    excerpt:
      'The install section is confusing newcomers. Drafted a shorter, task-first flow…',
    comments: 8,
    lastActivity: '4d',
    unread: 0,
  },
  {
    title: 'Should we ship a compact density mode?',
    author: 'Isabel Ortiz',
    image: 'https://i.pravatar.cc/150?img=64',
    excerpt:
      'Power users keep asking for tighter rows. Here is what a density toggle costs…',
    comments: 27,
    lastActivity: '5d',
    unread: 3,
  },
  {
    title: 'Iconography for the new task types',
    author: 'Omar Farouk',
    image: 'https://i.pravatar.cc/150?img=68',
    excerpt:
      'Need six new glyphs. First pass attached — the "blocked" one still feels off…',
    comments: 14,
    lastActivity: '5d',
    unread: 0,
  },
  {
    title: 'Consistent focus-ring across components',
    author: 'Evan You',
    image: 'https://avatars.githubusercontent.com/u/499550?v=4',
    excerpt:
      'Some components use outline, others box-shadow. Unifying on the token now…',
    comments: 19,
    lastActivity: '5d',
    unread: 2,
  },
  {
    title: 'Rethinking our modal sizes',
    author: 'Priya Nair',
    image: 'https://i.pravatar.cc/150?img=5',
    excerpt:
      'The 5xl modal is overused for content that would fit a drawer. A quick audit…',
    comments: 6,
    lastActivity: '6d',
    unread: 0,
  },
  {
    title: 'Brand refresh: logo lockups',
    author: 'Sam Rivera',
    image: 'https://i.pravatar.cc/150?img=12',
    excerpt:
      'Three lockup options for the wordmark. My vote is B, but curious what you think…',
    comments: 31,
    lastActivity: '6d',
    unread: 1,
  },
  {
    title: 'Data table: sticky headers and columns',
    author: 'Ana Costa',
    image: 'https://i.pravatar.cc/150?img=20',
    excerpt:
      'Prototype works but perf drops past 500 rows. Looking for virtualization ideas…',
    comments: 22,
    lastActivity: '6d',
    unread: 0,
  },
  {
    title: 'Emoji reactions — which set to support?',
    author: 'Maya Iyer',
    image: 'https://i.pravatar.cc/150?img=27',
    excerpt:
      'Native vs. a custom curated set. Custom is on-brand but a maintenance cost…',
    comments: 17,
    lastActivity: '1w',
    unread: 5,
  },
  {
    title: 'Standard page header anatomy',
    author: 'Leo Martins',
    image: 'https://i.pravatar.cc/150?img=33',
    excerpt:
      'Title, actions, tabs — where does each go? Documenting the canonical layout…',
    comments: 9,
    lastActivity: '1w',
    unread: 0,
  },
  {
    title: 'Onboarding checklist component',
    author: 'Nadia Haddad',
    image: 'https://i.pravatar.cc/150?img=40',
    excerpt:
      'A reusable progress checklist for first-run. Spec and edge cases inside…',
    comments: 12,
    lastActivity: '1w',
    unread: 0,
  },
  {
    title: 'Retiring the legacy TextEditor styles',
    author: 'Tom Becker',
    image: 'https://i.pravatar.cc/150?img=47',
    excerpt:
      'Old prose styles still bleed into the new editor. Mapped every conflict here…',
    comments: 24,
    lastActivity: '1w',
    unread: 2,
  },
  {
    title: 'Postmortem: the settings dialog regression',
    author: 'Yuki Tanaka',
    image: 'https://i.pravatar.cc/150?img=53',
    excerpt:
      'Cold-load rendered a blank panel. Root cause and the fix we shipped inside…',
    comments: 15,
    lastActivity: '2w',
    unread: 0,
  },
]

// Each row gets an id for the thread link and a space, so every space route
// shows its own feed.
export const discussions: Discussion[] = rawDiscussions.map((d, i) => ({
  ...d,
  id: i,
  space: spaces[i % spaces.length].name,
}))

export function discussionsInSpace(space: string): Discussion[] {
  return discussions.filter((d) => d.space === space)
}

export function findDiscussion(id: number): Discussion {
  return discussions.find((d) => d.id === id) ?? discussions[0]
}

/** Two closing paragraphs. They follow the excerpt in every thread. */
export const threadBody: string[] = [
  'Full notes and the linked files sit in the thread below. I tagged the people who own each open point, so nothing waits on me.',
  'Add anything I missed before Friday. I will fold the feedback into one revision and post the result here.',
]

export const threadReplies: Reply[] = [
  {
    author: 'Priya Nair',
    image: 'https://i.pravatar.cc/150?img=5',
    time: '2h',
    text: 'Agreed on the checklist. The progress bar answers the one question every new user asks, so keep it.',
  },
  {
    author: 'Sam Rivera',
    image: 'https://i.pravatar.cc/150?img=12',
    time: '1h',
    text: 'Dark values pass contrast everywhere except the skipped state. I will send a corrected token today.',
  },
  {
    author: 'Ana Costa',
    image: 'https://i.pravatar.cc/150?img=20',
    time: '48m',
    text: 'Can we seed the sample data behind a button? Automatic seeding surprised two people in the last round.',
  },
  {
    author: 'Maya Iyer',
    image: 'https://i.pravatar.cc/150?img=27',
    time: '20m',
    text: 'I wrote the SSO copy for the invite step. It is in the shared doc, second section.',
  },
]

export const spaceActions = [
  { label: 'Copy link', icon: 'lucide-link' },
  { label: 'Mark all as read', icon: 'lucide-check' },
  { label: 'Manage access', icon: 'lucide-users' },
  { label: 'Archive', icon: 'lucide-archive' },
]

// Profile
export const firstName = ref('Rhea')
export const lastName = ref('Kapoor')
export const bio = ref('Product designer. I care about type scales and empty states.')
export const fullName = computed(() => `${firstName.value} ${lastName.value}`.trim())
export const userImage = 'https://i.pravatar.cc/150?img=3'

// Preferences
export const theme = ref('system')
export const cursorStyle = ref('pointer')
export const badgeStyle = ref('Unread count')
export const spaceSort = ref('Recent activity')
export const hideInactiveSpaces = ref(false)

// Notifications
export const emailDigestEnabled = ref(true)
export const digestFrequency = ref('Weekly')
export const digestDay = ref('Monday')

// App settings and administration
export const managedCommunities = [
  {
    name: 'Design',
    spaces: 7,
    members: 18,
    image: 'https://i.pravatar.cc/150?img=33',
  },
  {
    name: 'Engineering',
    spaces: 12,
    members: 34,
    image: 'https://i.pravatar.cc/150?img=40',
  },
  {
    name: 'Marketing',
    spaces: 5,
    members: 11,
    image: 'https://i.pravatar.cc/150?img=47',
  },
]

export const customEmojis = ['🎉', '🚀', '👀', '💡', '✅', '🔥']

export const members = [
  {
    name: 'Rhea Kapoor',
    email: 'rhea@example.com',
    role: 'Admin',
    image: 'https://i.pravatar.cc/150?img=53',
  },
  {
    name: 'Evan You',
    email: 'evan@example.com',
    role: 'Member',
    image: 'https://i.pravatar.cc/150?img=60',
  },
  {
    name: 'Priya Nair',
    email: 'priya@example.com',
    role: 'Member',
    image: 'https://i.pravatar.cc/150?img=64',
  },
  {
    name: 'Sam Rivera',
    email: 'sam@example.com',
    role: 'Guest',
    image: 'https://i.pravatar.cc/150?img=68',
  },
]
