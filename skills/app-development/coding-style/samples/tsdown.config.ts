// tsdown config for a published package: multiple entries, with a comment explaining the role of each non-obvious entry.
// From kunkun/packages/sdk/tsdown.config.ts:1-30 (read 2026-10-05, excerpt).
// Note the implement-service.ts comment: it explains why a narrow entry instead of the barrel -
// to avoid dragging the worker-view React renderer side-effect import into service-only plugins.
import { defineConfig } from 'tsdown'

export default defineConfig({
  entry: [
    'src/cli.ts',
    'src/index.ts',
    'src/api/index.ts',
    'src/ai/index.ts',
    'src/resources/index.ts',
    'src/ai-sdk/index.ts',
    'src/resource-codegen/index.ts',
    'src/raycast/index.ts',
    'src/ui/index.ts',
    'src/ui/custom.ts',
    'src/manifest/index.ts',
    'src/contract/index.ts',
    'src/contract/json-schema.ts',
    'src/server/index.ts',
    'src/media/index.ts',
    'src/runtime/index.ts',
    'src/runtime/bootstrap.ts',
    'src/runtime/service-bootstrap.ts',
    // Narrow entry so a `node-headless` service can import `implementService`
    // without pulling the `runtime/index` barrel, which re-exports `startPlugin`
    // from `plugin-entry` and therefore side-effect-imports
    // `@uniview/react-renderer`. A service-only plugin has no reason to bundle
    // the worker-view React renderer, and often cannot even resolve it.
    'src/runtime/implement-service.ts',
    'src/runtime/channel.ts',
    'src/runtime/context.ts',
  ],
})
