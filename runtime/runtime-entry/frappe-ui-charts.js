// `frappe-ui/charts` is a separate export subpath, so it needs its own asset.
// Lazy by construction, like the editor. Its `style.css` lands in the shared
// `frappe-ui-components.css`, which the Viewer loads eagerly, so a chart is
// styled the moment its bundle arrives.
export * from 'frappe-ui/charts'
