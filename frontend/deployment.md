# Frontend deployment

## Production domains

- UI: https://kb.studyninja.ru, https://kb.xteam.pro
- API: https://api.kb.studyninja.ru, https://api.kb.xteam.pro

## Docker Compose

Frontend is deployed as the `frontend` service behind Traefik.

```bash
ENV_FILE=.env.prod docker compose --env-file .env.prod up -d --build
```

## Runtime configuration

The container generates `/env.js` at startup from environment variables matching `VITE_*`.

Required:

- `VITE_API_BASE_URL` (e.g. `https://api.kb.studyninja.ru`)

## Notes

- Changing `VITE_*` variables does not require rebuilding the frontend image; restart the container.
