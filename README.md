# sbx-workbench

Templates (base images) and kits (mixins) for [Docker Sandboxes](https://docs.docker.com/ai/sandboxes/).
Both publish to Docker Hub, so a project needs only a committed `.sbxenv.yaml`.

```
templates/workbench-laravel/   PHP 8.5, Postgres, Redis, sqlite, node 22, gh, chromium
kits/claude-config/            global CLAUDE.md, statusline, plugins
kits/devup/                    starts the services the image ships stopped
```

## Use

Per project, committed:

```yaml
# <project>/.sbxenv.yaml
schemaVersion: "1"
name: my-project
agent: claude
workspace: .
kits:
  - docker.io/bmillerz/claude-config:1.0.0
  - docker.io/bmillerz/devup:1.3.0
sandboxOptions:
  template: docker.io/bmillerz/workbench-laravel:v1
ports:
  - sandbox: 8000
    host: 8000
secrets:
  STRIPE_SECRET:
    ref: op://Vault/my-project/stripe-secret
```

```
sbx env run                  # create if needed, start, attach
sbx env exec -it -- bash     # second shell
sbx env rm                   # tear down, including scoped secrets
```

Inside a fresh sandbox: `npm ci`, then `createdb <name> && php artisan migrate`,
then `php artisan serve --host 0.0.0.0 --port 8000`.

## Publish

```
docker build --platform linux/arm64 -t workbench-laravel:v1 templates/workbench-laravel
docker tag workbench-laravel:v1 docker.io/bmillerz/workbench-laravel:v1
docker push docker.io/bmillerz/workbench-laravel:v1

sbx kit validate kits/devup
sbx kit push kits/devup docker.io/bmillerz/devup:1.0.0
```

Kit tags must match the spec's `version:` — separate strings, nothing syncs them.

**Bump tags, never rebuild in place.** A host that pulled `:v1` keeps its cached
copy and silently runs the old image.

## Gotchas

- **No init in a sandbox** — everything apt installs is installed-but-stopped.
That's what `devup` is for.
- **Serve on `--host 0.0.0.0`** — 127.0.0.1 inside is unreachable even when the
port is published.
- **The DB starts empty** and isn't the host's Postgres. `.env` wants
`DB_HOST=127.0.0.1`, `DB_USERNAME=agent`, empty password.
- `**node_modules` is bind-mounted** — `npm ci` inside overwrites the host's copy
with Linux builds. `workspace: {path: ., clone: true}` avoids it.
- **The workspace is the host's real files** unless `clone: true`.
- **Never run `npx playwright install`** — chromium is already at
`PLAYWRIGHT_BROWSERS_PATH=/opt/playwright`, on `PATH` as `chromium`.
- **Images are arm64-only.** `docker buildx --platform linux/amd64,linux/arm64 --push` if an Intel host needs one.
- `**sbx env`/`sbx kit` are experimental** and `sbx template save` is broken on
v0.38.0 (ext4 tar bug) — hence building with Docker.

