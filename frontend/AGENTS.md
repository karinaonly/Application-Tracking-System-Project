# LandIt — frontend

React 19 + Vite + Tailwind CSS v4 frontend for LandIt. This is
a standalone Vite app; it does not use Figma Make.

## Development

```bash
bun install
bun run dev      # Vite dev server on http://localhost:8443
bun run build    # tsc --noEmit && vite build
bun run preview  # serve the production build
```

The API URL defaults to `http://127.0.0.1:8000`. Override it with
`VITE_API_URL` (for example in `frontend/.env.local`).

## Project structure

- `src/main.tsx` — React entrypoint; imports `src/index.css` and mounts `src/App.tsx`
- `src/App.tsx` — page switch, auth bootstrap, and toasts
- `src/api.ts` — typed API client (auth, resumes, jobs, analyses, exports)
- `src/pages/` — Landing, Auth, Dashboard, Upload, JobDescriptions, Analysis, Settings
- `src/components/` — Navbar, Toast, and shared UI
- `src/types.ts` — shared page/toast types
- `src/index.css` — Tailwind CSS v4 import and theme tokens

## Styling

Tailwind CSS v4 is wired through `@tailwindcss/vite`; `src/index.css` imports
Tailwind and defines the project's theme tokens. Use Tailwind utility classes in
JSX. No `tailwind.config.js` or PostCSS config is needed.

## Code quality

- `bun run build` runs TypeScript before bundling, so a type error fails the build.
- Use double quotes for strings containing apostrophes, or escape them.
- Keep components as default exports, matching the existing pages.
