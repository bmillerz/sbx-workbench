# sbx-workbench

Templates (base images) and kits (mixins) for [Docker Sandboxes](https://docs.docker.com/ai/sandboxes/).
Both publish to Docker Hub, so a project needs only a committed `.sbxenv.yaml`.

```
templates/workbench-laravel/   PHP 8.5, Postgres, Redis, sqlite, node 22, gh, chromium
templates/workbench-wordpress/ PHP 8.5, MariaDB, Apache, wp-cli, node 22, gh, chromium
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
  - docker.io/bmillerz/devup:1.0.1
sandboxOptions:
  template: docker.io/bmillerz/workbench-laravel:v1
ports:
  - sandbox: 8000
    host: 8000
  - sandbox: 5173
    host: 5173
env:
  SERVER_HOST: "[::]"
secrets:
  STRIPE_SECRET:
    ref: op://Vault/my-project/stripe-secret
```

```
sbx env run                  # create if needed, start, attach
sbx env exec -it -- bash     # second shell
sbx env rm                   # tear down, including scoped secrets
```

Inside a fresh Laravel sandbox: `npm ci`, then `createdb <name> && php artisan migrate`,
then `composer dev` — `SERVER_HOST` above makes it bind dual-stack.

WordPress serves over Apache on port 80, so publish `sandbox: 80` and point the
docroot at the project once inside: `sudo ln -sfn "$PWD" /var/www/html`. Import a
dump with `sbx cp` then `wp db import`, and fix URLs with `wp search-replace`.

## Publish

```
docker build --platform linux/arm64 -t workbench-laravel:v1 templates/workbench-laravel
docker tag workbench-laravel:v1 docker.io/bmillerz/workbench-laravel:v1
docker push docker.io/bmillerz/workbench-laravel:v1

sbx kit validate kits/devup
sbx kit push kits/devup docker.io/bmillerz/devup:1.0.1
```

Kit tags must match the spec's `version:` — separate strings, nothing syncs them.

**Bump tags, never rebuild in place.** A host that pulled `:v1` keeps its cached
copy and silently runs the old image.

Images are arm64-only — add `docker buildx --platform linux/amd64,linux/arm64
--push` if an Intel host needs one. Built with Docker rather than
`sbx template save`, which is broken on v0.38.0 (ext4 tar bug).

## Gotchas

- **No init in a sandbox** — apt installs are installed-but-stopped. That's what `devup` is for.
- **Serve on `[::]`, not `0.0.0.0`** — 127.0.0.1 inside is unreachable, and macOS resolves
  `localhost` to `::1` first. Laravel: set `SERVER_HOST: "[::]"` in the env file — `artisan
  serve` reads it, so composer.json stays stock.
- **DB creds** — `DB_HOST=127.0.0.1`, `DB_USERNAME=agent`, empty password.
- **`node_modules` is bind-mounted** — `npm ci` inside overwrites the host's copy with Linux builds. `workspace: {path: ., clone: true}` avoids it.
- **Never run `npx playwright install`** — chromium is already at `/opt/playwright`, on `PATH` as `chromium`.
