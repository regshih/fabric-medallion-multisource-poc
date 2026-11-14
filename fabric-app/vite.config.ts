import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import ts from 'typescript';

export default defineConfig({
  // Vite 8/Oxc preserves Stage 3 decorators. Lower Rayfin models with the
  // installed TypeScript compiler so browser builds and Vitest execute the
  // same metadata semantics as the Rayfin CLI. No legacy decorator mode.
  plugins: [
    {
      name: 'rayfin-stage3-models',
      enforce: 'pre',
      transform(source, id) {
        if (
          !id.replaceAll('\\', '/').includes('/rayfin/') ||
          !id.endsWith('.ts') ||
          id.includes('node_modules')
        )
          return;
        const result = ts.transpileModule(source, {
          fileName: id,
          compilerOptions: {
            target: ts.ScriptTarget.ES2022,
            module: ts.ModuleKind.ESNext,
            useDefineForClassFields: true,
            sourceMap: true,
          },
        });
        return { code: result.outputText, map: result.sourceMapText };
      },
    },
    react(),
  ],
  test: { environment: 'jsdom', setupFiles: ['./tests/setup.ts'], clearMocks: true },
  build: { sourcemap: false, target: 'es2022' },
});
