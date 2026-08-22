# Code Server — VS Code in the browser for aw-workspace. Ported from
# agentic-workspace's tools/code-server/Dockerfile (same base image + baked
# tooling/extensions); the only structural change is that the runtime
# command that used to be passed as `docker run` args (monolith's
# src/config/aw.json docker_services.code-server) is now baked into
# ENTRYPOINT/CMD, since aw-workspace's ContainerSupervisor (Tier-2 apps)
# only ever runs `docker run <image>` with no extra args of its own.
#
# Published by .github/workflows/build.yml as
# ghcr.io/tekflox/aw-app-code-server:latest.
FROM codercom/code-server:latest

USER root

# coder is uid 1000 — matches this workspace's own container users. No remap.

# ── System packages ──────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    unzip \
    git \
    jq \
    less \
    gnupg \
    ca-certificates \
    build-essential \
    python3 \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

# ── AWS CLI v2 ───────────────────────────────────────────────────────────────
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then \
        URL="https://awscli.amazonaws.com/awscli-exe-linux-aarch64.zip"; \
    else \
        URL="https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip"; \
    fi && \
    curl -fsSL "$URL" -o /tmp/awscliv2.zip && \
    unzip -q /tmp/awscliv2.zip -d /tmp && \
    /tmp/aws/install && \
    rm -rf /tmp/awscliv2.zip /tmp/aws

# ── Node.js (LTS) ────────────────────────────────────────────────────────────
RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# ── Python pip packages ──────────────────────────────────────────────────────
RUN pip3 install --no-cache-dir --break-system-packages \
    boto3 \
    httpx \
    requests

# ── VS Code extensions ───────────────────────────────────────────────────────
# Installed at image build time so they're always present.
#
# IMPORTANT: install into a SEED path (not ~/.local/share/code-server) because
# the runtime bind mount of $AW_APP_DATA shadows the default home/profile,
# which would otherwise erase everything baked here. The entrypoint hook
# at /entrypoint.d/10-seed-extensions.sh copies the seed → mounted dir on
# container start, only filling in extensions the user hasn't already got.
# Add/remove extensions here; user-installed ones persist via the mount.
USER root
RUN mkdir -p /opt/code-server-extensions-seed && \
    chown -R coder:coder /opt/code-server-extensions-seed
USER coder
RUN code-server --extensions-dir /opt/code-server-extensions-seed --install-extension ms-python.python \
    && code-server --extensions-dir /opt/code-server-extensions-seed --install-extension dbaeumer.vscode-eslint \
    && code-server --extensions-dir /opt/code-server-extensions-seed --install-extension esbenp.prettier-vscode \
    && code-server --extensions-dir /opt/code-server-extensions-seed --install-extension anthropic.claude-code \
    && code-server --extensions-dir /opt/code-server-extensions-seed --install-extension openai.chatgpt

USER root
COPY seed-extensions.sh /entrypoint.d/10-seed-extensions.sh
RUN chmod +x /entrypoint.d/10-seed-extensions.sh

# ── Shell config ─────────────────────────────────────────────────────────────
# Make python3/pip3 available as python/pip for convenience
RUN ln -sf /usr/bin/python3 /usr/local/bin/python \
    && ln -sf /usr/bin/pip3 /usr/local/bin/pip

WORKDIR /opt/aw-workspace

EXPOSE 8543

# Run as root at container runtime, not `coder` (uid 1000). aw-workspace's
# Tier-2 containers run under ROOTLESS podman, where container uid 0 maps
# to the HOST uid that podman itself runs as — the same uid that owns the
# $AW_APP_DATA host directory bind-mounted onto /home/coder (aw-workspace's
# own os.makedirs call). A non-zero container uid maps to a DIFFERENT,
# unrelated subordinate host uid, which can't write into that directory —
# confirmed live: code-server silently failed to come up (proxy reported
# "container unreachable") with `USER coder` here. Every other Tier-2 app
# in this fleet that mounts $AW_APP_DATA (e.g. aw-app-kb) runs as root for
# exactly this reason — see that repo's Dockerfile/entrypoint.sh. HOME is
# set explicitly since root's default is /root, not the coder profile.
USER root
ENV HOME=/home/coder

# Bind on 0.0.0.0:8543 (matches aw-app.json's runtime.port) with no auth —
# the same trust boundary as every other Tier-2 app here: aw-workspace's own
# IdentityGuard sits in front of the container's reverse-proxy mount, so
# code-server itself doesn't need to authenticate the browser separately.
ENTRYPOINT ["/usr/bin/entrypoint.sh"]
# The folder code-server opens with. aw-app.json bind-mounts the workspace
# tree at the SAME absolute path it has outside (/opt/aw-workspace) rather
# than the old /home/coder/project, so a path an agent quotes in chat is the
# path the editor and its terminal both use — no translation for the human
# to do in their head. Note this is a directory the mount provides: run this
# image without that bind and code-server opens an empty folder.
CMD ["--bind-addr", "0.0.0.0:8543", "--auth", "none", "--disable-workspace-trust", "/opt/aw-workspace"]
