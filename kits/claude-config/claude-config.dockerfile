# syntax=docker/dockerfile:1
# Overlay for the claude-config mixin: ccstatusline, the statusline wrapper,
# and the static config the install hooks merge in. Everything stages under
# /usr/local — never /home/agent, which may be a mounted volume and whose
# ownership an overlay would otherwise replace (SPEC-v3 §10).
FROM docker/sandbox-templates:shell-0.10.0 AS build
ARG CCSTATUSLINE_VERSION=2.2.32
USER root

# Baked rather than `npx -y ccstatusline@latest` per render: no npm round trip
# on every statusline refresh, and the version can't drift. Single dist file,
# no dependencies; it runs on the workload's node.
RUN npm install -g --prefix /out/usr/local "ccstatusline@${CCSTATUSLINE_VERSION}" \
 && rm -rf /root/.npm \
 && test "$(node -p "require('/out/usr/local/lib/node_modules/ccstatusline/package.json').version")" = "${CCSTATUSLINE_VERSION}"

COPY files/settings.json files/ccstatusline.json /out/usr/local/share/claude-config/
COPY --chmod=755 files/statusline /out/usr/local/bin/claude-config-statusline

# The session monitor: one stdlib-only Python file, run on the workload's
# python3, which the descriptor requires. Its tests live in tests/.
COPY --chmod=755 files/session-deck /out/usr/local/bin/session-deck

FROM scratch
COPY --from=build /out /
