# syntax=docker/dockerfile:1
# Root filesystem for the workbench-wordpress-base workload. No agent: Claude
# Code arrives as Docker's sbx-kit-claude-mixin, which also carries the
# credential, session volumes and MCP gateway wiring, so none of that is
# restated here. Chromium arrives the same way, as sbx-kit-playwright.
#
# ponytail: PHP 8.5, not the 8.3 that Cloudways runs. Ubuntu 26.04 ships only
# 8.5 and ondrej's PPA stops at noble, so 8.3 would mean grafting binaries from
# the official php image or abandoning the sbx base. Living with the version
# gap until a plugin actually breaks on 8.5.

# The official image's binary, pinned, instead of an unverified installer script.
ARG COMPOSER_VERSION=2.10.3
FROM composer:${COMPOSER_VERSION} AS composer

# Base pinned to a versioned tag so a rebuild only changes when we say so.
# 0.10.0 carries the post-eMudhra CA bundle (2026-10-21). Bump it for the
# next security rebuild; `docker buildx imagetools inspect` lists the tags.
FROM docker/sandbox-templates:shell-0.10.0
ARG COMPOSER_VERSION

# WordPress's `artisan`. Agents reach for this constantly.
# Pinned release, checked against its published sha512.
ARG WP_CLI_VERSION=2.12.0
ARG WP_CLI_SHA512=be928f6b8ca1e8dfb9d2f4b75a13aa4aee0896f8a9a0a1c45cd5d2c98605e6172e6d014dda2e27f88c98befc16c040cbb2bd1bfa121510ea5cdf5f6a30fe8832

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

COPY --from=composer /usr/bin/composer /usr/local/bin/composer

RUN curl -fsSL https://github.com/wp-cli/wp-cli/releases/download/v${WP_CLI_VERSION}/wp-cli-${WP_CLI_VERSION}.phar \
      -o /usr/local/bin/wp \
 && echo "${WP_CLI_SHA512}  /usr/local/bin/wp" | sha512sum -c - \
 && chmod 755 /usr/local/bin/wp

# Ubuntu's default /var/www/html is removed so devup's symlink can take its place.
COPY files/000-default.conf /etc/apache2/sites-available/000-default.conf
RUN a2enmod rewrite >/dev/null \
 && rm -rf /var/www/html

COPY files/99-sandbox.ini /etc/php/8.5/apache2/conf.d/99-sandbox.ini
COPY files/99-sandbox.ini /etc/php/8.5/cli/conf.d/99-sandbox.ini
COPY files/99-sandbox.cnf /etc/mysql/mariadb.conf.d/99-sandbox.cnf

# Sandboxes have no init; the descriptor's startup hook runs this every boot.
COPY --chmod=755 files/devup /usr/local/bin/devup

# Fail the build rather than ship something other than what the comments claim.
RUN php -r 'exit(PHP_MAJOR_VERSION.".".PHP_MINOR_VERSION === "8.5" ? 0 : 1);' \
 && composer --version 2>/dev/null | grep -F "Composer version ${COMPOSER_VERSION} " \
 && wp --version --allow-root | grep -F "WP-CLI ${WP_CLI_VERSION}"

# Same as Docker's own claude workload: Claude Code sources this before every
# Bash tool call, which is what lets an `export` survive into the next one.
ENV CLAUDE_ENV_FILE=/etc/sandbox-persistent.sh \
    IS_SANDBOX=1

USER agent

# The launch command sbx runs for a session. `claude` comes from the claude
# mixin (/usr/local/bin/claude), which is why the descriptor requires it.
ENTRYPOINT ["claude", "--dangerously-skip-permissions"]
CMD []
