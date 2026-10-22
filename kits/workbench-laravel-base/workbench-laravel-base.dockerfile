# syntax=docker/dockerfile:1
# Root filesystem for the workbench-laravel-base workload. No agent: Claude
# Code arrives as Docker's sbx-kit-claude-mixin, which also carries the
# credential, session volumes and MCP gateway wiring, so none of that is
# restated here. Chromium arrives the same way, as sbx-kit-playwright.

# The official image's binary, pinned, instead of an unverified installer script.
ARG COMPOSER_VERSION=2.10.3
FROM composer:${COMPOSER_VERSION} AS composer

# Base pinned to a versioned tag so a rebuild only changes when we say so.
# 0.10.0 carries the post-eMudhra CA bundle (2026-10-21). Bump it for the
# next security rebuild; `docker buildx imagetools inspect` lists the tags.
FROM docker/sandbox-templates:shell-0.10.0
ARG COMPOSER_VERSION

USER root

# ponytail: recommends left on, so php pulls apache2 — unused here, harmless.
RUN apt-get update \
 && apt-get install -y -qq \
      php8.5 php8.5-cli php8.5-common php8.5-pgsql php8.5-sqlite3 php8.5-mbstring \
      php8.5-xml php8.5-curl php8.5-zip php8.5-bcmath php8.5-gd php8.5-redis \
      php8.5-intl sqlite3 postgresql postgresql-client redis-server zip wget \
 && rm -rf /var/lib/apt/lists/*

COPY --from=composer /usr/bin/composer /usr/local/bin/composer

# Laravel connects over TCP (DB_HOST=127.0.0.1), and Ubuntu's pg_hba only trusts
# the unix socket — loopback wants scram, which no role here has a password for.
# ponytail: trust on loopback only, inside a throwaway sandbox. Don't copy to a server.
RUN sed -i 's/^\(host.*\(127\.0\.0\.1\/32\|::1\/128\).*\)scram-sha-256/\1trust/' \
      /etc/postgresql/*/main/pg_hba.conf

# Ubuntu's 2M upload and 128M memory defaults trip on media uploads and heavy
# test suites. Same values as the WordPress workload.
RUN printf '%s\n' \
  'upload_max_filesize = 128M' \
  'post_max_size = 128M' \
  'memory_limit = 512M' \
  'max_execution_time = 300' \
  > /etc/php/8.5/cli/conf.d/99-sandbox.ini

# Sandboxes have no init; the descriptor's startup hook runs this every boot.
COPY --chmod=755 files/devup /usr/local/bin/devup

# Fail the build rather than ship something other than what the comments claim.
RUN php -r 'exit(PHP_MAJOR_VERSION.".".PHP_MINOR_VERSION === "8.5" ? 0 : 1);' \
 && composer --version 2>/dev/null | grep -F "Composer version ${COMPOSER_VERSION} "

# Same as Docker's own claude workload: Claude Code sources this before every
# Bash tool call, which is what lets an `export` survive into the next one.
ENV CLAUDE_ENV_FILE=/etc/sandbox-persistent.sh \
    IS_SANDBOX=1

USER agent

# The launch command sbx runs for a session. `claude` comes from the claude
# mixin (/usr/local/bin/claude), which is why the descriptor requires it.
ENTRYPOINT ["claude", "--dangerously-skip-permissions"]
CMD []
