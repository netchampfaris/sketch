// The shell's boot JSON (sketch/viewer.py shell_payload). Never the tree: the frame has that.
export type Person = { user: string; username: string; full_name: string; user_image: string }

export type ShellBoot = {
	name: string
	title: string
	slug: string
	owner_username: string
	role: 'owner' | 'editor' | 'viewer' | 'guest' | ''
	me: Person | null
	is_public: boolean
	sign_in: boolean
	comments_open: number
	badges: unknown
	annotations: unknown
	annotations_epoch: number
	rev: string
	csrf_token: string
	theme: 'light' | 'dark' | null
	prototype_theme: string | null
	frame_src: string
}

export function readBoot(): ShellBoot {
	const el = document.getElementById('sketch-shell')
	const raw = (el?.textContent || '').trim()
	if (!raw || raw === 'SKETCH_SHELL') throw new Error('The sketch-shell slot is empty. Open a Prototype, not the shell page.')
	return JSON.parse(raw)
}
