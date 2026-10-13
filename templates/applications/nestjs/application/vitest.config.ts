import swc from 'unplugin-swc';
import { defineConfig } from 'vitest/config';

// SWC compiles decorators + emitDecoratorMetadata, which NestJS dependency injection needs.
export default defineConfig({
  plugins: [swc.vite({ module: { type: 'es6' } })],
  test: {
    globals: true,
    include: ['test/**/*.spec.ts'],
    environment: 'node',
  },
});
