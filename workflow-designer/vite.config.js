import {defineConfig} from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path';
import {visualizer} from 'rollup-plugin-visualizer';

// https://vite.dev/config/
export default defineConfig({
    base: '/',
    server: {
        port: 3003,
    },
    plugins: [react(), visualizer({
        open: true,
        filename: 'stats.html',
        gzipSize: true,
        brotliSize: true,
    }),],
    resolve: {
        alias: {
            '@': path.resolve(__dirname, 'src'),
        },
    },
    assetsInclude: ["**/*.PNG"],
    build: {
        minify: 'esbuild',
        rollupOptions: {
            output: {
                manualChunks: (id) => {
                    if (id.includes('node_modules')) {
                        return 'vendor';
                    }
                }
            }
        }
    }
})
