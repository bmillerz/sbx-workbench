# sbx-workbench

[Docker Sandboxes](https://docs.docker.com/ai/sandboxes/) kits in the
[v3 format](https://github.com/docker/sandbox-kit-spec/blob/main/docs/spec/SPEC-v3.md),
published to Docker Hub so a project needs only a committed `sbxenv.yaml`.
Needs sbx v0.47 or later (`long-running@1`); written against v0.49.

```
kits/workbench-laravel/        set: laravel-base + Claude Code + Playwright   ← projects use this
kits/workbench-wordpress/      set: wordpress-base + Claude Code + Playwright ← or this
kits/workbench-laravel-base/   workload: PHP 8.5, Composer, Postgres, Redis, sqlite
kits/workbench-wordpress-base/ workload: PHP 8.5, Apache, MariaDB, Redis, Composer, wp-cli
kits/claude-config/            mixin: prefs, ccstatusline, CLAUDE.md style rules
```

How the pieces divide, following Docker's own kits:

- **Workloads** are the machine: the image, its ports, and a startup hook that
  runs `devup` (sandboxes have no init, so apt's services ship stopped). They
  carry no agent.
- **Claude Code** is Docker's `sbx-kit-claude-mixin`, which owns the
  credential, OAuth, session volumes, settings seed and MCP gateway wiring.
  **Chromium** is Docker's `sbx-kit-playwright`. Neither is restated here.
- **Sets** pin a workload and those two mixins together, by digest, as one
  reference.
- **claude-config** is personal, so it stays out of the sets.

## Use

Per project, committed:

```yaml
# <project>/sbxenv.yaml — no leading dot; since v0.42 `.sbxenv.yaml` is only read from ~
schemaVersion: "1"
name: my-project
agent: workbench-laravel        # a set's agent name is its repository name
workspace: .
kits:
  - docker.io/bmillerz/workbench-laravel:2.0.0
  - docker.io/bmillerz/claude-config:2.0.0
ports:
  - sandbox: 8000
    host: 8000
  - sandbox: 5173
    host: 5173
env:
  SERVER_HOST: "0.0.0.0"        # artisan serve's bind address; composer.json stays stock
secrets:
  STRIPE_SECRET:
    ref: op://Vault/my-project/stripe-secret
```

WordPress: `agent: workbench-wordpress`, the matching kit, and `sandbox: 80`.

```
sbx env run                  # create if needed, start, attach
sbx env exec -it -- bash     # second shell
sbx env rm                   # tear down, including scoped secrets
```

`env:` values beat the project's `.env` (Laravel never overrides a real
environment variable), so they're for sandbox-only differences. `SERVER_HOST`
is the one Laravel needs; add `DB_CONNECTION: pgsql`, `DB_HOST: 127.0.0.1`,
`DB_USERNAME: agent` or `APP_URL` only where `.env` says otherwise. Vite binds
localhost on its own, so port 5173 needs `server: { host: true }` in
`vite.config.js` or `npm run dev -- --host`.

### Moving a project off the v2 setup

1. Replace `.sbxenv.yaml` with the `sbxenv.yaml` above, keeping the project's
   `name`, `env` and `secrets`. Drop `agent: claude`, the `devup` kit and
   `sandboxOptions.template` — the set carries all three.
2. Dump anything inside the old sandbox you need; the workspace is on the Mac,
   the database isn't:
   `sbx exec <name> -- pg_dump -h 127.0.0.1 -U agent <db> > <db>.sql`
3. `sbx rm <name>` — by name, because sbx no longer reads `.sbxenv.yaml` in a
   project, so `sbx env rm` can't find the old one.
4. `sbx env run`. The plan should say `1 to add`; approve it, and the claude
   kit's credential request.
5. Inside: `createdb <db>`, then migrate or
   `psql -h 127.0.0.1 -U agent <db> < <db>.sql`.

Docker recommends keeping env files outside the mounted workspace, so an agent
can't change the host-side commands a later run executes. sbx mounts the file
read-only into the sandbox and this one declares no host commands, so keeping it
in the project is a judgment call — move it out if you add `lifecycle:` or
`command:` secrets.

## Plugins, MCP and skills

- **Plugins** live on the claude.ai account ([Customize → Plugins](https://claude.ai/customize/plugins)):
  add from Discover, or add a GitHub marketplace with **Sync automatically**
  on. They sync into every Claude Code session signed in to that account —
  the Mac and each sandbox — as `<name>@synced`, so nothing here lists them.
  Directory copies are reviewed and lag GitHub; a marketplace tracks it. In a
  sandbox, sync needs a claude.ai login, not an API key: `/login`, or a
  subscription in `sbx secret set anthropic` (claude-config clears the
  `apiKeyHelper` the claude kit would otherwise write).
- **MCP servers** go through sbx's gateway, not plugins: tokens stay on the host
  and one registration serves every sandbox. Declare personal ones once in
  `~/.sbxenv.yaml`; its `mcp.servers` list combines with each project's:

  ```yaml
  # ~/.sbxenv.yaml
  schemaVersion: "1"
  mcp:
    servers:
      - name: context7
        url: https://mcp.context7.com/mcp
  ```

  Or ad hoc: `sbx mcp add <name> --url <url>`, then
  `sbx mcp load <name> --sandbox <sandbox>` for one that already exists.
  `sbx env run` shows the merged plan before applying it. A `--command`
  (stdio) server runs on the Mac, outside the sandbox; prefer `--url`.
  claude.ai connectors follow the login and need none of this.
- **Skills** that aren't part of a plugin: `sbx skills import` copies
  `~/.claude/skills` from the Mac — a copy, so re-run it after changes — and
  `sbx skills add <git-url>` takes one from a repo. They're shared read-only
  into every sandbox. Project skills belong in the repo's `.claude/skills/`.

## Publish

```
./publish.sh                 # all kits, multi-arch, in dependency order
./publish.sh claude-config   # just one
```

Tags come from each kit's `version:`, and the script refuses to overwrite one —
**bump, never rebuild in place**. Sets pin their components by digest at
build, so republish a set whenever a component it lists changes.

Building is validating: the `# syntax=docker/sandbox-kit:3` frontend rejects
any malformed descriptor. `sbx kit validate` doesn't accept v3 source kits;
use `docker buildx build kits/<k> -f kits/<k>/<k>.yaml --output type=cacheonly`
or `sbx kit inspect ./kits/<k>`. Run a local kit directly with
`sbx run ./kits/workbench-laravel-base --kit docker.io/docker/sbx-kit-claude-mixin:2.1.292`.

Security rebuilds (e.g. the eMudhra CA compromise, Oct 2026): bump the
`docker/sandbox-templates:shell-<version>` base in both workload recipes, bump
every version, republish, and recreate sandboxes — existing ones keep their old
filesystem.

## Gotchas

- **Bind to `0.0.0.0`** — 127.0.0.1 inside is unreachable from the host.
- **DB creds** — `127.0.0.1`, user `agent`, empty password (WordPress also
  takes `root`).
- **`node_modules` is bind-mounted** — `npm ci` inside overwrites the host's copy
  with Linux builds. `workspace: {path: ., clone: true}` avoids it.
- **Startup hooks run alongside the agent**, not before it. `devup` finishes in
  a couple of seconds; rerun it if anything reports DOWN.
- **New account plugins** reach a sandbox at the next session start; run
  `/reload-plugins` in one that's already open.
