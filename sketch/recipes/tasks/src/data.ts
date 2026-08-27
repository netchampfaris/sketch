// Fixture data for the Tasks prototype. There is no server, so the tasks live
// in a `reactive` array. The detail panel edits it in place.
import { reactive } from 'vue'


const statuses = ['Backlog', 'Todo', 'In Progress', 'Done', 'Canceled']
const statusIcon = {
  Backlog: 'lucide-circle-dashed',
  Todo: 'lucide-circle',
  'In Progress': 'lucide-circle-dot',
  Done: 'lucide-circle-check',
  Canceled: 'lucide-circle-x',
}
const priorities = ['High', 'Medium', 'Low']
// Linear-style signal icons: more bars = higher priority. The bar count already
// encodes severity. Color reinforces it: hot for High, warm for Medium, muted
// for Low so low-priority rows recede.
const priorityIcon = {
  High: 'lucide-signal-high',
  Medium: 'lucide-signal-medium',
  Low: 'lucide-signal-low',
}
const priorityColor = {
  High: 'text-ink-red-6',
  Medium: 'text-ink-amber-6',
  Low: 'text-ink-gray-5',
}

// Linear-style labels. The theme only tints the badge. The label text
// carries the meaning, so the palette can stay small.
const labelTheme = {
  Bug: 'red',
  Feature: 'blue',
  Improvement: 'green',
  Design: 'violet',
  Research: 'amber',
  Backend: 'gray',
  Frontend: 'gray',
  Docs: 'gray',
  Chore: 'gray',
}
// Labels render as neutral gray-outline badges so the column stays quiet; the
// only color is a small dot that keeps each label recognizable at a glance.
const themeDot = {
  red: 'bg-surface-red-6',
  blue: 'bg-surface-blue-6',
  green: 'bg-surface-green-6',
  amber: 'bg-surface-amber-6',
  violet: 'bg-surface-violet-6',
  gray: 'bg-surface-gray-6',
}
const labelDotClass = (label) => themeDot[labelTheme[label]]

const me = 'Rhea Kapoor'
const people = [
  { name: 'Rhea Kapoor', image: 'https://i.pravatar.cc/150?img=1' },
  {
    name: 'Evan You',
    image: 'https://avatars.githubusercontent.com/u/499550?v=4',
  },
  { name: 'Priya Nair', image: 'https://i.pravatar.cc/150?img=5' },
  { name: 'Sam Rivera', image: 'https://i.pravatar.cc/150?img=12' },
  { name: 'Ana Costa', image: 'https://i.pravatar.cc/150?img=20' },
  { name: 'Maya Iyer', image: 'https://i.pravatar.cc/150?img=27' },
]
const imageOf = (name) => people.find((p) => p.name === name)?.image

const projects = [
  { name: 'Website Redesign', icon: 'lucide-globe' },
  { name: 'Mobile App', icon: 'lucide-smartphone' },
  { name: 'Design System', icon: 'lucide-shapes' },
  { name: 'Q3 Launch', icon: 'lucide-rocket' },
]

const tasks = reactive([
  // Website Redesign
  {
    id: 245,
    title: 'Fix layout shift on the pricing page',
    project: 'Website Redesign',
    status: 'In Progress',
    priority: 'High',
    labels: ['Bug', 'Frontend'],
    assignees: ['Priya Nair'],
    owner: 'Rhea Kapoor',
    due: '2026-07-06',
    description:
      'The hero image loads without reserved space, so the whole page jumps once it decodes. Set explicit dimensions and measure CLS before and after.',
    comments: [],
  },
  {
    id: 231,
    title: 'Fix validation errors in the checkout flow',
    project: 'Website Redesign',
    status: 'In Progress',
    priority: 'High',
    labels: ['Bug', 'Frontend'],
    assignees: ['Rhea Kapoor', 'Evan You'],
    owner: 'Evan You',
    due: '2026-07-06',
    description:
      'The payment step accepts an empty billing address and then fails at the gateway with a generic error. Validate required fields inline, surface gateway errors next to the affected field, and keep the entered card details on retry.',
    comments: [
      {
        author: 'Evan You',
        time: '2h ago',
        text: 'Reproduced it. The address form skips validation when you pay with a saved card. That path is probably the real bug.',
      },
      {
        author: 'Rhea Kapoor',
        time: '1h ago',
        text: 'Agreed. Fixing the saved-card path first, then adding inline errors for the rest of the form.',
      },
    ],
  },
  {
    id: 228,
    title: 'Migrate marketing pages to the new CMS',
    project: 'Website Redesign',
    status: 'In Progress',
    priority: 'Medium',
    labels: ['Feature', 'Backend'],
    assignees: ['Priya Nair'],
    owner: 'Rhea Kapoor',
    due: '2026-07-08',
    description:
      'Move the pricing, about, and careers pages off the legacy templates. Content is already exported. Wire up the new layouts and set redirects for the old URLs.',
    comments: [],
  },
  {
    id: 242,
    title: 'Rebuild the top navigation as a sticky header',
    project: 'Website Redesign',
    status: 'Todo',
    priority: 'Medium',
    labels: ['Feature', 'Frontend'],
    assignees: ['Sam Rivera'],
    owner: 'Rhea Kapoor',
    due: '2026-07-11',
    description:
      'The nav should stay pinned on scroll and collapse into a compact bar past the fold. Keep the mega-menu behavior on desktop and the drawer on mobile.',
    comments: [],
  },
  {
    id: 238,
    title: 'Add dark mode to the marketing site',
    project: 'Website Redesign',
    status: 'Todo',
    priority: 'High',
    labels: ['Feature', 'Design'],
    assignees: ['Evan You'],
    owner: 'Ana Costa',
    due: '2026-07-14',
    description:
      'Respect the OS preference by default and add a manual toggle in the footer. Audit the illustrations for both themes before shipping.',
    comments: [],
  },
  {
    id: 221,
    title: 'Consolidate duplicate utility classes',
    project: 'Website Redesign',
    status: 'Backlog',
    priority: 'Low',
    labels: ['Chore', 'Frontend'],
    assignees: ['Maya Iyer'],
    owner: 'Sam Rivera',
    due: '',
    description:
      'The stylesheet has grown three near-identical spacing helpers. Collapse them to the token scale and delete the dead rules.',
    comments: [],
  },
  {
    id: 216,
    title: 'Set up analytics events for the signup funnel',
    project: 'Website Redesign',
    status: 'Backlog',
    priority: 'Medium',
    labels: ['Backend'],
    assignees: ['Sam Rivera'],
    owner: 'Rhea Kapoor',
    due: '',
    description:
      'Instrument each step of the signup funnel so we can see where people drop off. Match the event names to the existing dashboard schema.',
    comments: [],
  },
  {
    id: 199,
    title: 'Launch the redesigned homepage',
    project: 'Website Redesign',
    status: 'Done',
    priority: 'High',
    labels: ['Feature'],
    assignees: ['Rhea Kapoor'],
    owner: 'Rhea Kapoor',
    due: '2026-06-28',
    description:
      'Final cutover from the old homepage. Redirects verified, Lighthouse scores green, and the old template archived.',
    comments: [],
  },
  {
    id: 203,
    title: 'Prototype animated page transitions',
    project: 'Website Redesign',
    status: 'Canceled',
    priority: 'Low',
    labels: ['Research'],
    assignees: ['Evan You'],
    owner: 'Evan You',
    due: '',
    description:
      'Dropped in favor of shipping the redesign sooner. Revisit after launch.',
    comments: [],
  },

  // Mobile App
  {
    id: 244,
    title: 'Fix push notifications not arriving on iOS 17',
    project: 'Mobile App',
    status: 'In Progress',
    priority: 'High',
    labels: ['Bug', 'Backend'],
    assignees: ['Sam Rivera'],
    owner: 'Rhea Kapoor',
    due: '2026-07-07',
    description:
      'A chunk of iOS 17 devices stopped receiving pushes after the last release. Suspect the APNs token refresh. Add logging around registration and compare against Android.',
    comments: [
      {
        author: 'Sam Rivera',
        time: '5h ago',
        text: 'Tokens look stale for users who upgraded in place. Testing a forced re-registration on launch.',
      },
    ],
  },
  {
    id: 241,
    title: 'Add biometric login',
    project: 'Mobile App',
    status: 'In Progress',
    priority: 'Medium',
    labels: ['Feature'],
    assignees: ['Evan You'],
    owner: 'Priya Nair',
    due: '2026-07-09',
    description:
      'Let people unlock the app with Face ID / fingerprint after the first password login. Fall back to the passcode when biometrics fail twice.',
    comments: [],
  },
  {
    id: 235,
    title: 'Review the onboarding flow prototype',
    project: 'Mobile App',
    status: 'Todo',
    priority: 'High',
    labels: ['Design'],
    assignees: ['Rhea Kapoor'],
    owner: 'Ana Costa',
    due: '2026-07-07',
    description:
      'Second iteration is up. Focus on the empty states and the progress indicator. Both changed since the last review.',
    comments: [
      {
        author: 'Ana Costa',
        time: '1d ago',
        text: 'Prototype link is in the project description. The step counter is the part I am least sure about.',
      },
    ],
  },
  {
    id: 237,
    title: 'Build offline mode for the task list',
    project: 'Mobile App',
    status: 'Todo',
    priority: 'High',
    labels: ['Feature'],
    assignees: ['Priya Nair'],
    owner: 'Rhea Kapoor',
    due: '2026-07-13',
    description:
      'Cache the task list locally and queue edits made while offline, then reconcile on reconnect. Show a clear indicator when changes are pending sync.',
    comments: [],
  },
  {
    id: 233,
    title: 'Set up crash reporting for the beta build',
    project: 'Mobile App',
    status: 'Todo',
    priority: 'Medium',
    labels: ['Improvement'],
    assignees: ['Sam Rivera'],
    owner: 'Rhea Kapoor',
    due: '2026-07-10',
    description:
      'Beta testers are reporting crashes we cannot reproduce. Add a crash reporter to the beta build and symbolicate stack traces in CI so reports arrive readable.',
    comments: [],
  },
  {
    id: 230,
    title: 'Reduce app cold-start time',
    project: 'Mobile App',
    status: 'Backlog',
    priority: 'Medium',
    labels: ['Improvement'],
    assignees: ['Sam Rivera'],
    owner: 'Rhea Kapoor',
    due: '',
    description:
      'Cold start is over two seconds on mid-range Android devices. Profile the launch path and defer anything that is not needed for the first screen.',
    comments: [],
  },
  {
    id: 224,
    title: 'Localize the app into Spanish and German',
    project: 'Mobile App',
    status: 'Backlog',
    priority: 'Low',
    labels: ['Feature'],
    assignees: ['Ana Costa'],
    owner: 'Maya Iyer',
    due: '',
    description:
      'Extract the remaining hardcoded strings, wire up the translation files, and check the layouts for text that overflows once translated.',
    comments: [],
  },
  {
    id: 210,
    title: 'Ship the redesigned tab bar',
    project: 'Mobile App',
    status: 'Done',
    priority: 'High',
    labels: ['Design'],
    assignees: ['Maya Iyer'],
    owner: 'Rhea Kapoor',
    due: '2026-06-30',
    description:
      'New five-tab layout with the create action promoted to the center. Rolled out to 100% after a clean week on the beta channel.',
    comments: [],
  },

  // Design System
  {
    id: 236,
    title: 'Migrate components to design tokens',
    project: 'Design System',
    status: 'In Progress',
    priority: 'High',
    labels: ['Improvement', 'Frontend'],
    assignees: ['Maya Iyer'],
    owner: 'Rhea Kapoor',
    due: '2026-07-08',
    description:
      'Replace the remaining hardcoded colors and spacing with semantic tokens so theming works in one place. Start with the form controls.',
    comments: [],
  },
  {
    id: 229,
    title: 'Document the Button component API',
    project: 'Design System',
    status: 'Todo',
    priority: 'Medium',
    labels: ['Docs'],
    assignees: ['Priya Nair'],
    owner: 'Rhea Kapoor',
    due: '2026-07-12',
    description:
      'Write the props table, list every variant and size, and add copy-paste examples for the common cases. Link it from the component page.',
    comments: [],
  },
  {
    id: 222,
    title: 'Add a DatePicker component',
    project: 'Design System',
    status: 'Todo',
    priority: 'High',
    labels: ['Feature', 'Frontend'],
    assignees: ['Evan You'],
    owner: 'Maya Iyer',
    due: '2026-07-16',
    description:
      'A keyboard-accessible date picker with range support and a text input fallback. Match the existing popover and token conventions.',
    comments: [],
  },
  {
    id: 219,
    title: 'Explore a two-tone illustration style',
    project: 'Design System',
    status: 'Backlog',
    priority: 'Low',
    labels: ['Design', 'Research'],
    assignees: ['Maya Iyer'],
    owner: 'Priya Nair',
    due: '',
    description:
      'A lighter, more geometric direction that scales down cleanly to 16px marks. Timebox to a week of exploration.',
    comments: [],
  },
  {
    id: 214,
    title: 'Audit spacing token usage across marketing pages',
    project: 'Design System',
    status: 'Backlog',
    priority: 'Medium',
    labels: ['Chore'],
    assignees: [],
    owner: 'Sam Rivera',
    due: '',
    description:
      'Marketing pages have drifted from the spacing scale. List the offending pages and the one-off values they use.',
    comments: [],
  },
  {
    id: 212,
    title: 'Audit color contrast for accessibility',
    project: 'Design System',
    status: 'Backlog',
    priority: 'Low',
    labels: ['Research', 'Design'],
    assignees: ['Ana Costa'],
    owner: 'Priya Nair',
    due: '',
    description:
      'Check text and interactive colors against WCAG AA in both themes. Flag the tokens that fail and propose adjusted values.',
    comments: [],
  },
  {
    id: 208,
    title: 'Ship empty-state illustrations',
    project: 'Design System',
    status: 'Done',
    priority: 'High',
    labels: ['Design'],
    assignees: ['Rhea Kapoor'],
    owner: 'Rhea Kapoor',
    due: '2026-07-01',
    description:
      'Final set of six empty-state illustrations, exported for both themes and wired into the component library.',
    comments: [
      {
        author: 'Priya Nair',
        time: '3d ago',
        text: 'These look great in the app. Nice work!',
      },
    ],
  },
  {
    id: 205,
    title: 'Publish the icon library v2',
    project: 'Design System',
    status: 'Done',
    priority: 'Medium',
    labels: ['Design'],
    assignees: ['Maya Iyer'],
    owner: 'Rhea Kapoor',
    due: '2026-06-27',
    description:
      'Redrawn on a consistent 24px grid with a lighter stroke. Published to the package and the Figma library in sync.',
    comments: [],
  },

  // Q3 Launch
  {
    id: 243,
    title: 'Finalize pricing and packaging',
    project: 'Q3 Launch',
    status: 'In Progress',
    priority: 'High',
    labels: ['Research'],
    assignees: ['Rhea Kapoor'],
    owner: 'Rhea Kapoor',
    due: '2026-07-06',
    description:
      'Lock the three tiers and what goes in each. Pull the willingness-to-pay numbers from the last survey and get sign-off from sales.',
    comments: [],
  },
  {
    id: 240,
    title: 'Prepare QA checklist for the release candidate',
    project: 'Q3 Launch',
    status: 'In Progress',
    priority: 'High',
    labels: ['Chore'],
    assignees: ['Ana Costa'],
    owner: 'Rhea Kapoor',
    due: '2026-07-05',
    description:
      'Collect the regression scenarios from the last two releases into a single checklist, ordered by risk. Everything above the line must pass before we cut the release candidate.',
    comments: [],
  },
  {
    id: 239,
    title: 'Prepare the press kit',
    project: 'Q3 Launch',
    status: 'Todo',
    priority: 'High',
    labels: ['Docs', 'Design'],
    assignees: ['Ana Costa'],
    owner: 'Rhea Kapoor',
    due: '2026-07-10',
    description:
      'Assemble the fact sheet, founder bios, logo pack, and three product screenshots into a single downloadable kit for press.',
    comments: [],
  },
  {
    id: 234,
    title: 'Set up the launch landing page',
    project: 'Q3 Launch',
    status: 'Todo',
    priority: 'Medium',
    labels: ['Feature', 'Frontend'],
    assignees: ['Priya Nair'],
    owner: 'Rhea Kapoor',
    due: '2026-07-13',
    description:
      'A single page with the announcement, a demo video, and an email capture. Wire the form to the marketing list and add the launch-day banner.',
    comments: [],
  },
  {
    id: 226,
    title: 'Draft the launch announcement email',
    project: 'Q3 Launch',
    status: 'Todo',
    priority: 'Low',
    labels: ['Docs'],
    assignees: ['Rhea Kapoor'],
    owner: 'Rhea Kapoor',
    due: '2026-07-15',
    description:
      'First draft of the announcement for the existing-customer list: what changed, what it costs, and one clear call to action. Marketing reviews it on the 16th.',
    comments: [],
  },
  {
    id: 227,
    title: 'Draft the launch-day runbook',
    project: 'Q3 Launch',
    status: 'Backlog',
    priority: 'Medium',
    labels: ['Docs', 'Chore'],
    assignees: ['Sam Rivera'],
    owner: 'Rhea Kapoor',
    due: '',
    description:
      'Step-by-step timeline for launch day: who flips which switch, in what order, and the rollback plan if something goes sideways.',
    comments: [],
  },
  {
    id: 218,
    title: 'Line up customer testimonials',
    project: 'Q3 Launch',
    status: 'Backlog',
    priority: 'Low',
    labels: ['Research'],
    assignees: ['Ana Costa'],
    owner: 'Ana Costa',
    due: '',
    description:
      'Reach out to five beta customers for a short quote and a logo release. Two confirmed so far.',
    comments: [],
  },
  {
    id: 201,
    title: 'Beta program wrap-up report',
    project: 'Q3 Launch',
    status: 'Done',
    priority: 'High',
    labels: ['Docs'],
    assignees: ['Rhea Kapoor'],
    owner: 'Rhea Kapoor',
    due: '2026-06-25',
    description:
      'What we learned from the eight-week beta: top requests, the bugs we fixed, and the three things we deliberately deferred.',
    comments: [],
  },
])

export const MY_TASKS = 'My tasks'

// Every label used by the fixtures, sorted for the filter and group menus.
export const labels = [...new Set(tasks.flatMap((t) => t.labels))].sort()

export const priorityRank = { High: 0, Medium: 1, Low: 2 }

export function openCount(project) {
  return tasks.filter(
    (t) => t.project === project && !['Done', 'Canceled'].includes(t.status),
  ).length
}

export {
  statuses,
  statusIcon,
  priorities,
  priorityIcon,
  priorityColor,
  labelTheme,
  themeDot,
  labelDotClass,
  me,
  people,
  imageOf,
  projects,
  tasks,
}
