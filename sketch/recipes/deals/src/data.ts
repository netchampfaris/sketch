// Fixture data for the Deals prototype. There is no server, so the board and
// the list read the same `ref`. The board reorders it by drag, and the list
// shows the new order at once.
import { ref } from 'vue'

export type Deal = {
  org: string
  value: string
  owner: string
  due: string
  tag: string
}

export type Column = {
  status: string
  theme: string
  deals: Deal[]
}

export const owners: Record<
  string,
  { name: string; title: string; image: string; deals: number }
> = {
  evan: {
    name: 'Evan You',
    title: 'Account Executive',
    image: 'https://avatars.githubusercontent.com/u/499550?v=4',
    deals: 8,
  },
  priya: {
    name: 'Priya Nair',
    title: 'Sales Manager',
    image: 'https://i.pravatar.cc/150?img=5',
    deals: 12,
  },
  sam: {
    name: 'Sam Rivera',
    title: 'Account Executive',
    image: 'https://i.pravatar.cc/150?img=12',
    deals: 5,
  },
  ana: {
    name: 'Ana Costa',
    title: 'SDR',
    image: 'https://i.pravatar.cc/150?img=9',
    deals: 9,
  },
}

export const logo = (org: string) =>
  `https://api.dicebear.com/9.x/shapes/svg?seed=${encodeURIComponent(org)}`

// Status dot colours for the board column headings.
export const statusDot: Record<string, string> = {
  gray: 'bg-surface-gray-7',
  amber: 'bg-surface-amber-7',
  blue: 'bg-surface-blue-7',
  green: 'bg-surface-green-7',
}

// Badge theme per pipeline stage, for the list view.
export const statusBadgeTheme: Record<string, string> = {
  gray: 'gray',
  amber: 'orange',
  blue: 'blue',
  green: 'green',
}

export const nav = [
  { label: 'Notifications', icon: 'lucide-inbox', count: 4 },
  { label: 'Leads', icon: 'lucide-users' },
  { label: 'Deals', icon: 'lucide-handshake' },
  { label: 'Contacts', icon: 'lucide-contact' },
  { label: 'Organizations', icon: 'lucide-building-2' },
  { label: 'Notes', icon: 'lucide-notebook-pen' },
  { label: 'Tasks', icon: 'lucide-list-todo' },
]

export const columns = ref<Column[]>([
  {
    status: 'Qualification',
    theme: 'gray',
    deals: [
      {
        org: 'Globex',
        value: '$ 45,000',
        owner: 'priya',
        due: 'Jul 18',
        tag: 'Inbound',
      },
      {
        org: 'Stark Industries',
        value: '$ 1,10,000',
        owner: 'ana',
        due: 'Jul 22',
        tag: 'Referral',
      },
      {
        org: 'Wayne Corp',
        value: '$ 32,000',
        owner: 'sam',
        due: 'Aug 2',
        tag: 'Outbound',
      },
      {
        org: 'Cyberdyne',
        value: '$ 76,000',
        owner: 'evan',
        due: 'Aug 9',
        tag: 'Outbound',
      },
      {
        org: 'Vandelay',
        value: '$ 28,500',
        owner: 'priya',
        due: 'Aug 14',
        tag: 'Inbound',
      },
    ],
  },
  {
    status: 'Negotiation',
    theme: 'amber',
    deals: [
      {
        org: 'Acme Corp',
        value: '$ 1,20,000',
        owner: 'evan',
        due: 'Jul 12',
        tag: 'Inbound',
      },
      {
        org: 'Umbrella Labs',
        value: '$ 88,000',
        owner: 'ana',
        due: 'Jul 15',
        tag: 'Partner',
      },
      {
        org: 'Wonka Industries',
        value: '$ 54,000',
        owner: 'sam',
        due: 'Jul 21',
        tag: 'Outbound',
      },
      {
        org: 'Duff Co',
        value: '$ 39,000',
        owner: 'priya',
        due: 'Jul 25',
        tag: 'Referral',
      },
    ],
  },
  {
    status: 'Ready to Close',
    theme: 'blue',
    deals: [
      {
        org: 'Hooli',
        value: '$ 2,05,000',
        owner: 'evan',
        due: 'Jul 9',
        tag: 'Expansion',
      },
      {
        org: 'Pied Piper',
        value: '$ 64,000',
        owner: 'priya',
        due: 'Jul 11',
        tag: 'Inbound',
      },
      {
        org: 'Massive Dynamic',
        value: '$ 1,75,000',
        owner: 'ana',
        due: 'Jul 14',
        tag: 'Partner',
      },
    ],
  },
  {
    status: 'Won',
    theme: 'green',
    deals: [
      {
        org: 'Initech',
        value: '$ 2,40,000',
        owner: 'sam',
        due: 'Closed Jul 1',
        tag: 'Renewal',
      },
      {
        org: 'Soylent Corp',
        value: '$ 96,000',
        owner: 'evan',
        due: 'Closed Jun 28',
        tag: 'Expansion',
      },
      {
        org: 'Tyrell Corp',
        value: '$ 1,32,000',
        owner: 'priya',
        due: 'Closed Jun 20',
        tag: 'Referral',
      },
    ],
  },
])

// The detail route looks a deal up by organisation name, which is unique here.
// It returns the pipeline stage with it, because the stage lives on the column.
export function findDeal(org: string) {
  for (const column of columns.value) {
    const deal = column.deals.find((item) => item.org === org)
    if (deal) return { deal, status: column.status, theme: column.theme }
  }
  return null
}

// A short shared timeline. Every deal shows the same shape of history.
export const activity = [
  {
    icon: 'lucide-phone',
    title: 'Discovery call',
    detail: 'Walked through the current stack and the two blockers.',
    when: 'Jun 24',
  },
  {
    icon: 'lucide-file-text',
    title: 'Proposal sent',
    detail: 'Three-year term with the growth tier and onboarding.',
    when: 'Jun 30',
  },
  {
    icon: 'lucide-mail',
    title: 'Security review answered',
    detail: 'Sent the SOC 2 report and the data residency note.',
    when: 'Jul 4',
  },
  {
    icon: 'lucide-calendar-check',
    title: 'Pricing call booked',
    detail: 'Legal and finance both join this one.',
    when: 'Jul 8',
  },
]
