import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  // Relative base so the build works from any host path; sections live in the URL hash.
  base: './',
  plugins: [react()],
  build: {
    target: 'es2022',
    // three.js lives alone in the lazily loaded BookCanvas chunk, which is expected to be large.
    chunkSizeWarningLimit: 700,
  },
});
