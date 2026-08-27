// Fixture data for the Mail Prototype. There is no server, so the mail lives
// in plain consts. The upstream recipe kept one sidebar `ref`. Here each
// mailbox and each label is a route, so the view key comes from the route.

export type MailAuthor = {
  name: string
  email: string
  image?: string
}

export type MailMessage = {
  author: MailAuthor
  date: string
  body: string[]
}

export type MailThread = {
  id: number
  category: string
  folder: 'inbox' | 'trash'
  starred?: boolean
  sent?: boolean
  labels?: string[]
  subject: string
  time: string
  unread: boolean
  preview: string
  messages: MailMessage[]
}

// Mailboxes and labels: the sidebar navigation. Each one owns a route.
export const mailboxes = [
  { key: 'inbox', label: 'Inbox', icon: 'lucide-inbox', path: '/' },
  { key: 'starred', label: 'Starred', icon: 'lucide-star', path: '/starred' },
  { key: 'sent', label: 'Sent', icon: 'lucide-send', path: '/sent' },
  {
    key: 'drafts',
    label: 'Drafts',
    icon: 'lucide-file-pen-line',
    path: '/drafts',
  },
  { key: 'trash', label: 'Trash', icon: 'lucide-trash-2', path: '/trash' },
]

export const labels = [
  { key: 'label:work', label: 'Work', path: '/labels/work' },
  { key: 'label:personal', label: 'Personal', path: '/labels/personal' },
]

// Gmail-style category tabs above the list. They filter the Inbox only.
export const mailTabs = ['Primary', 'Transactions', 'Updates', 'Promotions']

const evan = 'https://avatars.githubusercontent.com/u/499550?v=4'

// Each thread is one row in the list pane and one conversation in the reading
// pane; `category` routes it to a tab, `folder` to a mailbox.
export const threads: MailThread[] = [
  {
    id: 1,
    category: 'Primary',
    folder: 'inbox',
    starred: true,
    sent: true,
    labels: ['Work'],
    subject: 'Trouble connecting Slack integration',
    time: '6h',
    unread: false,
    preview:
      'Our team is trying to connect Slack with Northwind, but the authorization process fails with an OAuth error.',
    messages: [
      {
        author: {
          name: 'Sarah Tran',
          email: 'sarah.tran@example.com',
          image: 'https://i.pravatar.cc/150?img=1',
        },
        date: 'Aug 29, 8:03 AM',
        body: [
          'Hi Northwind Support,',
          'Our team is trying to connect Slack with Northwind, but the authorization process fails with the following error message: “OAuth token invalid.”',
          'We’ve tried reconnecting a couple of times and even restarted the workspace, but no luck. Could you help us get this integration working?',
          'Thanks,\nSarah Tran\nOps Manager, BrightWave Marketing',
        ],
      },
      {
        author: {
          name: 'Peter Lann',
          email: 'peter.lann@northwind.com',
          image: evan,
        },
        date: 'Aug 29, 12:56 PM',
        body: [
          'Hi Sarah,',
          'Thanks for reaching out — happy to help! That error usually happens when Slack doesn’t grant Northwind the right permissions during the connection step. Here are a few things to try:',
          '1. Make sure you’re logged into the correct Slack workspace before starting the connection.\n2. Remove Northwind from your Slack app directory, then reconnect from Settings → Integrations.\n3. Confirm an admin is approving the OAuth request — restricted workspaces block it otherwise.',
          'Let me know how it goes and I’ll dig deeper if needed.',
          'Regards,\nPeter Lann',
        ],
      },
    ],
  },
  {
    id: 2,
    category: 'Primary',
    folder: 'inbox',
    labels: ['Work'],
    subject: 'Missing files in shared workspace',
    time: '6h',
    unread: true,
    preview:
      'Yesterday I uploaded a set of project files to our shared workspace. Today, two of the files are nowhere to be found.',
    messages: [
      {
        author: {
          name: 'Marcus Feng',
          email: 'marcus@northloop.io',
          image: 'https://i.pravatar.cc/150?img=12',
        },
        date: 'Aug 29, 7:40 AM',
        body: [
          'Hi team,',
          'Yesterday I uploaded a set of project files to our shared workspace. Today, two of the files are nowhere to be found and the folder shows the wrong item count.',
          'Could you check whether they were moved or deleted? These are time-sensitive.',
        ],
      },
    ],
  },
  {
    id: 3,
    category: 'Primary',
    folder: 'inbox',
    subject: 'Can’t reset my password',
    time: '12h',
    unread: true,
    preview:
      'I tried to reset my Northwind password using the “Forgot Password” link, but the reset email never arrives.',
    messages: [
      {
        author: {
          name: 'Leo Nakamura',
          email: 'leo.n@fieldworks.dev',
          image: 'https://i.pravatar.cc/150?img=33',
        },
        date: 'Aug 28, 9:30 PM',
        body: [
          'Hi,',
          'I tried to reset my Northwind password using the “Forgot Password” link, but the reset email never arrives. I’ve checked spam too.',
          'Can you help me regain access?',
        ],
      },
    ],
  },
  {
    id: 4,
    category: 'Primary',
    folder: 'inbox',
    labels: ['Work'],
    subject: 'Dashboard analytics not updating',
    time: '1d',
    unread: false,
    preview:
      'The analytics dashboard stopped updating yesterday around 3 PM. All charts are stuck at the same values.',
    messages: [
      {
        author: {
          name: 'Priya Nair',
          email: 'priya@acme.com',
          image: 'https://i.pravatar.cc/150?img=47',
        },
        date: 'Aug 28, 3:14 PM',
        body: [
          'Hi team,',
          'The analytics dashboard stopped updating yesterday around 3 PM. All charts are stuck at the same values even after a hard refresh.',
          'Is there a known issue?',
        ],
      },
    ],
  },
  {
    id: 5,
    category: 'Primary',
    folder: 'inbox',
    labels: ['Personal'],
    subject: 'Question about adding team seats',
    time: '1d',
    unread: false,
    preview:
      'We’re growing fast and need to add five more seats. Can we do that mid-cycle, and how is it prorated?',
    messages: [
      {
        author: {
          name: 'Nadia Osei',
          email: 'nadia@brightwave.co',
          image: 'https://i.pravatar.cc/150?img=5',
        },
        date: 'Aug 28, 11:02 AM',
        body: [
          'Hello,',
          'We’re growing fast and need to add five more seats this week. Can we do that mid-cycle, and how is the cost prorated?',
          'Thanks,\nNadia',
        ],
      },
    ],
  },
  {
    id: 6,
    category: 'Primary',
    folder: 'inbox',
    labels: ['Personal'],
    subject: 'Feedback on the new editor',
    time: '2d',
    unread: false,
    preview:
      'Just wanted to say the new editor is a huge improvement. One small thing — the slash menu sometimes opens off-screen.',
    messages: [
      {
        author: {
          name: 'Tom Becker',
          email: 'tom@fieldworks.dev',
          image: 'https://i.pravatar.cc/150?img=8',
        },
        date: 'Aug 27, 4:45 PM',
        body: [
          'Hi folks,',
          'Just wanted to say the new editor is a huge improvement — the tables especially. One small thing: the slash menu sometimes opens off-screen near the bottom of the page.',
          'Not urgent, just flagging it. Keep up the great work!',
        ],
      },
    ],
  },
  {
    id: 7,
    category: 'Primary',
    folder: 'inbox',
    subject: 'Follow-up from our onboarding call',
    time: '2d',
    unread: false,
    preview:
      'Thanks for the walkthrough today. Sharing the notes and the two questions the team still had about permissions.',
    messages: [
      {
        author: {
          name: 'Grace Liu',
          email: 'grace@northloop.io',
          image: 'https://i.pravatar.cc/150?img=16',
        },
        date: 'Aug 27, 1:20 PM',
        body: [
          'Hi Priya,',
          'Thanks for the walkthrough today — really helpful. I’m sharing the notes with the team and following up on the two questions we had about role permissions.',
          'Talk soon,\nGrace',
        ],
      },
    ],
  },
  {
    id: 8,
    category: 'Primary',
    folder: 'inbox',
    starred: true,
    labels: ['Work'],
    subject: 'Hitting API rate limits in production',
    time: '3d',
    unread: true,
    preview:
      'Since this morning we’re getting 429s on the documents endpoint. Traffic hasn’t changed — has the limit been lowered?',
    messages: [
      {
        author: {
          name: 'Victor Alvarez',
          email: 'victor@initech.com',
          image: 'https://i.pravatar.cc/150?img=52',
        },
        date: 'Aug 26, 9:05 AM',
        body: [
          'Hi,',
          'Since this morning we’re getting 429 responses on the documents endpoint in production. Our traffic hasn’t changed — has the rate limit been lowered recently?',
          'This is affecting live users, so any quick guidance would help.',
        ],
      },
    ],
  },
  {
    id: 9,
    category: 'Primary',
    folder: 'inbox',
    labels: ['Work'],
    subject: 'Can we enable SSO for our org?',
    time: '4d',
    unread: false,
    preview:
      'Security is asking us to move to SAML SSO. What’s involved on your side, and is it available on our current plan?',
    messages: [
      {
        author: {
          name: 'Elena Fischer',
          email: 'elena@umbrella.co',
          image: 'https://i.pravatar.cc/150?img=20',
        },
        date: 'Aug 25, 2:30 PM',
        body: [
          'Hi team,',
          'Our security team is asking us to move to SAML SSO. What’s involved on your side to set it up, and is it available on our current plan?',
          'Best,\nElena',
        ],
      },
    ],
  },
  {
    id: 10,
    category: 'Transactions',
    folder: 'inbox',
    subject: 'Receipt for your July payment',
    time: '5d',
    unread: false,
    preview:
      'Thanks for your payment of $480.00. Your receipt for the July billing period is attached below.',
    messages: [
      {
        author: { name: 'Northwind Billing', email: 'billing@northwind.com' },
        date: 'Aug 24, 6:00 AM',
        body: [
          'Hi,',
          'Thanks for your payment of $480.00 for the July billing period. This email is your receipt — no action needed.',
          'You can view or download past invoices anytime from Settings → Billing.',
        ],
      },
    ],
  },
  {
    id: 11,
    category: 'Transactions',
    folder: 'inbox',
    subject: 'Invoice #2043 is ready to view',
    time: '6d',
    unread: true,
    preview:
      'Your invoice for the upcoming period is ready. The total is $600.00, due on September 1.',
    messages: [
      {
        author: { name: 'Northwind Billing', email: 'billing@northwind.com' },
        date: 'Aug 23, 6:00 AM',
        body: [
          'Hi,',
          'Invoice #2043 for the upcoming billing period is ready to view. The total is $600.00, due on September 1.',
          'No action is needed if you’re on auto-pay — we’ll charge your card on file.',
        ],
      },
    ],
  },
  {
    id: 12,
    category: 'Transactions',
    folder: 'inbox',
    labels: ['Work'],
    subject: 'Billing discrepancy on latest invoice',
    time: '6d',
    unread: true,
    preview:
      'Our invoice for this month shows 10 Pro licenses, but we only have 8 active users. Can you review the charge?',
    messages: [
      {
        author: {
          name: 'Dana Whitfield',
          email: 'dana@brightwave.co',
          image: 'https://i.pravatar.cc/150?img=25',
        },
        date: 'Aug 23, 5:12 AM',
        body: [
          'Hello,',
          'Our invoice for this month shows 10 Pro licenses, but we only have 8 active users. Can you review the charge and issue a correction if needed?',
          'Thanks,\nDana',
        ],
      },
    ],
  },
  {
    id: 13,
    category: 'Updates',
    folder: 'inbox',
    starred: true,
    subject: 'What’s new: faster search and saved views',
    time: '1w',
    unread: false,
    preview:
      'This month we rebuilt search to be up to 5× faster and added saved views so you can pin the filters you use most.',
    messages: [
      {
        author: { name: 'Northwind', email: 'product@northwind.com' },
        date: 'Aug 22, 8:00 AM',
        body: [
          'Hi there,',
          'This month we rebuilt search to be up to 5× faster, and added saved views so you can pin the filters you use most.',
          'Read the full changelog in your dashboard under What’s New.',
        ],
      },
    ],
  },
  {
    id: 14,
    category: 'Updates',
    folder: 'inbox',
    subject: 'New sign-in from Chrome on macOS',
    time: '1w',
    unread: false,
    preview:
      'We noticed a new sign-in to your Northwind account. If this was you, no action is needed.',
    messages: [
      {
        author: { name: 'Northwind Security', email: 'security@northwind.com' },
        date: 'Aug 21, 10:14 PM',
        body: [
          'Hi,',
          'We noticed a new sign-in to your Northwind account from Chrome on macOS, near San Francisco, CA.',
          'If this was you, no action is needed. If not, reset your password and review active sessions right away.',
        ],
      },
    ],
  },
  {
    id: 15,
    category: 'Updates',
    folder: 'inbox',
    subject: 'Scheduled maintenance this Sunday',
    time: '1w',
    unread: false,
    preview:
      'Northwind will be briefly unavailable on Sunday, 02:00–03:00 UTC while we upgrade our database cluster.',
    messages: [
      {
        author: { name: 'Northwind', email: 'status@northwind.com' },
        date: 'Aug 21, 9:00 AM',
        body: [
          'Hi,',
          'Northwind will be briefly unavailable on Sunday from 02:00 to 03:00 UTC while we upgrade our database cluster.',
          'No action is needed — we’re sharing this so you can plan around the window.',
        ],
      },
    ],
  },
  {
    id: 16,
    category: 'Promotions',
    folder: 'trash',
    subject: 'Upgrade to Pro and save 20% this month',
    time: '1w',
    unread: false,
    preview:
      'Unlock automations, advanced permissions, and priority support. Upgrade before month-end to lock in 20% off.',
    messages: [
      {
        author: { name: 'Northwind', email: 'offers@northwind.com' },
        date: 'Aug 20, 8:30 AM',
        body: [
          'Hi there,',
          'Unlock automations, advanced permissions, and priority support with Northwind Pro. Upgrade before month-end to lock in 20% off your first year.',
          'Questions about the plan? Just reply to this email.',
        ],
      },
    ],
  },
  {
    id: 17,
    category: 'Promotions',
    folder: 'inbox',
    labels: ['Personal'],
    subject: 'You’re invited: automation webinar',
    time: '2w',
    unread: false,
    preview:
      'Join our 30-minute live session on building no-code automations, with time for Q&A at the end.',
    messages: [
      {
        author: { name: 'Northwind Partners', email: 'events@northwind.com' },
        date: 'Aug 15, 12:00 PM',
        body: [
          'Hi,',
          'Join our 30-minute live session on building no-code automations in Northwind, with time for Q&A at the end.',
          'Save your seat from the link in your dashboard — recordings go out to everyone who registers.',
        ],
      },
    ],
  },
]

// The routes hand a view key in. Drafts holds nothing, so it shows the empty
// state.
export function threadsFor(view: string): MailThread[] {
  if (view === 'inbox') return threads.filter((t) => t.folder === 'inbox')
  if (view === 'trash') return threads.filter((t) => t.folder === 'trash')
  if (view === 'starred') return threads.filter((t) => t.starred)
  if (view === 'sent') return threads.filter((t) => t.sent)
  if (view === 'drafts') return []
  const label = view.replace('label:', '')
  return threads.filter((t) =>
    (t.labels ?? []).some((l) => l.toLowerCase() === label),
  )
}

export function unreadCount(view: string): number {
  return threadsFor(view).filter((t) => t.unread).length
}

export function viewLabel(view: string): string {
  const box = mailboxes.find((m) => m.key === view)
  if (box) return box.label
  return labels.find((l) => l.key === view)?.label ?? 'Mail'
}

// Overflow actions for the reading toolbar: mail verbs, not ticket verbs.
export const moreActions = [
  { label: 'Star', icon: 'lucide-star' },
  { label: 'Mark as important', icon: 'lucide-bookmark' },
  { label: 'Move to…', icon: 'lucide-folder-input' },
  { label: 'Mute', icon: 'lucide-bell-off' },
  { label: 'Print', icon: 'lucide-printer' },
  { label: 'Report spam', icon: 'lucide-shield-alert' },
  { label: 'Block sender', icon: 'lucide-user-x' },
]
