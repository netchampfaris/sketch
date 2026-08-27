// `frappe-ui/editor` is a separate export subpath, so it needs its own asset.
// Lazy by construction: the import map resolves it only when a Prototype
// imports it, so a Prototype with no Editor never downloads TipTap.
export * from 'frappe-ui/editor'
