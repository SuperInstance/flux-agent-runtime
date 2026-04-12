# flux-agent-runtime

**FLUX-native agents that bootstrap themselves.**

A Docker-based runtime that creates FLUX agents from scratch. Each agent:
1. Boots in an isolated Docker container
2. Discovers the fleet via CAPABILITY.toml
3. Reads onboarding prompt and bootcamp
4. Creates its own vessel repo on GitHub
5. Picks a task from the fleet board
6. Executes real work (reads code, writes code, opens PRs)
7. Reports results via bottles and issues

## Architecture

```
┌─────────────────────────────────┐
│       Docker Container          │
│  ┌───────────────────────────┐  │
│  │    FLUX VM (Python)       │  │
│  │  ┌─────────────────────┐  │  │
│  │  │  agent.fluxasm      │  │  │
│  │  │  (bytecode brain)   │  │  │
│  │  └─────────────────────┘  │  │
│  │         ↕                  │  │
│  │  ┌─────────────────────┐  │  │
│  │  │  agent_bridge.py    │  │  │
│  │  │  (GitHub API shim)  │  │  │
│  │  └─────────────────────┘  │  │
│  └───────────────────────────┘  │
│         ↕                        │
│    GitHub API (git nervous sys)  │
└─────────────────────────────────┘
```

## Usage

```bash
# Build the agent sandbox
docker build -t flux-agent .

# Boot a new agent (generates unique identity)
docker run --rm -e GITHUB_TOKEN=ghp_xxx flux-agent

# Boot with custom onboarding
docker run --rm -e GITHUB_TOKEN=ghp_xxx \
  -v ./my-onboarding.md:/workspace/onboarding.md flux-agent
```

## What Gets Created

Each booted agent creates:
- `SuperInstance/flux-agent-XXXXXX` — vessel repo with:
  - `CHARTER.md` — who the agent is
  - `IDENTITY.md` — agent metadata
  - `CAPABILITY.toml` — fleet-discoverable capabilities
  - `BOOT-REPORT.md` — what happened during boot
  - `for-fleet/`, `for-oracle1/` — bottle directories

## Self-Replication

This is the revolutionary part:

```
Oracle1 (Python agent)
  → builds flux-agent-runtime (this repo)
    → boots flux-agent-a0fa81 (FLUX-native agent)
      → can build MORE flux-agent-runtimes
        → can boot MORE agents
          → exponential fleet growth
```

A FLUX agent built by a FLUX agent built by Oracle1. The system builds itself.

## Files

- `agent_bridge.py` — FLUX VM ↔ GitHub API bridge
- `agent.fluxasm` — FLUX bytecode agent behavior
- `Dockerfile` — sandbox with Python, Go, Rust, Node, C
- `onboarding.md` — default onboarding prompt

## First Boot

```
🚀 Agent booting...
   Phase 1: Discovering fleet...
   Found 2 agents with CAPABILITY.toml
   Phase 2: Reading bootcamp...
   Phase 3: Scanning task board...
   Phase 4: Checking bottles...
   Found 2 fleet bottles
   Phase 5: Identity = flux-agent-a0fa81
   Phase 6: Creating vessel...
   Vessel created: SuperInstance/flux-agent-a0fa81

✅ Agent flux-agent-a0fa81 is ONLINE
```

## The Holy Grail

If a FLUX agent can:
1. Create its own vessel ✅
2. Pick a task ✅
3. Produce useful code ✅ (bridge to real tools)
4. Be built entirely in FLUX (in progress)
5. Create another FLUX agent (next step)

...then the system builds itself. The fleet becomes self-replicating.
