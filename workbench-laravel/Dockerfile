# Laravel workbench template for Docker Sandboxes (sbx).
# Built here rather than via `sbx template save` because sbx's ext4->tar
# commit path can't read multi-block directories in the sandbox upper layer.
#   docker build --platform linux/arm64 -t workbench-laravel:v1 .
#   docker save workbench-laravel:v1 -o workbench-laravel-v1.tar
#   sbx template load workbench-laravel-v1.tar
FROM docker/sandbox-templates:claude-code

USER root

# ponytail: same flags the sandbox used (recommends left on, so php pulls apache2)
RUN apt-get update \
 && apt-get install -y -qq \
      php8.5 php8.5-cli php8.5-common php8.5-pgsql php8.5-sqlite3 php8.5-mbstring \
      php8.5-xml php8.5-curl php8.5-zip php8.5-bcmath php8.5-gd php8.5-redis \
      php8.5-intl sqlite3 postgresql postgresql-client redis-server zip wget \
 && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://getcomposer.org/installer -o /tmp/composer-setup.php \
 && php /tmp/composer-setup.php --install-dir=/usr/local/bin --filename=composer \
 && rm /tmp/composer-setup.php

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

# Laravel connects over TCP (DB_HOST=127.0.0.1), and Ubuntu's pg_hba only trusts
# the unix socket — loopback wants scram, which no role here has a password for.
# ponytail: trust on loopback only, inside a throwaway sandbox. Don't copy to a server.
RUN sed -i 's/^\(host.*\(127\.0\.0\.1\/32\|::1\/128\).*\)scram-sha-256/\1trust/' \
      /etc/postgresql/*/main/pg_hba.conf

# Sandboxes have no init, so nothing starts the services apt just installed.
# ponytail: this is the whole service manager. Version auto-detected so a
# newer Ubuntu base doesn't silently break it.
RUN printf '%s\n' \
  '#!/bin/sh' \
  '# Start the services a sandbox has no init to start. Safe to re-run.' \
  'V=$(ls /etc/postgresql 2>/dev/null | head -1)' \
  '[ -n "$V" ] && sudo pg_ctlcluster "$V" main start 2>/dev/null' \
  'sudo service redis-server start >/dev/null 2>&1' \
  'sudo -u postgres createuser -s "$(id -un)" 2>/dev/null' \
  'pg_isready -q && echo "postgres $V up" || echo "postgres DOWN"' \
  'redis-cli ping >/dev/null 2>&1 && echo "redis up" || echo "redis DOWN"' \
  'exit 0' \
  > /usr/local/bin/devup && chmod 755 /usr/local/bin/devup

USER agent
