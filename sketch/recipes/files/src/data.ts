// Fixture data for the Files Prototype. There is no server, so the tree lives
// in plain consts.

export type FileItem = {
  id: string
  parent: string | null
  type: 'folder' | 'file'
  name: string
  icon: string
  owner: string
  ownerImage: string
  daysAgo: number
  size?: number
  sizeLabel?: string
  favourite?: boolean
  trashed?: boolean
}

// The signed-in user. "Shared with me" holds everything another person owns.
export const currentUser = 'Rhea Kapoor'

// The sidebar navigation. Each entry owns a parameterless route.
export const navItems = [
  { key: 'home', label: 'Home', icon: 'lucide-house', path: '/' },
  { key: 'recents', label: 'Recents', icon: 'lucide-clock', path: '/recents' },
  {
    key: 'favourites',
    label: 'Favourites',
    icon: 'lucide-star',
    path: '/favourites',
  },
  {
    key: 'shared',
    label: 'Shared with me',
    icon: 'lucide-users',
    path: '/shared',
  },
  { key: 'trash', label: 'Trash', icon: 'lucide-trash-2', path: '/trash' },
]

// A flat tree: `parent` is the id of the containing folder (null at the root).
// Folders and files share one collection so they interleave in the time
// buckets. `daysAgo` is the single source of truth for age: both the relative
// label and the bucket a row lands in derive from it. Folders carry no byte
// `size`; their Size column shows a derived child count instead.
export const allItems: FileItem[] = [
  // Root
  {
    id: 'design',
    parent: null,
    type: 'folder',
    name: 'Design assets',
    icon: 'lucide-folder',
    owner: 'Rhea Kapoor',
    ownerImage: 'https://i.pravatar.cc/150?img=5',
    daysAgo: 0,
  },
  {
    id: 'contracts',
    parent: null,
    type: 'folder',
    name: 'Contracts',
    icon: 'lucide-folder',
    owner: 'Priya Nair',
    ownerImage: 'https://i.pravatar.cc/150?img=12',
    daysAgo: 3,
  },
  {
    id: 'screenshots',
    parent: null,
    type: 'folder',
    name: 'Product screenshots',
    icon: 'lucide-folder',
    owner: 'Sam Rivera',
    ownerImage: 'https://i.pravatar.cc/150?img=33',
    daysAgo: 8,
  },
  {
    id: 'offsite',
    parent: null,
    type: 'folder',
    name: 'Team offsite 2026',
    icon: 'lucide-folder',
    owner: 'Ana Costa',
    ownerImage: 'https://i.pravatar.cc/150?img=47',
    daysAgo: 21,
  },
  {
    id: 'q2-deck',
    parent: null,
    type: 'file',
    name: 'Q2 board deck.pdf',
    icon: 'lucide-file-text',
    owner: 'Rhea Kapoor',
    ownerImage: 'https://i.pravatar.cc/150?img=5',
    daysAgo: 0,
    size: 8.4,
    sizeLabel: '8.4 MB',
    favourite: true,
  },
  {
    id: 'standup',
    parent: null,
    type: 'file',
    name: 'Standup notes.md',
    icon: 'lucide-file-text',
    owner: 'Evan You',
    ownerImage: 'https://avatars.githubusercontent.com/u/499550?v=4',
    daysAgo: 0,
    size: 0.02,
    sizeLabel: '18 KB',
  },
  {
    id: 'hero',
    parent: null,
    type: 'file',
    name: 'Homepage hero.png',
    icon: 'lucide-image',
    owner: 'Evan You',
    ownerImage: 'https://avatars.githubusercontent.com/u/499550?v=4',
    daysAgo: 1,
    size: 2.1,
    sizeLabel: '2.1 MB',
    favourite: true,
  },
  {
    id: 'revenue',
    parent: null,
    type: 'file',
    name: 'Revenue model.xlsx',
    icon: 'lucide-file-spreadsheet',
    owner: 'Priya Nair',
    ownerImage: 'https://i.pravatar.cc/150?img=12',
    daysAgo: 2,
    size: 0.6,
    sizeLabel: '640 KB',
  },
  {
    id: 'sprint',
    parent: null,
    type: 'file',
    name: 'Sprint plan.docx',
    icon: 'lucide-file-text',
    owner: 'Amy Santiago',
    ownerImage: 'https://i.pravatar.cc/150?img=45',
    daysAgo: 4,
    size: 0.3,
    sizeLabel: '312 KB',
  },
  {
    id: 'teaser',
    parent: null,
    type: 'file',
    name: 'Launch teaser.mp4',
    icon: 'lucide-video',
    owner: 'Sam Rivera',
    ownerImage: 'https://i.pravatar.cc/150?img=33',
    daysAgo: 5,
    size: 148,
    sizeLabel: '148 MB',
    favourite: true,
  },
  {
    id: 'old-logo',
    parent: null,
    type: 'file',
    name: 'Old logo.ai',
    icon: 'lucide-file-image',
    owner: 'Ana Costa',
    ownerImage: 'https://i.pravatar.cc/150?img=47',
    daysAgo: 9,
    size: 5.6,
    sizeLabel: '5.6 MB',
    trashed: true,
  },
  {
    id: 'brand-fonts',
    parent: null,
    type: 'file',
    name: 'Brand fonts.zip',
    icon: 'lucide-file-archive',
    owner: 'Ana Costa',
    ownerImage: 'https://i.pravatar.cc/150?img=47',
    daysAgo: 12,
    size: 24,
    sizeLabel: '24 MB',
  },
  {
    id: 'archive',
    parent: null,
    type: 'file',
    name: 'Archive 2025.zip',
    icon: 'lucide-file-archive',
    owner: 'Rhea Kapoor',
    ownerImage: 'https://i.pravatar.cc/150?img=5',
    daysAgo: 40,
    size: 512,
    sizeLabel: '512 MB',
    trashed: true,
  },

  // Inside "Design assets": includes a sub-folder for multi-level nav
  {
    id: 'exports',
    parent: 'design',
    type: 'folder',
    name: 'Exports',
    icon: 'lucide-folder',
    owner: 'Rhea Kapoor',
    ownerImage: 'https://i.pravatar.cc/150?img=5',
    daysAgo: 1,
  },
  {
    id: 'logo-master',
    parent: 'design',
    type: 'file',
    name: 'Logo master.svg',
    icon: 'lucide-file-image',
    owner: 'Rhea Kapoor',
    ownerImage: 'https://i.pravatar.cc/150?img=5',
    daysAgo: 0,
    size: 0.4,
    sizeLabel: '420 KB',
    favourite: true,
  },
  {
    id: 'palette',
    parent: 'design',
    type: 'file',
    name: 'Color palette.png',
    icon: 'lucide-image',
    owner: 'Sam Rivera',
    ownerImage: 'https://i.pravatar.cc/150?img=33',
    daysAgo: 2,
    size: 1.2,
    sizeLabel: '1.2 MB',
  },
  {
    id: 'type-scale',
    parent: 'design',
    type: 'file',
    name: 'Type scale.pdf',
    icon: 'lucide-file-text',
    owner: 'Rhea Kapoor',
    ownerImage: 'https://i.pravatar.cc/150?img=5',
    daysAgo: 6,
    size: 3.1,
    sizeLabel: '3.1 MB',
  },

  // Inside "Design assets / Exports"
  {
    id: 'logo-2x',
    parent: 'exports',
    type: 'file',
    name: 'logo@2x.png',
    icon: 'lucide-image',
    owner: 'Rhea Kapoor',
    ownerImage: 'https://i.pravatar.cc/150?img=5',
    daysAgo: 1,
    size: 0.8,
    sizeLabel: '800 KB',
  },
  {
    id: 'brand-sheet',
    parent: 'exports',
    type: 'file',
    name: 'brand-sheet.pdf',
    icon: 'lucide-file-text',
    owner: 'Sam Rivera',
    ownerImage: 'https://i.pravatar.cc/150?img=33',
    daysAgo: 1,
    size: 2.4,
    sizeLabel: '2.4 MB',
  },

  // Inside "Contracts"
  {
    id: 'msa',
    parent: 'contracts',
    type: 'file',
    name: 'MSA 2026.pdf',
    icon: 'lucide-file-text',
    owner: 'Priya Nair',
    ownerImage: 'https://i.pravatar.cc/150?img=12',
    daysAgo: 3,
    size: 0.5,
    sizeLabel: '512 KB',
    favourite: true,
  },
  {
    id: 'nda',
    parent: 'contracts',
    type: 'file',
    name: 'NDA template.docx',
    icon: 'lucide-file-text',
    owner: 'Priya Nair',
    ownerImage: 'https://i.pravatar.cc/150?img=12',
    daysAgo: 9,
    size: 0.1,
    sizeLabel: '96 KB',
  },
  {
    id: 'vendor',
    parent: 'contracts',
    type: 'file',
    name: 'Vendor agreement.pdf',
    icon: 'lucide-file-text',
    owner: 'Amy Santiago',
    ownerImage: 'https://i.pravatar.cc/150?img=45',
    daysAgo: 20,
    size: 0.7,
    sizeLabel: '720 KB',
  },

  // Inside "Product screenshots"
  {
    id: 'ss-dashboard',
    parent: 'screenshots',
    type: 'file',
    name: 'Dashboard.png',
    icon: 'lucide-image',
    owner: 'Sam Rivera',
    ownerImage: 'https://i.pravatar.cc/150?img=33',
    daysAgo: 8,
    size: 1.6,
    sizeLabel: '1.6 MB',
  },
  {
    id: 'ss-settings',
    parent: 'screenshots',
    type: 'file',
    name: 'Settings.png',
    icon: 'lucide-image',
    owner: 'Sam Rivera',
    ownerImage: 'https://i.pravatar.cc/150?img=33',
    daysAgo: 8,
    size: 1.1,
    sizeLabel: '1.1 MB',
  },
  {
    id: 'ss-onboarding',
    parent: 'screenshots',
    type: 'file',
    name: 'Onboarding.png',
    icon: 'lucide-image',
    owner: 'Evan You',
    ownerImage: 'https://avatars.githubusercontent.com/u/499550?v=4',
    daysAgo: 10,
    size: 1.3,
    sizeLabel: '1.3 MB',
  },

  // Inside "Team offsite 2026"
  {
    id: 'off-agenda',
    parent: 'offsite',
    type: 'file',
    name: 'Agenda.pdf',
    icon: 'lucide-file-text',
    owner: 'Ana Costa',
    ownerImage: 'https://i.pravatar.cc/150?img=47',
    daysAgo: 21,
    size: 0.3,
    sizeLabel: '320 KB',
  },
  {
    id: 'off-photo',
    parent: 'offsite',
    type: 'file',
    name: 'Group photo.jpg',
    icon: 'lucide-image',
    owner: 'Ana Costa',
    ownerImage: 'https://i.pravatar.cc/150?img=47',
    daysAgo: 22,
    size: 6.2,
    sizeLabel: '6.2 MB',
  },
  {
    id: 'off-budget',
    parent: 'offsite',
    type: 'file',
    name: 'Budget.xlsx',
    icon: 'lucide-file-spreadsheet',
    owner: 'Priya Nair',
    ownerImage: 'https://i.pravatar.cc/150?img=12',
    daysAgo: 25,
    size: 0.4,
    sizeLabel: '380 KB',
  },
]

export const itemsById = new Map(allItems.map((item) => [item.id, item]))

// Direct children of a folder. Trashed rows drop out; the Trash route shows
// them.
export function childrenOf(folderId: string | null): FileItem[] {
  return allItems.filter((item) => item.parent === folderId && !item.trashed)
}

// The rows a route shows. Home browses the tree; the other views are flat.
export function itemsFor(view: string, folderId: string | null): FileItem[] {
  if (view === 'home') return childrenOf(folderId)
  if (view === 'trash') return allItems.filter((item) => item.trashed)
  const live = allItems.filter((item) => !item.trashed)
  if (view === 'recents')
    return live.filter((item) => item.type === 'file' && item.daysAgo <= 6)
  if (view === 'favourites') return live.filter((item) => item.favourite)
  if (view === 'shared') return live.filter((item) => item.owner !== currentUser)
  return live
}

export function viewLabel(view: string): string {
  return navItems.find((item) => item.key === view)?.label ?? 'Files'
}

export const fileActions = [
  { label: 'Download', icon: 'lucide-download' },
  { label: 'Share', icon: 'lucide-user-plus' },
  { label: 'Rename', icon: 'lucide-pencil' },
  { label: 'Move to trash', icon: 'lucide-trash-2' },
]

export const folderActions = [
  { label: 'Open', icon: 'lucide-folder-open' },
  { label: 'Share', icon: 'lucide-user-plus' },
  { label: 'Rename', icon: 'lucide-pencil' },
  { label: 'Move to trash', icon: 'lucide-trash-2' },
]

// Fixed, chronological buckets. Each row lands in the first bucket whose
// `match` accepts its `daysAgo`; empty buckets drop out of the render.
export const timeBuckets = [
  { key: 'today', label: 'Today', match: (d: number) => d <= 0 },
  { key: 'yesterday', label: 'Yesterday', match: (d: number) => d === 1 },
  { key: 'this-week', label: 'This week', match: (d: number) => d >= 2 && d <= 6 },
  { key: 'last-week', label: 'Last week', match: (d: number) => d >= 7 && d <= 13 },
  { key: 'earlier', label: 'Earlier', match: (d: number) => d >= 14 },
]

// One filterable category per row. Folders are their own category; files map
// from their icon so the data stays the single source of truth.
const categoryByIcon: Record<string, string> = {
  'lucide-file-text': 'document',
  'lucide-file-spreadsheet': 'document',
  'lucide-image': 'image',
  'lucide-file-image': 'image',
  'lucide-video': 'video',
  'lucide-file-archive': 'archive',
}

export function categoryOf(item: FileItem): string {
  if (item.type === 'folder') return 'folder'
  return categoryByIcon[item.icon] ?? 'document'
}

export const typeOptions = [
  { label: 'All types', value: 'all', icon: 'lucide-list-filter' },
  { label: 'Folders', value: 'folder', icon: 'lucide-folder' },
  { label: 'Documents', value: 'document', icon: 'lucide-file-text' },
  { label: 'Images', value: 'image', icon: 'lucide-image' },
  { label: 'Videos', value: 'video', icon: 'lucide-video' },
  { label: 'Archives', value: 'archive', icon: 'lucide-file-archive' },
]

export const typeIcon: Record<string, string> = Object.fromEntries(
  typeOptions.map((option) => [option.value, option.icon]),
)

export function relativeLabel(daysAgo: number): string {
  if (daysAgo <= 0) return 'Today'
  if (daysAgo === 1) return 'Yesterday'
  if (daysAgo < 7) return `${daysAgo} days ago`
  if (daysAgo < 14) return 'Last week'
  if (daysAgo < 30) return `${Math.floor(daysAgo / 7)} weeks ago`
  const months = Math.floor(daysAgo / 30)
  return `${months} ${months === 1 ? 'month' : 'months'} ago`
}
