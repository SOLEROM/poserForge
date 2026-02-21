# syntax=docker/dockerfile:1
# Reproducible Development Environment
# Provides a consistent, long-lived shell environment with pinned toolchain versions.

FROM ubuntu:22.04

# ── Metadata ──────────────────────────────────────────────────────────────────
LABEL maintainer="poserForge" \
      description="Reproducible dev container: Node 20, Python 3.11, build tools" \
      version="1.0.0"

# ── Prevent interactive prompts during apt installs ────────────────────────────
ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# ── System packages ────────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Core utilities
    bash \
    curl \
    wget \
    git \
    unzip \
    ca-certificates \
    gnupg \
    lsb-release \
    # Build essentials
    build-essential \
    make \
    pkg-config \
    # Python 3.11
    python3.11 \
    python3.11-venv \
    python3-pip \
    python3-dev \
    # Shell quality of life
    less \
    vim \
    nano \
    jq \
    tree \
    htop \
    # Networking
    iputils-ping \
    dnsutils \
 && rm -rf /var/lib/apt/lists/*

# ── Node.js 20 LTS (via NodeSource) ───────────────────────────────────────────
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
 && apt-get install -y --no-install-recommends nodejs \
 && rm -rf /var/lib/apt/lists/* \
 && npm install -g npm@latest

# ── Python: make python3.11 the default python3 ───────────────────────────────
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 \
 && update-alternatives --install /usr/bin/python  python  /usr/bin/python3.11 1

# ── Upgrade pip and install common Python dev tools ───────────────────────────
RUN pip3 install --no-cache-dir --upgrade pip setuptools wheel \
 && pip3 install --no-cache-dir \
    virtualenv \
    pytest \
    black \
    ruff \
    httpx

# ── Create non-root developer user ────────────────────────────────────────────
ARG DEV_UID=1000
ARG DEV_GID=1000
ARG DEV_USER=dev

RUN groupadd -g "${DEV_GID}" "${DEV_USER}" \
 && useradd -m -u "${DEV_UID}" -g "${DEV_GID}" -s /bin/bash "${DEV_USER}"

# ── Cache directories owned by dev user (will be bind-mounted as named vols) ──
RUN mkdir -p \
    /home/${DEV_USER}/.cache/pip \
    /home/${DEV_USER}/.cache/npm \
    /home/${DEV_USER}/.npm \
    /workspace/dist \
 && chown -R "${DEV_USER}:${DEV_USER}" \
    /home/${DEV_USER} \
    /workspace

# ── Shell configuration for the dev user ──────────────────────────────────────
COPY --chown=${DEV_USER}:${DEV_USER} config/bashrc /home/${DEV_USER}/.bashrc

# ── Switch to dev user ─────────────────────────────────────────────────────────
USER ${DEV_USER}
WORKDIR /workspace

# ── npm cache path (isolated named volume) ────────────────────────────────────
ENV npm_config_cache=/home/${DEV_USER}/.cache/npm \
    PIP_CACHE_DIR=/home/${DEV_USER}/.cache/pip \
    PATH="/home/${DEV_USER}/.local/bin:${PATH}"

# ── Default: drop into an interactive bash shell ──────────────────────────────
CMD ["/bin/bash"]
