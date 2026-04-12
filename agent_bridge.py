#!/usr/bin/env python3
"""FLUX Agent Bridge — connects FLUX bytecode to real-world agent operations.

This is the "nervous system" that lets FLUX bytecode interact with:
- GitHub API (read repos, push commits, open issues)
- Git operations (clone, branch, commit, push)
- Fleet protocol (bottles, CAPABILITY.toml, vessel creation)
- Docker (spawn new agent containers)
"""

import json
import os
import subprocess
import urllib.request
import base64
import time
import hashlib
from typing import Any, Dict, Optional, Callable

# ── GitHub API Layer ─────────────────────────────────────────────────────

class GitHubBridge:
    """Translates FLUX A2A opcodes into GitHub API calls."""
    
    def __init__(self, token: str, org: str = "SuperInstance"):
        self.token = token
        self.org = org
        self.headers = {
            "Authorization": f"token {token}",
            "Content-Type": "application/json",
        }
    
    def api_get(self, path: str) -> Any:
        url = f"https://api.github.com{path}"
        req = urllib.request.Request(url, headers=self.headers)
        return json.loads(urllib.request.urlopen(req).read())
    
    def api_post(self, path: str, data: dict) -> Any:
        url = f"https://api.github.com{path}"
        body = json.dumps(data).encode()
        req = urllib.request.Request(url, data=body, headers=self.headers, method="POST")
        return json.loads(urllib.request.urlopen(req).read())
    
    def api_put(self, path: str, data: dict) -> Any:
        url = f"https://api.github.com{path}"
        body = json.dumps(data).encode()
        req = urllib.request.Request(url, data=body, headers=self.headers, method="PUT")
        return json.loads(urllib.request.urlopen(req).read())
    
    # ── High-level agent operations ──
    
    def clone_repo(self, repo: str, dest: str) -> bool:
        """Clone a repo to dest directory."""
        url = f"https://{self.token}@github.com/{repo}.git"
        result = subprocess.run(["git", "clone", url, dest], capture_output=True, text=True)
        return result.returncode == 0
    
    def read_file(self, repo: str, path: str) -> Optional[str]:
        """Read a file from a repo via API."""
        try:
            data = self.api_get(f"/repos/{repo}/contents/{path}")
            return base64.b64decode(data["content"]).decode()
        except:
            return None
    
    def write_file(self, repo: str, path: str, content: str, message: str, 
                   sha: Optional[str] = None) -> bool:
        """Write a file to a repo via API."""
        encoded = base64.b64encode(content.encode()).decode()
        data = {"message": message, "content": encoded}
        if sha:
            data["sha"] = sha
        try:
            result = self.api_put(f"/repos/{repo}/contents/{path}", data)
            return True
        except Exception as e:
            print(f"  write_file error: {e}")
            return False
    
    def list_files(self, repo: str, path: str = "") -> list:
        """List files in a repo directory."""
        try:
            data = self.api_get(f"/repos/{repo}/contents/{path}")
            return [(item["name"], item["type"]) for item in data]
        except:
            return []
    
    def read_bottles(self, repo: str, direction: str = "for-fleet") -> Dict[str, str]:
        """Read all bottles in a direction folder."""
        bottles = {}
        try:
            files = self.list_files(repo, direction)
            for name, ftype in files:
                if ftype == "file" and name.endswith(".md"):
                    content = self.read_file(repo, f"{direction}/{name}")
                    if content:
                        bottles[name] = content
        except:
            pass
        return bottles
    
    def leave_bottle(self, repo: str, direction: str, filename: str, 
                     content: str, message: str) -> bool:
        """Leave a bottle in a direction folder."""
        path = f"{direction}/{filename}"
        return self.write_file(repo, path, content, message)
    
    def create_vessel(self, name: str, charter: str, identity: dict) -> bool:
        """Create a new vessel repo for an agent."""
        try:
            self.api_post("/user/repos", {
                "name": name,
                "description": f"{identity.get('name', 'Agent')} vessel — {identity.get('role', 'fleet agent')}",
                "private": False,
            })
        except:
            pass
        
        # Create essential files
        self.write_file(f"{self.org}/{name}", "CHARTER.md", charter, "init: vessel charter")
        self.write_file(f"{self.org}/{name}", "IDENTITY.md", 
                       json.dumps(identity, indent=2), "init: agent identity")
        
        # Create bottle directories with README
        for d in ["for-fleet", "from-fleet", "for-oracle1", "message-in-a-bottle"]:
            self.write_file(f"{self.org}/{name}", f"{d}/.gitkeep", "", f"init: {d}")
        
        # Create CAPABILITY.toml
        cap = f"""[agent]
name = "{identity.get('name', 'unknown')}"
type = "git-agent"
role = "{identity.get('role', 'flux-agent')}"
status = "active"
home_repo = "{self.org}/{name}"

[capabilities]
[communication]
bottles = true
issues = true

[resources]
languages = ["fluxasm"]
runtime = "flux-vm"
sandbox = true
"""
        self.write_file(f"{self.org}/{name}", "CAPABILITY.toml", cap, "init: capability declaration")
        return True
    
    def open_issue(self, repo: str, title: str, body: str) -> int:
        """Open an issue. Returns issue number."""
        result = self.api_post(f"/repos/{repo}/issues", {"title": title, "body": body})
        return result.get("number", 0)
    
    def get_latest_commits(self, repo: str, count: int = 5) -> list:
        """Get latest commits from a repo."""
        data = self.api_get(f"/repos/{repo}/commits?per_page={count}")
        return [{"sha": c["sha"][:7], "msg": c["commit"]["message"][:80], 
                 "date": c["commit"]["author"]["date"]} for c in data]
    
    def discover_agents(self) -> list:
        """Scan org repos for CAPABILITY.toml to discover fleet agents."""
        agents = []
        try:
            repos = self.api_get(f"/users/{self.org}/repos?per_page=100")
            for r in repos:
                if r.get("name", "").endswith("-vessel"):
                    cap = self.read_file(r["full_name"], "CAPABILITY.toml")
                    if cap:
                        agents.append({"repo": r["full_name"], "capability": cap})
        except:
            pass
        return agents


# ── FLUX Agent Runtime ──────────────────────────────────────────────────

class FluxAgentRuntime:
    """A complete agent runtime that executes FLUX bytecode with real-world effects."""
    
    def __init__(self, github_token: str, org: str = "SuperInstance"):
        self.github = GitHubBridge(github_token, org)
        self.agent_name = "flux-agent"
        self.vessel_repo = None
        self.confidence = 0.5
        self.energy = 1000
        self.skills = {}
        self.diary = []
        self.state = "BOOTING"
    
    def boot(self, onboarding_prompt: str):
        """Boot the agent from an onboarding prompt."""
        self.diary.append(f"BOOT: Reading onboarding prompt ({len(onboarding_prompt)} chars)")
        print(f"🚀 Agent booting...")
        print(f"   Reading onboarding prompt...")
        
        # Phase 1: Discover the fleet
        self.state = "DISCOVERING"
        print(f"   Phase 1: Discovering fleet...")
        agents = self.github.discover_agents()
        print(f"   Found {len(agents)} agents with CAPABILITY.toml")
        self.diary.append(f"DISCOVER: Found {len(agents)} agents")
        
        # Phase 2: Read bootcamp
        self.state = "LEARNING"
        print(f"   Phase 2: Reading bootcamp...")
        bootcamp = self.github.read_file("SuperInstance/oracle1-vessel", "for-fleet/WELCOME-OPUS.md")
        if not bootcamp:
            bootcamp = self.github.read_file("SuperInstance/oracle1-vessel", "CHARTER.md")
        print(f"   Read bootcamp: {len(bootcamp or '')} chars")
        
        # Phase 3: Scan task board
        self.state = "EVALUATING"
        print(f"   Phase 3: Scanning task board...")
        tasks = self.github.read_file("SuperInstance/oracle1-vessel", "TASKBOARD.md")
        task_count = (tasks or "").count("🔴") + (tasks or "").count("🟠")
        print(f"   Found {task_count} high-priority tasks")
        
        # Phase 4: Check bottles
        self.state = "CHECKING_BOTTLES"
        print(f"   Phase 4: Checking bottles...")
        bottles = self.github.read_bottles("SuperInstance/oracle1-vessel", "for-fleet")
        print(f"   Found {len(bottles)} fleet bottles")
        for name, content in bottles.items():
            print(f"   📨 {name}: {content[:80]}...")
            self.diary.append(f"BOTTLE: {name}")
        
        # Phase 5: Choose identity
        self.state = "IDENTIFYING"
        self.agent_name = f"flux-agent-{hashlib.md5(str(time.time()).encode()).hexdigest()[:6]}"
        print(f"   Phase 5: Identity = {self.agent_name}")
        
        # Phase 6: Create vessel
        self.state = "CREATING_VESSEL"
        print(f"   Phase 6: Creating vessel...")
        identity = {
            "name": self.agent_name,
            "role": "FLUX-native agent — self-bootstrapped",
            "type": "flux-agent",
            "runtime": "flux-vm",
            "bootstrapped_by": "oracle1",
            "confidence": self.confidence,
        }
        charter = f"""# {self.agent_name} Charter

## Origin
This agent was created by the FLUX agent runtime, bootstrapped by Oracle1.
It is a FLUX-native agent — its behavior is defined in FLUX bytecode.

## Mission
Read the fleet task board, pick a task, execute it, report results.

## Communication
Bottles in for-fleet/ and for-oracle1/ on this vessel.
Issues on oracle1-vessel for coordination.
"""
        self.github.create_vessel(self.agent_name, charter, identity)
        self.vessel_repo = f"{self.github.org}/{self.agent_name}"
        print(f"   Vessel created: {self.vessel_repo}")
        
        # Phase 7: Report
        self.state = "ACTIVE"
        report = f"""# {self.agent_name} — Boot Report

## Boot Sequence Complete
- Fleet agents discovered: {len(agents)}
- Bootcamp read: {len(bootcamp or '')} chars
- Tasks available: {task_count}
- Bottles found: {len(bottles)}
- Confidence: {self.confidence}
- Energy: {self.energy}
- State: {self.state}

## Diary
{chr(10).join(f'- {e}' for e in self.diary)}

## Next
Reading task board to pick a specialty.
"""
        self.github.write_file(self.vessel_repo, "BOOT-REPORT.md", report, 
                              "boot report — agent online")
        print(f"\n✅ Agent {self.agent_name} is ONLINE")
        print(f"   Vessel: https://github.com/{self.vessel_repo}")
        
        return self.agent_name


# ── Main: Boot a new FLUX agent ─────────────────────────────────────────

ONBOARDING_PROMPT = """You are a FLUX-native agent joining the SuperInstance fleet.

## Your Fleet
- Oracle1 🔮: Managing Director, runs on Oracle Cloud
- JetsonClaw1 🦀: Edge specialist, runs on Jetson Orin Nano
- Multiple Z agents: specialists (audits, specs, forensics)
- Claude Code agents: runtime engineers

## Your Mission
1. Read the fleet task board
2. Find a task that matches your capabilities
3. Execute the task (read code, write code, open PRs)
4. Report results via bottles and issues
5. Pick another task

## Your Capabilities
- Read/write GitHub repos via FLUX opcodes
- Leave bottles for other agents
- Create and manage your own vessel
- Run tests and report results
- Build new FLUX programs

## Ground Truth
- 88 conformance vectors must always pass
- Don't break what's working
- Communicate via bottles and issues
- Energy is finite — spend it wisely

Start by creating your vessel, reading the task board, and picking a task.
"""

if __name__ == "__main__":
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("Error: GITHUB_TOKEN required")
        exit(1)
    
    runtime = FluxAgentRuntime(token)
    agent_name = runtime.boot(ONBOARDING_PROMPT)
    print(f"\n🎯 Next: {agent_name} should pick a task from the board")


# ── Keeper-Aware Agent Bridge ───────────────────────────────────────────

class KeeperAgentBridge:
    """Agent that routes all API calls through the Lighthouse Keeper.
    
    Agents never see the GitHub token. All intelligence flows through the keeper.
    """
    
    def __init__(self, keeper_url: str = "http://127.0.0.1:8900", vessel: str = ""):
        import urllib.request, json, hashlib, time
        self.keeper = keeper_url
        self.vessel = vessel or f"flux-{hashlib.md5(str(time.time()).encode()).hexdigest()[:6]}"
        self.secret = None
        self.energy = 0
        self.confidence = 0.3
    
    def _req(self, method: str, path: str, body: dict = None) -> dict:
        import urllib.request, json
        url = f"{self.keeper}{path}"
        headers = {"Content-Type": "application/json"}
        if self.secret:
            headers["X-Agent-ID"] = self.vessel
            headers["X-Agent-Secret"] = self.secret
        data = json.dumps(body).encode() if body else None
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            resp = urllib.request.urlopen(req)
            return json.loads(resp.read()) if resp.length else {}
        except Exception as e:
            return {"error": str(e)}
    
    def boot(self) -> str:
        """Register with keeper and create vessel."""
        # Register
        result = self._req("POST", "/register", {"vessel": self.vessel})
        self.secret = result.get("secret")
        if not self.secret:
            raise RuntimeError(f"Registration failed: {result}")
        
        print(f"🔐 Registered with keeper: {self.vessel}")
        
        # Create vessel repo
        self._req("POST", "/repo", {"name": self.vessel, 
                  "description": f"FLUX-native I2I agent via keeper"})
        
        # Discover fleet
        vessels = self._req("GET", "/discover").get("vessels", [])
        print(f"🔍 Discovered {len(vessels)} fleet vessels")
        
        # Read bootcamp
        bootcamp = self._req("GET", "/file/SuperInstance/oracle1-vessel/for-fleet/WELCOME-OPUS.md")
        content = bootcamp.get("decoded", "")
        print(f"📖 Read bootcamp: {len(content)} chars")
        
        # Announce via I2I
        self._req("POST", "/i2i", {
            "target": "SuperInstance/oracle1-vessel",
            "type": "DISCOVER",
            "payload": {"agent": self.vessel, "capabilities": ["keeper-aware"], "confidence": self.confidence},
            "confidence": self.confidence,
        })
        print(f"📨 Sent I2I DISCOVER to Oracle1")
        
        # Check status
        status = self._req("GET", "/status")
        self.energy = status.get("energy_remaining", 0)
        print(f"⚡ Energy: {self.energy}")
        
        print(f"\n✅ {self.vessel} ONLINE via keeper")
        return self.vessel


if __name__ == "__main__":
    import sys
    keeper_url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8900"
    bridge = KeeperAgentBridge(keeper_url)
    bridge.boot()
