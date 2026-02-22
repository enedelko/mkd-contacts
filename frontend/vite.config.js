import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { readFileSync } from 'fs'
import { dirname, resolve } from 'path'
import { fileURLToPath } from 'url'
import { marked } from 'marked'

const __dirname = dirname(fileURLToPath(import.meta.url))

/** Plugin: .md?policy or .md?html → parse Markdown to HTML, split by <!-- ADMIN_LIST -->, export { htmlBefore, htmlAfter }. */
function policyMarkdownPlugin() {
  const MARKER = '<!-- ADMIN_LIST -->'
  return {
    name: 'policy-markdown',
    load(id) {
      if (!id.includes('.md')) return null
      if (!id.includes('?policy') && !id.includes('?html')) return null
      const filePath = id.split('?')[0]
      const content = readFileSync(filePath, 'utf-8')
      const html = marked.parse(content)
      const parts = html.split(MARKER)
      if (parts.length === 2) {
        return `export default { htmlBefore: ${JSON.stringify(parts[0])}, htmlAfter: ${JSON.stringify(parts[1])} }`
      }
      return `export default { htmlBefore: ${JSON.stringify(html)}, htmlAfter: "" }`
    },
  }
}

export default defineConfig({
  plugins: [policyMarkdownPlugin(), react()],
  resolve: {
    alias: { '@': resolve(__dirname, 'src') },
  },
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': { target: 'http://backend:8000', changeOrigin: true },
    },
  },
})
