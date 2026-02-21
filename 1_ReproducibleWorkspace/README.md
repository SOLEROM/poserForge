# 1 — Reproducible Workspace

A Docker Compose pattern for a **fully reproducible development environment**.

Instead of installing language runtimes and tools on your host machine, you spin up a single long-lived container that holds everything. Source code is bind-mounted from the host so edits are reflected instantly. Caches and build artifacts live in named volumes so your host filesystem stays clean.

```
Host filesystem                     Container (/workspace)
──────────────────                  ──────────────────────────────
./src/          ─── bind mount ───► /workspace/src/
./tests/        ─── bind mount ───► /workspace/tests/
                                    /workspace/dist/  ◄── named volume (artifacts)
                    named volume ──► ~/.cache/pip      (pip cache)
                    named volume ──► ~/.cache/npm      (npm cache)
```

---

## What's inside the container

| Tool | Version |
|---|---|
| OS | Ubuntu 22.04 |
| Node.js | 20 LTS |
| npm | latest |
| Python | 3.11 |
| pip / pytest / black / ruff | latest |
| git, make, curl, jq, tree | system |

The container runs as a non-root user (`dev`, uid 1000) and drops into an interactive bash shell.

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Mac/Windows) or Docker Engine + Compose plugin (Linux)
- `docker compose version` ≥ 2.x

---

## Quick start

### 1. Clone and enter the workspace

```bash
git clone <repo-url>
cd poserForge/1_ReproducibleWorkspace
```

### 2. (Optional) Adjust UID/GID to match your host user

This avoids file permission issues on the bind mount.

```bash
# Check your host UID and GID
id -u   # e.g. 1000
id -g   # e.g. 1000

# Edit .env if they differ from 1000
nano .env
```

### 3. Build the image

```bash
docker compose build
# or
make build
```

This downloads the base image and installs all toolchains. Takes ~2 min on first run; subsequent builds are cached.

### 4. Start the container

```bash
docker compose up -d
# or
make up
```

Output:
```
 Volume "poserforge-build-artifacts"  Created
 Volume "poserforge-pip-cache"        Created
 Volume "poserforge-npm-cache"        Created
 Container poserforge-devenv          Started
```

### 5. Enter the shell

```bash
docker compose exec devenv bash
# or
make shell
```

You land inside the container with a banner showing pinned versions:

```
  ┌─────────────────────────────────────────┐
  │   poserForge Reproducible Dev Container  │
  │                                          │
  │   Node  : v20.20.0                       │
  │   Python: Python 3.11.0rc1               │
  │   npm   : v11.10.1                       │
  │                                          │
  │   /workspace  ← your source (bind mount) │
  │   dist/       ← build artifacts (volume) │
  └─────────────────────────────────────────┘

dev@devenv:/workspace$
```

---

## Running the demo

The `src/` directory contains small demo modules that prove the toolchains work.

**Python:**
```bash
# inside the container
python3 src/hello.py
```
```
Hello from Python 3.11, poserForge!
  python: 3.11.0rc1 (...)
  platform: Linux
  arch: x86_64
```

**Node.js:**
```bash
node src/hello.js
```
```
Hello from Node.js v20.20.0, poserForge!
  node: v20.20.0
  platform: linux
  arch: x64
```

---

## Running the tests

### From inside the container

```bash
# Python
python3 -m pytest tests/ -v

# Node.js
node tests/test_node.js
```

### From the host (no need to enter the shell)

```bash
make test
```

Expected output:

```
── Python tests ─────────────────────────────────────
============================= test session starts ==============================
platform linux -- Python 3.11.0rc1, pytest-9.0.2
collected 4 items

tests/test_hello.py::test_greet_contains_name         PASSED  [ 25%]
tests/test_hello.py::test_greet_contains_python_version PASSED  [ 50%]
tests/test_hello.py::test_env_info_keys               PASSED  [ 75%]
tests/test_hello.py::test_env_info_python_version     PASSED  [100%]

============================== 4 passed in 0.01s ===============================

── Node.js tests ────────────────────────────────────
  ✓ greet() includes the name
  ✓ greet() includes 'Node.js'
  ✓ greet() includes runtime version
  ✓ envInfo() has node field
  ✓ envInfo() has platform field
  ✓ envInfo() has arch field
  ✓ Node >= 20 (got v20.20.0)

  Results: 7 passed, 0 failed
```

---

## Container lifecycle

| Command | What it does |
|---|---|
| `docker compose up -d` | Start container in background |
| `docker compose exec devenv bash` | Enter interactive shell |
| `docker compose stop` | Pause container (volumes preserved) |
| `docker compose down` | Remove container (volumes preserved) |
| `docker compose down -v` | Remove container **and** all named volumes |
| `docker compose logs -f devenv` | Stream container logs |

### Makefile shortcuts

```bash
make build    # (re)build the image
make up       # start in background
make shell    # start + enter bash
make test     # run all tests from host
make logs     # tail container logs
make clean    # stop + remove artifacts volume
make reset    # stop + remove ALL named volumes (full reset)
```

---

## File layout

```
1_ReproducibleWorkspace/
├── Dockerfile            # Container image definition
├── docker-compose.yml    # Service, mounts, volumes, limits
├── .env                  # Default environment variables
├── .dockerignore         # Files excluded from build context
├── Makefile              # Host-side lifecycle shortcuts
├── config/
│   └── bashrc            # Shell prompt + banner for dev user
├── src/
│   ├── hello.py          # Demo Python module
│   └── hello.js          # Demo Node.js module
└── tests/
    ├── test_hello.py     # pytest suite (Python)
    └── test_node.js      # Plain Node test runner
```

---

## Configuration

All defaults live in `.env`. Override them in the shell or by editing the file before running `docker compose up`.

| Variable | Default | Description |
|---|---|---|
| `DEV_USER` | `dev` | Username inside the container |
| `DEV_UID` | `1000` | UID — should match your host user |
| `DEV_GID` | `1000` | GID — should match your host user |
| `SOURCE_DIR` | `.` | Host path bind-mounted to `/workspace` |
| `PROJECT_NAME` | `myproject` | Passed into container as env var |
| `NODE_ENV` | `development` | Node environment |
| `CPU_LIMIT` | `4` | Max CPUs for the container |
| `MEM_LIMIT` | `4g` | Max RAM for the container |
| `IMAGE_TAG` | `latest` | Tag applied to the built image |

---

## How it guarantees reproducibility

1. **Pinned base image** — `ubuntu:22.04` is a fixed LTS release.
2. **Pinned Node version** — NodeSource `setup_20.x` installs exactly Node 20.
3. **Named volumes** — package caches survive rebuilds so installs are fast *and* consistent.
4. **Non-root user** — UID/GID are build args, so file ownership on the bind mount aligns with the host user without `chmod` hacks.
5. **No host toolchain required** — CI and every developer use the same image; the host only needs Docker.
