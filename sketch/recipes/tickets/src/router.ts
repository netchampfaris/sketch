// The Runtime creates the router in hash mode. A Prototype exports routes only.
import Tickets from './pages/Tickets.vue'
import Customers from './pages/Customers.vue'
import Contacts from './pages/Contacts.vue'
import Agents from './pages/Agents.vue'
import KnowledgeBase from './pages/KnowledgeBase.vue'
import CannedResponses from './pages/CannedResponses.vue'

// Tickets serves the main list and the four saved views. Every path is
// parameterless, so each one is a screen on its own.
export default [
  { path: '/', name: 'Tickets', component: Tickets },
  { path: '/my-open-tickets', name: 'MyOpenTickets', component: Tickets },
  { path: '/urgent', name: 'Urgent', component: Tickets },
  { path: '/unassigned', name: 'Unassigned', component: Tickets },
  { path: '/solved-this-week', name: 'SolvedThisWeek', component: Tickets },
  { path: '/customers', name: 'Customers', component: Customers },
  { path: '/contacts', name: 'Contacts', component: Contacts },
  { path: '/agents', name: 'Agents', component: Agents },
  { path: '/knowledge-base', name: 'KnowledgeBase', component: KnowledgeBase },
  {
    path: '/canned-responses',
    name: 'CannedResponses',
    component: CannedResponses,
  },
]
