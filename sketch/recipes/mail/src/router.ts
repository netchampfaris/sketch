// The Runtime creates the router in hash mode. A Prototype exports routes only.
import Mailbox from './pages/Mailbox.vue'

// Upstream held the mailbox in one `ref`. Here every mailbox and every label is
// a static route, so `check` can walk them all. The view key arrives as a prop.
export default [
  { path: '/', name: 'Inbox', component: Mailbox, props: { view: 'inbox' } },
  {
    path: '/starred',
    name: 'Starred',
    component: Mailbox,
    props: { view: 'starred' },
  },
  { path: '/sent', name: 'Sent', component: Mailbox, props: { view: 'sent' } },
  {
    path: '/drafts',
    name: 'Drafts',
    component: Mailbox,
    props: { view: 'drafts' },
  },
  {
    path: '/trash',
    name: 'Trash',
    component: Mailbox,
    props: { view: 'trash' },
  },
  {
    path: '/labels/work',
    name: 'Work',
    component: Mailbox,
    props: { view: 'label:work' },
  },
  {
    path: '/labels/personal',
    name: 'Personal',
    component: Mailbox,
    props: { view: 'label:personal' },
  },
]
