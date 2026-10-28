// One person, one colour. The fallback avatar (a first letter) takes its colour from the username, so the same
// person looks the same on a pin, a tile, the Demo card, the Share dialog and a gallery card. The toolbar, the
// canvas and the gallery are three builds that import this one rule.
export const AVATAR_THEMES = ['blue', 'green', 'amber', 'violet', 'red'] as const
export type AvatarTheme = (typeof AVATAR_THEMES)[number]

export const avatarTheme = (username: string): AvatarTheme =>
  AVATAR_THEMES[[...username].reduce((n, c) => n + c.charCodeAt(0), 0) % AVATAR_THEMES.length]
