// Shared list state for the Tasks screens. The sidebar, the filter bar and the
// list page all read and write this one object, so the two routes agree.
import { computed, reactive } from 'vue'
import {
  MY_TASKS,
  labels,
  me,
  people,
  priorities,
  priorityRank,
  projects,
  statuses,
  tasks,
} from '../data'

// `active` is a project name or MY_TASKS. The rest are optional attribute
// filters that stack on top. An empty string means "no filter".
export const view = reactive({
  active: 'Website Redesign',
  tab: 'All',
  status: '',
  priority: '',
  assignee: '',
  label: '',
  sortBy: 'priority',
  groupBy: 'status',
})

export function openView(name: string) {
  view.active = name
}

export const activeFilterCount = computed(
  () =>
    ['status', 'priority', 'assignee', 'label'].filter((key) => view[key])
      .length,
)

export function clearFilters() {
  view.status = ''
  view.priority = ''
  view.assignee = ''
  view.label = ''
}

// The first option doubles as the reset: its value is '' and its label reads
// like the field name, so the trigger shows "Priority" until you pick a value.
export const statusFilterOptions = [
  { label: 'Status', value: '' },
  ...statuses.map((s: string) => ({ label: s, value: s })),
]
export const priorityFilterOptions = [
  { label: 'Priority', value: '' },
  ...priorities.map((p: string) => ({ label: p, value: p })),
]
export const assigneeFilterOptions = [
  { label: 'Assignee', value: '' },
  ...people.map((p: any) => ({ label: p.name, value: p.name })),
]
export const labelFilterOptions = [
  { label: 'Label', value: '' },
  ...labels.map((l: string) => ({ label: l, value: l })),
]

export const sortLabels = {
  priority: 'Priority',
  due: 'Due date',
  title: 'Title',
}
export const sortLabel = computed(() => sortLabels[view.sortBy])
export const sortDropdownOptions = Object.entries(sortLabels).map(
  ([value, label]) => ({ label, onClick: () => (view.sortBy = value) }),
)

export const groupByLabels = {
  status: 'Status',
  priority: 'Priority',
  assignee: 'Assignee',
  project: 'Project',
  label: 'Label',
}
export const groupByLabel = computed(() => groupByLabels[view.groupBy])
export const groupByDropdownOptions = Object.entries(groupByLabels).map(
  ([value, label]) => ({ label, onClick: () => (view.groupBy = value) }),
)

export const visibleTasks = computed(() => {
  let scoped =
    view.active === MY_TASKS
      ? tasks.filter((t: any) => t.assignees.includes(me) || t.owner === me)
      : tasks.filter((t: any) => t.project === view.active)
  if (view.tab === 'Assigned to me') {
    scoped = scoped.filter((t: any) => t.assignees.includes(me))
  } else if (view.tab === 'Created by me') {
    scoped = scoped.filter((t: any) => t.owner === me)
  }
  if (view.status) scoped = scoped.filter((t: any) => t.status === view.status)
  if (view.priority)
    scoped = scoped.filter((t: any) => t.priority === view.priority)
  if (view.assignee)
    scoped = scoped.filter((t: any) => t.assignees.includes(view.assignee))
  if (view.label)
    scoped = scoped.filter((t: any) => t.labels.includes(view.label))
  return scoped
})

function sortTasks(list: any[]) {
  const arr = [...list]
  if (view.sortBy === 'priority') {
    arr.sort(
      (a, b) => priorityRank[a.priority] - priorityRank[b.priority],
    )
  } else if (view.sortBy === 'due') {
    // Undated tasks sort last.
    arr.sort((a, b) => (a.due || '9999').localeCompare(b.due || '9999'))
  } else if (view.sortBy === 'title') {
    arr.sort((a, b) => a.title.localeCompare(b.title))
  }
  return arr
}

// Each field defines its own section order and how a task maps to a section
// key. A task lands in one section, its first assignee or first label, so the
// counts stay honest.
function groupOrder(field: string) {
  if (field === 'priority') return priorities
  if (field === 'project') return projects.map((p: any) => p.name)
  if (field === 'assignee')
    return [...people.map((p: any) => p.name), 'No assignee']
  if (field === 'label') return [...labels, 'No label']
  return ['In Progress', 'Todo', 'Backlog', 'Done', 'Canceled']
}

function groupKeyOf(task: any, field: string) {
  if (field === 'priority') return task.priority
  if (field === 'project') return task.project
  if (field === 'assignee') return task.assignees[0] || 'No assignee'
  if (field === 'label') return task.labels[0] || 'No label'
  return task.status
}

// Sections are open by default. Only finished status columns start collapsed.
// `openState` records explicit user toggles and overrides that default.
const openState = reactive({})

function defaultOpen(key: string) {
  return !(view.groupBy === 'status' && ['Done', 'Canceled'].includes(key))
}

export function groupOpen(key: string) {
  return key in openState ? openState[key] : defaultOpen(key)
}

export function toggleGroup(key: string) {
  openState[key] = !groupOpen(key)
}

export const groupedTasks = computed(() => {
  const field = view.groupBy
  return groupOrder(field)
    .map((key: string) => ({
      key,
      tasks: sortTasks(
        visibleTasks.value.filter((t: any) => groupKeyOf(t, field) === key),
      ),
    }))
    .filter((group: any) => group.tasks.length)
})
