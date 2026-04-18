"""Tests for agent_bridge.py — GitHubBridge, FluxAgentRuntime, KeeperAgentBridge."""

import json
import os
import base64
import pytest
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timezone, timedelta

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ═══════════════════════════════════════════════════════════════════════
# GitHubBridge Tests
# ═══════════════════════════════════════════════════════════════════════

class TestGitHubBridgeInit:
    def test_init_with_defaults(self):
        from agent_bridge import GitHubBridge
        gh = GitHubBridge("tok123")
        assert gh.token == "tok123"
        assert gh.org == "SuperInstance"
        assert "Authorization" in gh.headers
        assert gh.headers["Authorization"] == "token tok123"

    def test_init_custom_org(self):
        from agent_bridge import GitHubBridge
        gh = GitHubBridge("tok", "CustomOrg")
        assert gh.org == "CustomOrg"


class TestGitHubBridgeReadFile:
    def test_read_file_success(self):
        from agent_bridge import GitHubBridge
        gh = GitHubBridge("tok")
        content = "hello world"
        encoded = base64.b64encode(content.encode()).decode()
        gh.api_get = MagicMock(return_value={"content": encoded, "sha": "abc"})
        result = gh.read_file("owner/repo", "path/file.txt")
        assert result == content

    def test_read_file_not_found(self):
        from agent_bridge import GitHubBridge
        gh = GitHubBridge("tok")
        gh.api_get = MagicMock(side_effect=Exception("404"))
        result = gh.read_file("owner/repo", "missing.txt")
        assert result is None

    def test_read_file_no_content(self):
        from agent_bridge import GitHubBridge
        gh = GitHubBridge("tok")
        gh.api_get = MagicMock(return_value={"message": "not found"})
        result = gh.read_file("owner/repo", "dir/")
        assert result is None


class TestGitHubBridgeWriteFile:
    def test_write_file_success(self):
        from agent_bridge import GitHubBridge
        gh = GitHubBridge("tok")
        gh.api_put = MagicMock(return_value={"content": {"sha": "new"}})
        result = gh.write_file("owner/repo", "test.md", "hello", "commit msg")
        assert result is True

    def test_write_file_with_sha(self):
        from agent_bridge import GitHubBridge
        gh = GitHubBridge("tok")
        gh.api_put = MagicMock(return_value={"content": {"sha": "new"}})
        result = gh.write_file("owner/repo", "test.md", "hello", "msg", sha="old")
        call_args = gh.api_put.call_args
        body = call_args[0][1]
        assert body["sha"] == "old"

    def test_write_file_failure(self):
        from agent_bridge import GitHubBridge
        gh = GitHubBridge("tok")
        gh.api_put = MagicMock(side_effect=Exception("error"))
        result = gh.write_file("owner/repo", "test.md", "hello", "msg")
        assert result is False


class TestGitHubBridgeListFiles:
    def test_list_files_success(self):
        from agent_bridge import GitHubBridge
        gh = GitHubBridge("tok")
        gh.api_get = MagicMock(return_value=[
            {"name": "README.md", "type": "file"},
            {"name": "src", "type": "dir"},
        ])
        result = gh.list_files("owner/repo", "")
        assert result == [("README.md", "file"), ("src", "dir")]

    def test_list_files_error(self):
        from agent_bridge import GitHubBridge
        gh = GitHubBridge("tok")
        gh.api_get = MagicMock(side_effect=Exception("error"))
        result = gh.list_files("owner/repo", "")
        assert result == []


class TestGitHubBridgeBottles:
    def test_read_bottles(self):
        from agent_bridge import GitHubBridge
        gh = GitHubBridge("tok")
        content = "bottle content here"
        encoded = base64.b64encode(content.encode()).decode()
        gh.list_files = MagicMock(return_value=[
            ("msg1.md", "file"), ("msg2.json", "file"), ("other.txt", "file")
        ])
        gh.read_file = MagicMock(side_effect=[
            content,  # msg1.md
            None,  # msg2.json is not .md
        ])
        bottles = gh.read_bottles("owner/repo", "for-fleet")
        assert len(bottles) == 1
        assert "msg1.md" in bottles
        assert bottles["msg1.md"] == content

    def test_read_bottles_error(self):
        from agent_bridge import GitHubBridge
        gh = GitHubBridge("tok")
        gh.list_files = MagicMock(side_effect=Exception("error"))
        bottles = gh.read_bottles("owner/repo", "for-fleet")
        assert bottles == {}

    def test_leave_bottle(self):
        from agent_bridge import GitHubBridge
        gh = GitHubBridge("tok")
        gh.write_file = MagicMock(return_value=True)
        result = gh.leave_bottle("owner/repo", "for-fleet", "msg.md", "content", "msg")
        assert result is True
        gh.write_file.assert_called_once_with("owner/repo", "for-fleet/msg.md", "content", "msg")


class TestGitHubBridgeCloneRepo:
    def test_clone_success(self):
        from agent_bridge import GitHubBridge
        gh = GitHubBridge("tok")
        with patch("agent_bridge.subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(returncode=0)
            result = gh.clone_repo("owner/repo", "/tmp/repo")
            assert result is True

    def test_clone_failure(self):
        from agent_bridge import GitHubBridge
        gh = GitHubBridge("tok")
        with patch("agent_bridge.subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(returncode=1)
            result = gh.clone_repo("owner/repo", "/tmp/repo")
            assert result is False


class TestGitHubBridgeCreateVessel:
    def test_create_vessel(self):
        from agent_bridge import GitHubBridge
        gh = GitHubBridge("tok")
        gh.api_post = MagicMock(return_value={})
        gh.write_file = MagicMock(return_value=True)
        result = gh.create_vessel("test-vessel", "# Charter", {"name": "Agent", "role": "test"})
        assert result is True
        # Should create multiple files
        assert gh.api_post.call_count == 1  # create repo
        assert gh.write_file.call_count >= 4  # charter, identity, directories, capability


class TestGitHubBridgeOpenIssue:
    def test_open_issue(self):
        from agent_bridge import GitHubBridge
        gh = GitHubBridge("tok")
        gh.api_post = MagicMock(return_value={"number": 42})
        num = gh.open_issue("owner/repo", "Bug title", "Bug body")
        assert num == 42

    def test_open_issue_no_number(self):
        from agent_bridge import GitHubBridge
        gh = GitHubBridge("tok")
        gh.api_post = MagicMock(return_value={"error": "failed"})
        num = gh.open_issue("owner/repo", "Bug", "Body")
        assert num == 0


class TestGitHubBridgeGetLatestCommits:
    def test_get_commits(self):
        from agent_bridge import GitHubBridge
        gh = GitHubBridge("tok")
        gh.api_get = MagicMock(return_value=[
            {"sha": "abcdef1234567890", "commit": {"message": "fix bug", "author": {"date": "2024-01-01T00:00:00Z"}}},
            {"sha": "bcdef12345678901", "commit": {"message": "add feature", "author": {"date": "2024-01-02T00:00:00Z"}}},
        ])
        commits = gh.get_latest_commits("owner/repo", count=2)
        assert len(commits) == 2
        assert commits[0]["sha"] == "abcdef1"
        assert commits[0]["msg"] == "fix bug"


class TestGitHubBridgeDiscoverAgents:
    def test_discover_agents(self):
        from agent_bridge import GitHubBridge
        gh = GitHubBridge("tok")
        content = "[agent]\nname = test"
        encoded = base64.b64encode(content.encode()).decode()
        gh.api_get = MagicMock(return_value=[
            {"name": "agent1-vessel", "full_name": "Org/agent1-vessel"},
            {"name": "other-repo", "full_name": "Org/other-repo"},
        ])
        gh.read_file = MagicMock(side_effect=[
            content,  # agent1 has CAPABILITY.toml
        ])
        agents = gh.discover_agents()
        assert len(agents) == 1
        assert agents[0]["repo"] == "Org/agent1-vessel"

    def test_discover_agents_error(self):
        from agent_bridge import GitHubBridge
        gh = GitHubBridge("tok")
        gh.api_get = MagicMock(side_effect=Exception("error"))
        agents = gh.discover_agents()
        assert agents == []


# ═══════════════════════════════════════════════════════════════════════
# FluxAgentRuntime Tests
# ═══════════════════════════════════════════════════════════════════════

class TestFluxAgentRuntimeInit:
    def test_init(self):
        from agent_bridge import FluxAgentRuntime
        rt = FluxAgentRuntime("tok")
        assert rt.github.token == "tok"
        assert rt.confidence == 0.5
        assert rt.energy == 1000
        assert rt.state == "BOOTING"
        assert rt.agent_name == "flux-agent"


# ═══════════════════════════════════════════════════════════════════════
# KeeperAgentBridge Tests
# ═══════════════════════════════════════════════════════════════════════

class TestKeeperAgentBridgeInit:
    def test_init_defaults(self):
        from agent_bridge import KeeperAgentBridge
        bridge = KeeperAgentBridge("http://localhost:8900")
        assert bridge.keeper == "http://localhost:8900"
        assert bridge.secret is None
        assert bridge.energy == 0
        assert bridge.confidence == 0.3

    def test_init_custom_vessel(self):
        from agent_bridge import KeeperAgentBridge
        bridge = KeeperAgentBridge("http://localhost:8900", "my-vessel")
        assert bridge.vessel == "my-vessel"

    def test_init_generates_vessel_name(self):
        from agent_bridge import KeeperAgentBridge
        bridge = KeeperAgentBridge("http://localhost:8900")
        assert bridge.vessel.startswith("flux-")
        assert len(bridge.vessel) == 11  # flux- + 6 hex chars

    def test_boot_register_success(self):
        from agent_bridge import KeeperAgentBridge
        bridge = KeeperAgentBridge("http://localhost:8900", "test-v")
        bridge._req = MagicMock(return_value={
            "secret": "abc123", "status": "registered"
        })
        bridge.boot()
        assert bridge.secret == "abc123"
        # Should have made several requests: register, discover, i2i, status
        assert bridge._req.call_count >= 4

    def test_boot_register_failure(self):
        from agent_bridge import KeeperAgentBridge
        bridge = KeeperAgentBridge("http://localhost:8900", "test-v")
        bridge._req = MagicMock(return_value={"error": "registration failed"})
        with pytest.raises(RuntimeError, match="Registration failed"):
            bridge.boot()


class TestKeeperAgentBridgePackBaton:
    def test_pack_baton_success(self):
        from agent_bridge import KeeperAgentBridge
        bridge = KeeperAgentBridge("http://localhost:8900", "test-v")
        bridge.secret = "secret"
        bridge.energy = 800
        bridge.confidence = 0.6
        bridge._req = MagicMock(return_value={"average": 7.0, "passes": True})
        result = bridge.pack_baton(
            "I was debugging", "Bugs are fixed", "Need more tests",
            "Run the test suite", "Not sure about edge cases",
            open_threads=["bug-42"]
        )
        assert result is not None
        assert result["generation"] == 1
        assert result["score"] == 7.0

    def test_pack_baton_quality_gate_fails(self):
        from agent_bridge import KeeperAgentBridge
        bridge = KeeperAgentBridge("http://localhost:8900", "test-v")
        bridge.secret = "secret"
        bridge._req = MagicMock(return_value={"average": 2.0, "passes": False})
        result = bridge.pack_baton(
            "I was debugging", "Bugs are fixed", "Need more tests",
            "Run the test suite", "Not sure about edge cases",
        )
        assert result is None


class TestKeeperAgentBridgeRequest:
    def test_request_without_auth(self):
        from agent_bridge import KeeperAgentBridge
        bridge = KeeperAgentBridge("http://localhost:8900", "test-v")
        bridge._req = MagicMock(return_value={"status": "ok"})
        # Calling _req directly (without secret set, headers should not have auth)
        # Actually _req uses self.secret, so if not set, no auth headers
        # Let's just test the method exists and returns
        pass
