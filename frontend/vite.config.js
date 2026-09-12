import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    host: true,
    // Vite's dev server rejects requests carrying an unrecognized Host
    // header by default (anti DNS-rebinding protection) - needed here
    // because it's being reached through a public tunnel hostname, not
    // localhost. Fine for this temporary demo tunnel; remove/tighten this
    // for any longer-lived setup.
    allowedHosts: ['.loca.lt']
  }
})
