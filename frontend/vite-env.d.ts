/// <reference types="vite/client" />
/// <reference path="types/electron.d.ts" />

interface ImportMetaEnv {
    readonly DEV: boolean
    readonly PROD: boolean
    readonly MODE: string
    readonly BASE_URL: string
    readonly SSR: boolean
}

interface ImportMeta {
    readonly env: ImportMetaEnv
}
