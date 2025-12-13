# KnowledgeBaseAI Frontend

React + TypeScript + Vite frontend for KnowledgeBaseAI.

## Tech stack

- React
- TypeScript
- Vite
- Nginx (production container)

## Runtime configuration (VITE_*)

In production, the frontend reads configuration at runtime from `/env.js`.

- `frontend/public/env.js` provides a safe default for local builds.
- In Docker, `frontend/docker-entrypoint.sh` generates `/usr/share/nginx/html/env.js` from container environment variables matching `VITE_*`.

Required variables:

- `VITE_API_BASE_URL`

Production API URLs:

- https://api.kb.studyninja.ru
- https://api.kb.xteam.pro

## Development

```bash
npm install
npm run dev
```

## Build

```bash
npm run build
npm run preview
```

## Deployment

See: [`deployment.md`](./deployment.md)

## Contributing

See root docs: `development.md` and `deployment.md`.
