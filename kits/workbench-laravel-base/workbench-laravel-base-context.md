## Laravel workbench

PHP 8.5, Composer, Postgres, Redis and sqlite are installed. The sandbox has
no init, so `devup` starts Postgres and Redis at every boot; run it again if
either reports DOWN.

- Database: `DB_HOST=127.0.0.1`, `DB_USERNAME=agent`, empty password.
  Create one with `createdb <name>`.
- Serve on `0.0.0.0`, never the default 127.0.0.1, or the host can't reach
  it: `php artisan serve --host=0.0.0.0` (or `SERVER_HOST=0.0.0.0`), and
  `npm run dev -- --host 0.0.0.0` for Vite. Ports 8000 and 5173 are published.
- Chromium comes from the Playwright kit — don't run
  `npx playwright install` for the bundled version.
