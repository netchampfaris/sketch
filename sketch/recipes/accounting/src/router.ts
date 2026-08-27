// The Runtime creates the router. A Prototype exports routes only.
import Cashflow from './pages/Cashflow.vue'
import Expenses from './pages/Expenses.vue'
import Payroll from './pages/Payroll.vue'
import ProfitAndLoss from './pages/ProfitAndLoss.vue'
import Section from './pages/Section.vue'

// Four real screens. Every other nav item gets its own parameterless path and
// shares the stub page, which passes the key as a static prop.
const stub = (path: string, itemKey: string) => ({
  path,
  component: Section,
  props: { itemKey },
})

export default [
  { path: '/', name: 'Cashflow', component: Cashflow },
  { path: '/expenses', name: 'Expenses', component: Expenses },
  { path: '/payroll', name: 'Payroll', component: Payroll },
  { path: '/reports', name: 'Profit and Loss', component: ProfitAndLoss },
  stub('/invoices', 'invoices'),
  stub('/payments', 'payments'),
  stub('/orders', 'orders'),
  stub('/customers', 'customers'),
  stub('/bills', 'bills'),
  stub('/suppliers', 'suppliers'),
  stub('/journal', 'journal'),
  stub('/taxes', 'taxes'),
  stub('/balance-sheet', 'balance'),
]
