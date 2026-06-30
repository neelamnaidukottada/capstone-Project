import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'node:path'

export default defineConfig({
  plugins: [
    react(),
  ],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov', 'json-summary'],
      reportsDirectory: './coverage',
      include: [
        'src/components/**/*.{ts,tsx}',
        'src/hooks/**/*.{ts,tsx}',
        'src/stores/**/*.{ts,tsx}',
        'src/app/login/**/*.{ts,tsx}',
        'src/app/register/**/*.{ts,tsx}',
        'src/lib/**/*.{ts,tsx}',
      ],
      exclude: [
        'src/**/*.d.ts',
        'src/test/**',
        'src/**/types/**',
        'src/lib/api.ts',
        'src/lib/auth-session.ts',
        'src/lib/supabase/**',
        'src/components/ui/**',
        'src/app/login/page.test.tsx',
        'src/app/register/page.test.tsx',
        'src/components/**/*.test.tsx',
        'src/hooks/**/*.test.tsx',
        'src/stores/**/*.test.ts',
        // Untested structural/layout components not in this test iteration
        'src/components/agent-activity-timeline.tsx',
        'src/components/app-shell.tsx',
        'src/components/approval-modal.tsx',
        'src/components/protected-route.tsx',
        'src/components/providers.tsx',
        'src/components/sidebar-nav.tsx',
        'src/components/theme-toggle.tsx',
        'src/components/toaster.tsx',
        'src/components/top-bar.tsx',
        'src/components/websocket-error-boundary.tsx',
        'src/hooks/use-campaign-queries.ts',
        'src/hooks/use-realtime.ts',
      ],
      thresholds: {
        lines: 70,
        functions: 65,
        branches: 65,
        statements: 70,
      },
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
})
