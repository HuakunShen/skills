---
name: shadcn-svelte-monorepo
description: Use when setting up, fixing, or explaining shadcn-svelte in a pnpm/SvelteKit monorepo where generated components live in a shared UI package such as packages/ui and an app such as apps/desktop consumes them through aliases. Trigger for shadcn-svelte components.json, SvelteKit kit.alias, $ui imports, shared ui packages, workspace component reuse, or problems where the shadcn-svelte CLI writes files to the wrong package.
---

# Shadcn Svelte Monorepo

## Purpose

Use this skill to keep shadcn-svelte components reusable across a monorepo. The key idea is simple: the app owns the shadcn CLI entry point and global CSS, while `components.json` aliases and SvelteKit aliases point generated component files into a shared UI package.

In Kunkun, `apps/desktop` is the main app and `packages/ui` owns reusable Svelte components.

## Source Of Truth

Check these files first before making changes:

- `apps/desktop/components.json` controls where the shadcn-svelte CLI places generated files when run from the desktop app.
- `apps/desktop/svelte.config.js` maps `$ui/*` to `../../packages/ui/src/lib/*` so the desktop renderer can import source from the shared package during development.
- `packages/ui/components.json` is useful when running shadcn-svelte directly inside the UI package.
- `packages/ui/svelte.config.js` maps `$ui/*` to `./src/lib/*` for the UI package itself.
- `packages/ui/src/lib/components/ui/` is the canonical home for reusable shadcn-svelte primitives.

## Official Docs Check

When the user asks about shadcn-svelte setup, installation, CLI behavior, or configuration, fetch current docs before answering or editing:

1. Resolve docs: `npx ctx7@latest library shadcn-svelte "<user question>"`
2. Query the selected ID: `npx ctx7@latest docs /websites/shadcn-svelte "<user question>"`

Relevant official concepts to verify in docs:

- `components.json` aliases tell the CLI where to place generated components, utilities, hooks, and UI files.
- SvelteKit `kit.alias` must define any non-default alias used by `components.json`.
- Components are added with commands such as `pnpm dlx shadcn-svelte@latest add button`.

## Kunkun Pattern

The desktop app's `components.json` intentionally points shadcn output into `$ui`:

```json
{
  "tailwind": {
    "css": "src/routes/layout.css",
    "baseColor": "neutral"
  },
  "aliases": {
    "components": "$ui/components",
    "utils": "$ui/utils",
    "ui": "$ui/components/ui",
    "hooks": "$ui/hooks",
    "lib": "$lib"
  },
  "typescript": true,
  "registry": "https://shadcn-svelte.com/registry"
}
```

The desktop app resolves `$ui` to the package source:

```js
const config = {
  kit: {
    alias: {
      "$lib/*": "./src/lib/*",
      "$ui/*": "../../packages/ui/src/lib/*",
      "$electron/*": "./electron/*"
    }
  }
};
```

The UI package resolves the same alias locally:

```js
const config = {
  kit: {
    alias: {
      "$lib/*": "./src/lib/*",
      "$ui/*": "./src/lib/*"
    }
  }
};
```

This lets app code import shared primitives consistently, for example:

```svelte
<script lang="ts">
  import { Button } from "$ui/components/ui/button";
</script>
```

## Setup Workflow

1. Create or identify the reusable UI package, usually `packages/ui`.
2. Ensure the UI package has a SvelteKit config with `kit.alias` mapping `$ui/*` to its own `src/lib/*`.
3. Ensure the consuming app has a SvelteKit config mapping `$ui/*` to the UI package source, not to `node_modules` or built `dist`.
4. Configure the consuming app's `components.json` aliases so shadcn-svelte writes reusable files under `$ui/components`, `$ui/components/ui`, `$ui/hooks`, and `$ui/utils`.
5. Keep the app's `tailwind.css` path in `components.json` pointed at the app's global CSS file, because the app owns rendering and Tailwind theme loading.
6. Add components from the consuming app directory when you want the CLI to install dependencies and generate files for that app while writing reusable component source to the UI package.
7. Add or verify workspace dependencies in the app, for example `@kunkunsh/ui: workspace:*`, plus any runtime dependencies shadcn components need.
8. Run the smallest relevant checks, usually `pnpm --filter @kunkunsh/ui check` and `pnpm --filter kunkun-electron check`.

## Adding A Component In Kunkun

Run shadcn-svelte from the app whose `components.json` points to shared UI:

```bash
pnpm --dir apps/desktop dlx shadcn-svelte@latest add button
```

Expected result:

- Component primitives land under `packages/ui/src/lib/components/ui/<component>/`.
- Shared helpers land under `packages/ui/src/lib/utils` or `packages/ui/src/lib/hooks` depending on the registry item.
- App-level CSS remains `apps/desktop/src/routes/layout.css` unless the user intentionally changes the app theme entry point.

If the command is run from `packages/ui`, use `packages/ui/components.json`; this is useful for UI-package-only work, but it may not update app-specific dependencies or CSS in the same way.

## Review Checklist

Before finishing setup or a fix, verify:

- `components.json` aliases and `svelte.config.js` aliases agree on `$ui`.
- Generated reusable components are in `packages/ui/src/lib`, not accidentally under `apps/desktop/src/lib`.
- The app imports from `$ui/components/ui/...` for shared primitives.
- The app's global CSS path in `components.json` points to the app, not the UI package, unless the architecture intentionally centralizes global CSS.
- `packages/ui` exports or source aliases support the way the app imports components.
- Typechecking covers both the UI package and the consuming app.

## Common Problems

| Problem | Likely Cause | Fix |
| --- | --- | --- |
| CLI writes components into the app | `components.json` aliases still point to `$lib` or local paths | Change `components`, `ui`, `hooks`, and `utils` aliases to `$ui/...` |
| Imports from `$ui` fail | Consuming app lacks `kit.alias` for `$ui/*` | Add `$ui/*: "../../packages/ui/src/lib/*"` in the app's `svelte.config.js` |
| UI package cannot typecheck its own components | UI package lacks local `$ui/*` alias | Add `$ui/*: "./src/lib/*"` in `packages/ui/svelte.config.js` |
| Components render unstyled | App global CSS is missing Tailwind/theme imports or `components.json.tailwind.css` points to the wrong file | Keep CSS in the consuming app and verify it is loaded by the root layout |
| Dependencies installed in only one package | Running CLI from a different workspace changes which package receives dependency updates | Check the package where the CLI ran and add required deps to the actual consumer or UI package as appropriate |
| Built package imports fail but dev source imports work | Package exports only `.` and not subpaths | Prefer `$ui` source aliases in monorepo dev, or add explicit package exports if consumers import from `@kunkunsh/ui/...` |

## Kunkun-Specific Guidance

- Prefer existing shared components in `packages/ui/src/lib/components/ui/` before adding one-off UI in `apps/desktop`.
- Keep browser/UI reusable component logic in `packages/ui`; `apps/desktop` should only contain app-specific routes, state wiring, and shell UI composition.
- Do not put shadcn-svelte primitives under `apps/desktop/electron`; Electron is shell code and cannot own browser UI components.
- If a component is only for one route but has no desktop-shell dependency, still consider `packages/ui` when it can be reused by future shells or web UI.

## Minimal Template For Another Monorepo

For an app at `apps/web` and a UI package at `packages/ui`:

```json
// apps/web/components.json
{
  "tailwind": { "css": "src/routes/app.css", "baseColor": "neutral" },
  "aliases": {
    "components": "$ui/components",
    "utils": "$ui/utils",
    "ui": "$ui/components/ui",
    "hooks": "$ui/hooks",
    "lib": "$lib"
  },
  "typescript": true,
  "registry": "https://shadcn-svelte.com/registry"
}
```

```js
// apps/web/svelte.config.js
const config = {
  kit: {
    alias: {
      "$lib/*": "./src/lib/*",
      "$ui/*": "../../packages/ui/src/lib/*"
    }
  }
};
```

```js
// packages/ui/svelte.config.js
const config = {
  kit: {
    alias: {
      "$lib/*": "./src/lib/*",
      "$ui/*": "./src/lib/*"
    }
  }
};
```
