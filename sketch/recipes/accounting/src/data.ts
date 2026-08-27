// Fixture data for the Accounting prototype. There is no server, so every
// figure is a plain const.

// Grouped navigation. Four items render a real screen. The rest are shell
// dressing and fall through to a shared empty state, so the sidebar reads like
// a full accounting product without faking every module. `to` is the route.
const navGroups = [
  {
    label: 'Overview',
    items: [
      {
        key: 'cashflow', to: '/',
        label: 'Cashflow',
        icon: 'lucide-activity',
        page: true,
      },
    ],
  },
  {
    label: 'Sales',
    items: [
      { key: 'invoices', to: '/invoices', label: 'Invoices', icon: 'lucide-file-text' },
      { key: 'payments', to: '/payments', label: 'Payments', icon: 'lucide-credit-card' },
      { key: 'orders', to: '/orders', label: 'Orders', icon: 'lucide-shopping-cart' },
      { key: 'customers', to: '/customers', label: 'Customers', icon: 'lucide-users-round' },
    ],
  },
  {
    label: 'Purchases',
    items: [
      { key: 'bills', to: '/bills', label: 'Bills', icon: 'lucide-receipt-text' },
      {
        key: 'expenses', to: '/expenses',
        label: 'Expenses',
        icon: 'lucide-receipt',
        page: true,
      },
      { key: 'suppliers', to: '/suppliers', label: 'Suppliers', icon: 'lucide-truck' },
    ],
  },
  {
    label: 'Accounting',
    items: [
      { key: 'payroll', to: '/payroll', label: 'Payroll', icon: 'lucide-users', page: true },
      { key: 'journal', to: '/journal', label: 'Journal', icon: 'lucide-book-open' },
      { key: 'taxes', to: '/taxes', label: 'Taxes', icon: 'lucide-percent' },
    ],
  },
  {
    label: 'Reports',
    items: [
      {
        key: 'reports', to: '/reports',
        label: 'Profit & Loss',
        icon: 'lucide-chart-no-axes-column',
        page: true,
      },
      { key: 'balance', to: '/balance-sheet', label: 'Balance Sheet', icon: 'lucide-scale' },
    ],
  },
]
export const navItems = navGroups.flatMap((group) => group.items)

// Every nav item gets a parameterless route. The four real screens have their
// own page; the rest share the stub page.
export function metaFor(key) {
  return navItems.find((item) => item.key === key) ?? navItems[0]
}

const currency = (n) =>
  `${n < 0 ? '-' : ''}$${Math.abs(n).toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`

/* -- Cashflow (dashboard) ------------------------------------------------- */

// `delta` is the month-over-month change in %. Its sign drives the arrow
// direction. Kept neutral gray, because "up" is not always good here: more
// outgoings is worse, so colour would mislead.
const cashflowStats = [
  { label: 'Todays balance', value: 14081.09, delta: 4.2 },
  { label: 'Incoming in 30 days', value: 2011.44, delta: 12.5 },
  { label: 'Outgoing in 30 days', value: 12011.44, delta: 3.1 },
  { label: 'Projected balance', value: -1518.0, delta: -8.4 },
]

// Linked bank/card accounts shown in the dashboard's right rail.
const accounts = [
  { name: 'Business checking', number: '•••• 4021', balance: 18240.55 },
  { name: 'Savings', number: '•••• 8873', balance: 42500.0 },
  { name: 'Credit card', number: '•••• 1180', balance: -3241.09 },
]
const accountsTotal = accounts.reduce((sum, a) => sum + a.balance, 0)

// This month's spend by category, pre-sorted; `pct` drives the bar width.
const expenseBreakdown = [
  { category: 'Salaries', amount: 20100, pct: 62 },
  { category: 'Rent & utilities', amount: 3400, pct: 11 },
  { category: 'Marketing', amount: 3400, pct: 11 },
  { category: 'Software', amount: 1550, pct: 5 },
  { category: 'Everything else', amount: 3400, pct: 11 },
]

const transactions = {
  incomings: [
    { date: 'August 18', description: 'Invoice #1043 — Acme Co', amount: 4200 },
    { date: 'August 11', description: 'Invoice #1042 — Globex', amount: 1810 },
    { date: 'August 3', description: 'Refund — SaaS annual', amount: 240 },
  ],
  outgoings: [
    { date: 'August 20', description: 'Lunch', amount: 104.99 },
    { date: 'August 12', description: 'Train ticket', amount: 5.23 },
    { date: 'August 8', description: 'Lunch with client', amount: 166.23 },
    { date: 'August 4', description: 'Printer', amount: 200.0 },
    { date: 'July 29', description: 'Coffee with client', amount: 6.0 },
  ],
}


const expenses = [
  { date: 'August 20', description: 'Lunch', amount: 104.99 },
  { date: 'August 12', description: 'Train ticket', amount: 5.23 },
  { date: 'August 8', description: 'Lunch with client', amount: 166.23 },
  { date: 'August 4', description: 'Printer', amount: 200.0 },
  { date: 'July 29', description: 'Coffee with client', amount: 6.0 },
  { date: 'July 22', description: 'Travel', amount: 105.63 },
  { date: 'July 21', description: 'Hotel stay', amount: 350.0 },
  { date: 'July 12', description: 'Printer ink', amount: 15.0 },
  { date: 'July 10', description: 'Conference tickets', amount: 699.99 },
  { date: 'July 2', description: 'Train ticket', amount: 5.23 },
  { date: 'June 25', description: 'Bus travel', amount: 10.02 },
  { date: 'July 13', description: 'Accountant software', amount: 175.0 },
]

/* -- Payroll -------------------------------------------------------------- */

const payroll = [
  { id: 1, name: 'Stacey Bobb', total: 1900, tax: 300, ni: 314, net: 18540 },
  { id: 2, name: 'Derek Forbes', total: 1205, tax: 300, ni: 314, net: 19500 },
  { id: 3, name: 'Garth Leemow', total: 1900, tax: 200, ni: 314, net: 18540 },
  { id: 4, name: 'Ilyssa Bodah', total: 1200, tax: 400, ni: 314, net: 12000 },
  { id: 5, name: 'Bernard Timm', total: 3900, tax: 500, ni: 314, net: 28560 },
  { id: 6, name: 'Rabbi Ferouz', total: 1205, tax: 300, ni: 314, net: 12110 },
  { id: 7, name: 'Sam Ruprecht', total: 1900, tax: 150, ni: 314, net: 13880 },
  { id: 8, name: 'Daren Crabb', total: 5205, tax: 180, ni: 314, net: 110540 },
]

// One financial year of monthly data, Apr 2024 to Mar 2025. Each month carries
// its first-of-month `date` so the DateRangePicker's window can be mapped back
// onto column indices. The report never renders all of it at once: the filter
// picks a window and the period toggle buckets it (see `buckets` below).
const months = [
  { label: 'Apr', year: 2024, date: '2024-04-01' },
  { label: 'May', year: 2024, date: '2024-05-01' },
  { label: 'Jun', year: 2024, date: '2024-06-01' },
  { label: 'Jul', year: 2024, date: '2024-07-01' },
  { label: 'Aug', year: 2024, date: '2024-08-01' },
  { label: 'Sep', year: 2024, date: '2024-09-01' },
  { label: 'Oct', year: 2024, date: '2024-10-01' },
  { label: 'Nov', year: 2024, date: '2024-11-01' },
  { label: 'Dec', year: 2024, date: '2024-12-01' },
  { label: 'Jan', year: 2025, date: '2025-01-01' },
  { label: 'Feb', year: 2025, date: '2025-02-01' },
  { label: 'Mar', year: 2025, date: '2025-03-01' },
]

// `section` rows are group headings; the rest are line items with one value per
// month, indexed to `months`. Enough lines that the report overflows the
// viewport and scrolls vertically as well as horizontally.
const pnlRows = [
  { type: 'section', label: 'Income' },
  {
    label: 'Turnover',
    values: [
      12500, 13200, 11800, 14100, 15300, 12900, 13800, 14600, 16200, 15100,
      14200, 17300,
    ],
  },
  {
    label: 'Product sales',
    values: [
      8200, 7600, 9100, 8800, 10200, 9400, 8900, 9700, 11300, 10600, 9800,
      12100,
    ],
  },
  {
    label: 'Service revenue',
    values: [
      4300, 4700, 4100, 5200, 4900, 5400, 5100, 5600, 6200, 5800, 5300, 6700,
    ],
  },
  {
    label: 'Consulting',
    values: [
      3100, 2800, 3400, 3600, 3900, 3300, 3700, 4000, 4300, 3800, 3500, 4600,
    ],
  },
  {
    label: 'Other income',
    values: [320, 410, 280, 390, 450, 300, 370, 420, 510, 470, 360, 540],
  },
  { type: 'section', label: 'Cost of sales' },
  {
    label: 'Materials',
    values: [
      4200, 3900, 4600, 4400, 5100, 4700, 4500, 4900, 5600, 5300, 4900, 6100,
    ],
  },
  {
    label: 'Shipping & freight',
    values: [820, 760, 910, 880, 1020, 940, 890, 970, 1130, 1060, 980, 1210],
  },
  {
    label: 'Merchant fees',
    values: [410, 430, 390, 470, 500, 440, 460, 490, 560, 520, 470, 610],
  },
  { type: 'section', label: 'Expenses' },
  {
    label: 'Accountancy fees',
    values: [750, 750, 750, 1450, 750, 750, 750, 1050, 750, 750, 750, 1250],
  },
  {
    label: 'Software subscriptions',
    values: [
      1200, 1250, 1250, 1300, 1400, 1450, 1250, 1550, 1250, 1350, 1250, 1550,
    ],
  },
  {
    label: 'Office equipment',
    values: [2400, 840, 1050, 3050, 450, 800, 1050, 575, 1200, 650, 900, 575],
  },
  {
    label: 'Rent & utilities',
    values: [
      3200, 3200, 3200, 3200, 3350, 3200, 3200, 3200, 3400, 3200, 3200, 3400,
    ],
  },
  {
    label: 'Salaries',
    values: [
      18500, 18500, 18500, 18500, 19200, 19200, 19200, 19200, 19200, 20100,
      20100, 20100,
    ],
  },
  {
    label: 'Marketing',
    values: [
      1500, 2200, 900, 1800, 2600, 1200, 3100, 1400, 2700, 1900, 1600, 3400,
    ],
  },
  {
    label: 'Travel',
    values: [640, 980, 420, 1250, 760, 540, 1120, 890, 1340, 720, 610, 1480],
  },
  {
    label: 'Insurance',
    values: [520, 520, 520, 520, 540, 540, 540, 540, 560, 560, 560, 560],
  },
  {
    label: 'Telecoms',
    values: [180, 185, 182, 190, 195, 188, 192, 198, 205, 200, 196, 210],
  },
  {
    label: 'Bank charges',
    values: [90, 95, 88, 110, 105, 92, 98, 102, 120, 108, 96, 130],
  },
  {
    label: 'Stationery',
    values: [180, 220, 150, 310, 240, 190, 270, 160, 330, 210, 175, 290],
  },
  {
    label: 'Meals & entertainment',
    values: [420, 560, 380, 610, 720, 390, 540, 480, 690, 450, 510, 620],
  },
]

export {
  navGroups,
  currency,
  cashflowStats,
  accounts,
  accountsTotal,
  expenseBreakdown,
  transactions,
  expenses,
  payroll,
  months,
  pnlRows,
}
