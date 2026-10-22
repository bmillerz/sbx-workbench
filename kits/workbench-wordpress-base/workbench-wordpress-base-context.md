## WordPress workbench

PHP 8.5, Apache, MariaDB, Redis, Composer and wp-cli are installed. The
sandbox has no init, so `devup` starts MariaDB, Redis and Apache at every
boot; run it again if any reports DOWN.

- Apache serves `/var/www/html` on port 80 (published). `devup` symlinks it
  to the first `wp-load.php` it finds in the workspace; otherwise
  `sudo ln -sfn "$PWD" /var/www/html`.
- Database: `DB_HOST=127.0.0.1`, user `agent` or `root`, empty password.
- Import a dump with `wp db import`, then fix URLs with
  `wp search-replace 'https://live.example' 'http://localhost'`.
- PHP is 8.5; production may run older. Flag plugin errors that look
  version-related rather than patching around them.
- Chromium comes from the Playwright kit — don't run
  `npx playwright install` for the bundled version.
