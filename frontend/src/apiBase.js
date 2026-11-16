// Where the API lives. Empty in development, where Vite proxies /api to the
// local server; set VITE_API_URL at build time when the API is on another host
// (the Azure deployment).
export const withBase = (base, path) => `${(base ?? '').replace(/\/+$/, '')}${path}`

export const API_BASE = import.meta.env?.VITE_API_URL ?? ''
