export function createHash() { let d = ''; return { update(s) { d += s; return this }, digest() { let h = 0; for (let i = 0; i < d.length; i++) h = (h * 31 + d.charCodeAt(i)) | 0; return String(h) } } }
export default { createHash }
