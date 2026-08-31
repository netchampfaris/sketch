/** The shapes `sketch.api` returns. One place, so screens agree on them. */

export interface SketchSession {
  user: string
  username: string
  full_name: string
  user_image: string
  has_token: boolean
  /**
   * When the agent last called /mcp with a good token. Null until it does.
   *
   * This is the connection signal, not `has_token`: `get_agent_token` mints a
   * token on read, so `has_token` turns true the moment a user opens Settings
   * (plan v2, step 1.5). Optional here because the server field is new; every
   * reader must survive an older reply.
   */
  last_used?: string | null
  /** The same instant as "2 minutes ago". Null until the agent connects. */
  last_used_pretty?: string | null
  mcp_endpoint: string
  logout_url: string
}

export interface Prototype {
  name: string
  title: string
  slug: string
  pin: string
  is_public: boolean
  file_count: number
  /** Derived on the server. No field stores it (spec 2). */
  description: string
  modified: string
  updated: string
  /** Same-origin path the Viewer serves. The card links here. */
  viewer_path: string
  /** Absolute link a visitor can open. */
  public_url: string
  /**
   * The card picture, one same-origin path per theme.
   *
   * Null until an agent has run `check` with `screenshot: true`. A theme is
   * absent when that capture failed, so a reader falls back to `light`.
   */
  thumbnail: PrototypeThumbnail | null
}

/**
 * One card on /feed: a public Prototype, and who wrote it.
 *
 * Not a `Prototype`. `sketch.api.public_prototypes` answers a different row
 * (`_public_row`): it names the owner, because the feed crosses users, and it
 * drops `pin` and `is_public`, because every row on it is public and the Pin
 * is a build detail. Nothing here may be written, so there is no `name`: the
 * document id is the owner's, and the address is `username` plus `slug`.
 */
export interface PublicPrototype {
  title: string
  /** The owner's handle. The first half of every Viewer address. */
  username: string
  /** The Avatar's fallback. It makes the initials when there is no image. */
  full_name: string
  /** `User.user_image`, or "" for a user who has none. */
  user_image: string
  slug: string
  file_count: number
  /** Derived on the server, like `Prototype.description`. */
  description: string
  modified: string
  updated: string
  viewer_path: string
  public_url: string
  thumbnail: PrototypeThumbnail | null
}

/** See `Prototype.thumbnail`. Written by `sketch/thumbnails.py`. */
export interface PrototypeThumbnail {
  light?: string
  dark?: string
}

/** One row in the Files browser. `sketch.api.list_prototype_files`. */
export interface PrototypeFile {
  path: string
  /** Bytes on disk. */
  size: number
}

/** One file's source. `sketch.api.read_prototype_file`. */
export interface PrototypeFileSource extends PrototypeFile {
  content: string
  /** True when the file is longer than the server sends. */
  truncated: boolean
}

export interface PrototypeFileChange {
  path: string
  /** One of "added", "modified", "deleted". */
  action: string
}

export interface PrototypeVersion {
  name: string
  /** 1-based, per Prototype. */
  sequence: number
  /** The user prompt, stored verbatim. */
  prompt: string
  summary: string
  changes: PrototypeFileChange[]
  files_added: number
  files_modified: number
  files_deleted: number
  creation: string
  created: string
}

export interface Recipe {
  slug: string
  label: string
  description: string
  icon: string
  /** False while the tree is not vendored yet. */
  available: boolean
}

export interface AgentToken {
  token: string
  endpoint: string
  /** See `SketchSession.last_used`. Same field, same meaning. */
  last_used?: string | null
  /** See `SketchSession.last_used_pretty`. */
  last_used_pretty?: string | null
}
