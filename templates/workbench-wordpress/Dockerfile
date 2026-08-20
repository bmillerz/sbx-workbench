# syntax=docker/dockerfile:1
# WordPress workbench template for Docker Sandboxes (sbx).
#   docker build --platform linux/arm64 -t workbench-wordpress:v1 .
#   docker tag workbench-wordpress:v1 docker.io/bmillerz/workbench-wordpress:v1
#   docker push docker.io/bmillerz/workbench-wordpress:v1
# Tags are immutable — bump, never rebuild in place.
#
# ponytail: PHP 8.5, not the 8.3 that Cloudways runs. Ubuntu 26.04 ships only
# 8.5 and ondrej's PPA stops at noble, so 8.3 would mean grafting binaries from
# the official php image or abandoning the sbx base. Living with the version
# gap until a plugin actually breaks on 8.5.
FROM docker/sandbox-templates:claude-code

LABEL org.opencontainers.image.source="https://github.com/bmillerz/sbx-workbench"

USER root

# libapache2-mod-php pulls apache2; WordPress has no `artisan serve` equivalent
# and php -S mishandles WP's loopback requests, cron and admin-ajax.
# ponytail: no sqlite, no pgsql — WordPress is MariaDB only.
RUN apt-get update \
 && apt-get install -y -qq \
      php8.5 php8.5-cli php8.5-common php8.5-mysql php8.5-mbstring php8.5-xml \
      php8.5-curl php8.5-zip php8.5-bcmath php8.5-gd php8.5-intl php8.5-redis \
      libapache2-mod-php8.5 mariadb-server mariadb-client redis-server zip wget \
 && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://getcomposer.org/installer -o /tmp/composer-setup.php \
 && php /tmp/composer-setup.php --install-dir=/usr/local/bin --filename=composer \
 && rm /tmp/composer-setup.php

# WordPress's `artisan`. Agents reach for this constantly.
RUN curl -fsSL https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar \
      -o /usr/local/bin/wp && chmod 755 /usr/local/bin/wp

# Chromium for screenshots. Ubuntu's apt `chromium` is a snap shim that can't run
# in a container, so take Playwright's build; --with-deps pulls the shared libs.
# ponytail: shared path + world-readable, so any sandbox user finds it.
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright
RUN npx --yes playwright@latest install --with-deps chromium \
 && chmod -R a+rX /opt/playwright \
 && rm -rf /var/lib/apt/lists/* /root/.npm

# ponytail: on PATH under the name anything would look for, so nobody has to be
# told where it is (and nobody re-downloads 150MB deciding it's absent).
RUN ln -sf "$(ls -d /opt/playwright/chromium-*/chrome-linux/chrome | head -1)" /usr/local/bin/chromium

# Ubuntu's default /var/www/html is removed so the symlink can take its place.
# The workspace mounts at its absolute host path, unknown at build time, so the
# vhost serves a symlink the agent points at the project:
#   sudo ln -sfn "$PWD" /var/www/html
# ponytail: FollowSymLinks + AllowOverride so WP permalinks work via .htaccess.
RUN printf '%s\n' \
  '<VirtualHost *:80>' \
  '  DocumentRoot /var/www/html' \
  '  <Directory /var/www/html>' \
  '    Options FollowSymLinks' \
  '    AllowOverride All' \
  '    Require all granted' \
  '  </Directory>' \
  '</VirtualHost>' \
  > /etc/apache2/sites-available/000-default.conf \
 && a2enmod rewrite >/dev/null \
 && rm -rf /var/www/html

# Sandboxes have no init, so nothing starts the services apt just installed.
# ponytail: same contract as workbench-laravel — idempotent, always exits 0, so
# the `devup` kit works against either image unchanged.
# MariaDB root authenticates via unix_socket, hence plain `sudo mariadb`. The
# agent user needs an explicit `IDENTIFIED BY ''` — MariaDB 11.8 gives a bare
# CREATE USER an unusable auth string, which fails login with error 1698. It
# gets no password: wp-config wants DB_USER/DB_PASSWORD over TCP and
# nothing here has a real one, mirroring the Laravel image's pg_hba trust.
RUN <<'SH'
cat > /usr/local/bin/devup <<'DEVUP'
#!/bin/sh
# Start the services a sandbox has no init to start. Safe to re-run.
sudo service mariadb start >/dev/null 2>&1
sudo service redis-server start >/dev/null 2>&1
sudo service apache2 start >/dev/null 2>&1
U=$(id -un)
sudo mariadb -e "CREATE USER IF NOT EXISTS \`$U\`@localhost IDENTIFIED BY '';
  GRANT ALL PRIVILEGES ON *.* TO \`$U\`@localhost WITH GRANT OPTION;
  FLUSH PRIVILEGES;" 2>/dev/null
# Client wp-config.php files commonly use root with an empty password in dev,
# and they are committed, so the sandbox accommodates them rather than the
# other way round. Loopback only, throwaway sandbox - same posture as the
# Laravel image's pg_hba trust.
sudo mariadb -e "ALTER USER 'root'@'localhost' IDENTIFIED VIA mysql_native_password USING '';" 2>/dev/null
mariadb-admin ping >/dev/null 2>&1 && echo "mariadb up" || echo "mariadb DOWN"
redis-cli ping >/dev/null 2>&1 && echo "redis up" || echo "redis DOWN"
pidof apache2 >/dev/null && echo "apache up" || echo "apache DOWN"
[ -e /var/www/html ] || echo "note: sudo ln -sfn \"$PWD\" /var/www/html"
exit 0
DEVUP
chmod 755 /usr/local/bin/devup
SH

USER agent
