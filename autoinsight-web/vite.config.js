import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    commonjsOptions: {
      include: [/plotly\.js/, /react-plotly\.js/, /node_modules/],
      transformMixedEsModules: true,
    },
  },
  optimizeDeps: {
    include: ['plotly.js-dist-min', 'react-plotly.js'],
  },
})