import { ref } from 'vue'

export type Status = 'open' | 'in-progress' | 'done'

export interface Issue {
  name: string
  title: string
  status: Status
  owner: string
  updated: string
}

export const issues = ref<Issue[]>([
  { name: 'ISS-001', title: 'Sidebar collapses on first paint', status: 'open', owner: 'Faris', updated: '2 hours ago' },
  { name: 'ISS-002', title: 'Dialog traps focus behind the header', status: 'in-progress', owner: 'Rhea', updated: 'Yesterday' },
  { name: 'ISS-003', title: 'List rows jump when the badge wraps', status: 'done', owner: 'Kabir', updated: '3 days ago' },
  { name: 'ISS-004', title: 'Empty state has no call to action', status: 'open', owner: 'Faris', updated: 'Last week' },
])

export function findIssue(name: string): Issue | undefined {
  return issues.value.find((i) => i.name === name)
}

export function addIssue(title: string, status: Status, owner: string): void {
  const next = issues.value.length + 1
  issues.value.unshift({
    name: `ISS-${String(next).padStart(3, '0')}`,
    title,
    status,
    owner,
    updated: 'Just now',
  })
}
