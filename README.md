# harvest-engine

## Worker scaling runtime note

The API now exposes worker scaling endpoints that execute `docker compose` commands:
- `GET /workers`
- `POST /workers/scale?count=N`

This requires the API runtime to have Docker Compose access to the project compose context.
When running via Docker Compose, the API service must have:
- `docker-compose` available in the container image
- host socket mount: `/var/run/docker.sock:/var/run/docker.sock`
- project mount with `docker-compose.yml` (used by `COMPOSE_FILE_PATH`)
