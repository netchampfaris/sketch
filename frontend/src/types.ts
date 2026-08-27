/** The shapes `sketch.api` returns. One place, so screens agree on them. */

export interface SketchSession {
  user: string
  username: string
  full_name: string
  user_image: string
  has_token: boolean
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
  /** Same-origin path the iframe loads. */
  viewer_path: string
  /** Absolute link a visitor can open. */
  public_url: string
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
}
