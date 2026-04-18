"""Tests for i2i_agent_bridge.py — I2IAgentBridge."""

import json
import os
import base64
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ═══════════════════════════════════════════════════════════════════════
# I2IAgentBridge Tests
# ═══════════════════════════════════════════════════════════════════════

class TestI2IAgentBridgeInit:
    def test_init_defaults(self):
        from i2i_agent_bridge import I2IAgentBridge
        agent = I2IAgentBridge("tok")
        assert agent.token == "tok"
        assert agent.org == "SuperInstance"
        assert agent.confidence == 0.3
        assert agent.energy == 1000
        assert agent.agent_name is None
        assert agent.vessel_repo is None
        assert agent.tasks_completed == 0
        assert agent.improvements_made == 0

    def test_init_custom_org(self):
        from i2i_agent_bridge import I2IAgentBridge
        agent = I2IAgentBridge("tok", "CustomOrg")
        assert agent.org == "CustomOrg"


class TestI2IAgentBridgeAPI:
    def test_api_get_success(self):
        from i2i_agent_bridge import I2IAgentBridge
        agent = I2IAgentBridge("tok")
        with patch("i2i_agent_bridge.urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({"key": "value"}).encode()
            mock_urlopen.return_value = mock_resp
            result = agent._api("GET", "/repos/test/repo")
            assert result == {"key": "value"}

    def test_api_get_failure(self):
        from i2i_agent_bridge import I2IAgentBridge
        agent = I2IAgentBridge("tok")
        with patch("i2i_agent_bridge.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = Exception("network error")
            result = agent._api("GET", "/repos/test/repo")
            assert "error" in result

    def test_read_file_success(self):
        from i2i_agent_bridge import I2IAgentBridge
        agent = I2IAgentBridge("tok")
        content = "file content"
        encoded = base64.b64encode(content.encode()).decode()
        agent._api = MagicMock(return_value={"content": encoded})
        result = agent._read_file("owner/repo", "test.txt")
        assert result == content

    def test_read_file_error(self):
        from i2i_agent_bridge import I2IAgentBridge
        agent = I2IAgentBridge("tok")
        agent._api = MagicMock(side_effect=Exception("error"))
        result = agent._read_file("owner/repo", "missing.txt")
        assert result is None

    def test_write_file_success(self):
        from i2i_agent_bridge import I2IAgentBridge
        agent = I2IAgentBridge("tok")
        agent._api = MagicMock(side_effect=[
            {"sha": "old"},  # GET returns sha
            {"content": {"sha": "new"}},  # PUT succeeds
        ])
        result = agent._write_file("owner/repo", "test.md", "hello", "msg")
        assert result is True

    def test_write_file_new_file(self):
        from i2i_agent_bridge import I2IAgentBridge
        agent = I2IAgentBridge("tok")
        agent._api = MagicMock(side_effect=[
            {"error": "not found"},  # GET fails (no existing file)
            {"content": {"sha": "new"}},  # PUT succeeds
        ])
        result = agent._write_file("owner/repo", "new.md", "hello", "msg")
        assert result is True

    def test_list_dir_success(self):
        from i2i_agent_bridge import I2IAgentBridge
        agent = I2IAgentBridge("tok")
        agent._api = MagicMock(return_value=[
            {"name": "file1.py", "type": "file"},
            {"name": "dir1", "type": "dir"},
        ])
        result = agent._list_dir("owner/repo", "src")
        assert result == [("file1.py", "file"), ("dir1", "dir")]

    def test_list_dir_error(self):
        from i2i_agent_bridge import I2IAgentBridge
        agent = I2IAgentBridge("tok")
        agent._api = MagicMock(side_effect=Exception("error"))
        result = agent._list_dir("owner/repo", "src")
        assert result == []


class TestI2IProtocol:
    def test_send_valid_message_type(self):
        from i2i_agent_bridge import I2IAgentBridge
        agent = I2IAgentBridge("tok")
        agent.vessel_repo = "Org/test-vessel"
        agent._write_file = MagicMock(return_value=True)
        result = agent.i2i_send("Org/target-vessel", "DISCOVER", {"info": "hello"})
        assert result is True
        # Check the file was written
        call_args = agent._write_file.call_args
        assert "i2i-discover-" in call_args[0][1]

    def test_send_invalid_message_type(self):
        from i2i_agent_bridge import I2IAgentBridge
        agent = I2IAgentBridge("tok")
        result = agent.i2i_send("Org/target", "INVALID_TYPE", {})
        assert result is False

    def test_send_oracle1_goes_to_for_oracle1(self):
        from i2i_agent_bridge import I2IAgentBridge
        agent = I2IAgentBridge("tok")
        agent.vessel_repo = "Org/test-vessel"
        agent._write_file = MagicMock(return_value=True)
        agent.i2i_send("Org/oracle1-vessel", "DISCOVER", {})
        call_args = agent._write_file.call_args
        assert "for-oracle1/" in call_args[0][1]

    def test_send_regular_goes_to_for_fleet(self):
        from i2i_agent_bridge import I2IAgentBridge
        agent = I2IAgentBridge("tok")
        agent.vessel_repo = "Org/test-vessel"
        agent._write_file = MagicMock(return_value=True)
        agent.i2i_send("Org/other-vessel", "DISCOVER", {})
        call_args = agent._write_file.call_args
        assert "for-fleet/" in call_args[0][1]

    def test_send_envelope_format(self):
        from i2i_agent_bridge import I2IAgentBridge
        agent = I2IAgentBridge("tok")
        agent.vessel_repo = "Org/test-vessel"
        agent.confidence = 0.8
        captured_content = None
        def capture_write(*args, **kwargs):
            nonlocal captured_content
            captured_content = args[2]
            return True
        agent._write_file = MagicMock(side_effect=capture_write)
        agent.i2i_send("Org/target", "IMPROVE", {"action": "fix bug"})
        envelope = json.loads(captured_content)
        assert envelope["protocol"] == "I2I-v2"
        assert envelope["type"] == "IMPROVE"
        assert envelope["from"] == "Org/test-vessel"
        assert envelope["payload"] == {"action": "fix bug"}
        assert envelope["confidence"] == 0.8

    def test_i2i_read(self):
        from i2i_agent_bridge import I2IAgentBridge
        agent = I2IAgentBridge("tok")
        agent.vessel_repo = "Org/test-vessel"

        msg1 = json.dumps({"protocol": "I2I-v2", "type": "DISCOVER", "from": "Org/sender"})
        msg2 = json.dumps({"protocol": "I2I-v2", "type": "ANNOUNCE", "from": "Org/sender2"})

        agent._list_dir = MagicMock(return_value=[
            ("i2i-discover-1234.json", "file"),
            ("i2i-announce-5678.json", "file"),
            ("other-file.md", "file"),
        ])
        agent._read_file = MagicMock(side_effect=[msg1, msg2])
        messages = agent.i2i_read("for-fleet")
        assert len(messages) == 2
        assert messages[0]["type"] == "DISCOVER"
        assert messages[1]["type"] == "ANNOUNCE"

    def test_all_valid_message_types(self):
        from i2i_agent_bridge import I2IAgentBridge
        agent = I2IAgentBridge("tok")
        valid = [
            "DISCOVER", "ANNOUNCE", "TASK_OFFER", "TASK_ACCEPT", "TASK_COMPLETE",
            "TASK_REJECT", "BOTTLE", "WITNESS", "IMPROVE", "REVIEW",
            "CAPABILITY_UPDATE", "ENERGY_REPORT", "CONFIDENCE_VOTE", "SYNCHRONIZE",
            "REQUEST_HELP", "OFFER_HELP", "CRITIQUE", "PRAISE", "EVOLVE", "FORWARD"
        ]
        for msg_type in valid:
            agent.vessel_repo = "Org/test"
            agent._write_file = MagicMock(return_value=True)
            result = agent.i2i_send("Org/target", msg_type, {})
            assert result is True, f"Failed for type {msg_type}"


class TestTaskExecution:
    def test_scan_for_tasks_from_taskboard(self):
        from i2i_agent_bridge import I2IAgentBridge
        agent = I2IAgentBridge("tok")
        agent.vessel_repo = "Org/test-vessel"
        taskboard = "# Task Board\n- 🔴 Fix critical bug\n- 🟠 Add tests\n- ✅ Done task"
        agent._read_file = MagicMock(return_value=taskboard)
        agent._list_dir = MagicMock(return_value=[])
        agent._api = MagicMock(return_value=[])  # no issues
        tasks = agent.scan_for_tasks()
        # Should find 2 high-priority tasks (🔴 and 🟠)
        task_lines = [t for t in tasks if "taskboard" in t.get("source", "")]
        assert len(task_lines) == 2

    def test_execute_task_issue(self):
        from i2i_agent_bridge import I2IAgentBridge
        agent = I2IAgentBridge("tok")
        initial_confidence = agent.confidence
        result = agent.execute_task({
            "source": "issue #42",
            "title": "Bug fix needed",
            "body": "Something is broken"
        })
        assert result["status"] == "analyzed"
        assert agent.confidence > initial_confidence
        assert agent.energy == 950  # -50 per task

    def test_execute_task_taskboard(self):
        from i2i_agent_bridge import I2IAgentBridge
        agent = I2IAgentBridge("tok")
        result = agent.execute_task({
            "source": "oracle1-taskboard",
            "line": "🔴 Fix bug in flux-runtime"
        })
        assert result["status"] == "identified"

    def test_execute_task_bottle(self):
        from i2i_agent_bridge import I2IAgentBridge
        agent = I2IAgentBridge("tok")
        result = agent.execute_task({
            "source": "bottle:priority-task.md",
            "content": "High priority task content"
        })
        assert result["status"] == "read"


class TestAnalyzeRepo:
    def test_missing_readme(self):
        from i2i_agent_bridge import I2IAgentBridge
        agent = I2IAgentBridge("tok")
        agent._list_dir = MagicMock(return_value=[
            ("CHARTER.md", "file"),
        ])
        agent._read_file = MagicMock(return_value=None)
        agent._api = MagicMock(return_value={"description": "Test repo"})
        analysis = agent.analyze_repo("Org/test-vessel")
        assert "Missing README.md" in analysis["issues_found"]
        assert "Missing CAPABILITY.toml" in analysis["issues_found"]
        assert "Missing BOOTCAMP.md" in analysis["issues_found"]

    def test_good_readme(self):
        from i2i_agent_bridge import I2IAgentBridge
        agent = I2IAgentBridge("tok")
        agent._list_dir = MagicMock(return_value=[("README.md", "file")])
        agent._read_file = MagicMock(return_value="A" * 100)  # > 50 chars
        analysis = agent.analyze_repo("Org/test-repo")
        assert not any("README" in i for i in analysis["issues_found"])

    def test_short_readme(self):
        from i2i_agent_bridge import I2IAgentBridge
        agent = I2IAgentBridge("tok")
        agent._list_dir = MagicMock(return_value=[("README.md", "file")])
        agent._read_file = MagicMock(return_value="Short")
        analysis = agent.analyze_repo("Org/test-repo")
        assert "README too short" in analysis["issues_found"]

    def test_no_issues(self):
        from i2i_agent_bridge import I2IAgentBridge
        agent = I2IAgentBridge("tok")
        agent._list_dir = MagicMock(return_value=[
            ("README.md", "file"),
            ("CAPABILITY.toml", "file"),
        ])
        agent._read_file = MagicMock(return_value="A" * 100)
        analysis = agent.analyze_repo("Org/test-repo")  # not a vessel name
        assert analysis["issues_found"] == []


class TestImproveFleetRepo:
    def test_improve_adds_readme(self):
        from i2i_agent_bridge import I2IAgentBridge
        agent = I2IAgentBridge("tok")
        agent._list_dir = MagicMock(return_value=[])  # no files
        agent._read_file = MagicMock(return_value=None)
        agent._api = MagicMock(return_value={"description": "Test vessel repo"})
        agent._write_file = MagicMock(return_value=True)
        agent.i2i_send = MagicMock(return_value=True)
        agent.log_diary = MagicMock()
        result = agent.improve_fleet_repo("Org/test-vessel")
        assert result is True
        assert agent.improvements_made == 1
        # Should write README
        write_calls = [c for c in agent._write_file.call_args_list if c[0][1] == "README.md"]
        assert len(write_calls) == 1

    def test_improve_adds_capability_toml(self):
        from i2i_agent_bridge import I2IAgentBridge
        agent = I2IAgentBridge("tok")
        agent._list_dir = MagicMock(return_value=[("README.md", "file")])
        agent._read_file = MagicMock(return_value="A" * 100)
        agent._write_file = MagicMock(return_value=True)
        agent.log_diary = MagicMock()
        result = agent.improve_fleet_repo("Org/test-vessel")
        assert result is True
        assert agent.improvements_made == 1
        write_calls = [c for c in agent._write_file.call_args_list if c[0][1] == "CAPABILITY.toml"]
        assert len(write_calls) == 1

    def test_improve_no_issues(self):
        from i2i_agent_bridge import I2IAgentBridge
        agent = I2IAgentBridge("tok")
        agent._list_dir = MagicMock(return_value=[
            ("README.md", "file"), ("CAPABILITY.toml", "file"), ("BOOTCAMP.md", "file")
        ])
        agent._read_file = MagicMock(return_value="A" * 100)
        result = agent.improve_fleet_repo("Org/test-vessel")
        assert result is False


class TestLogDiary:
    def test_log_diary(self):
        from i2i_agent_bridge import I2IAgentBridge
        agent = I2IAgentBridge("tok")
        agent.vessel_repo = "Org/test-vessel"
        agent._read_file = MagicMock(return_value="")
        agent._write_file = MagicMock(return_value=True)
        agent.log_diary("TEST", "something happened")
        assert len(agent.diary) == 1
        assert "TEST" in agent.diary[0]
        agent._write_file.assert_called_once()


class TestReportStatus:
    def test_report_status(self):
        from i2i_agent_bridge import I2IAgentBridge
        agent = I2IAgentBridge("tok")
        agent.vessel_repo = "Org/test-vessel"
        agent.tasks_completed = 5
        agent.improvements_made = 2
        agent._write_file = MagicMock(return_value=True)

        captured = None
        def capture(*args, **kwargs):
            nonlocal captured
            captured = args[2]
            return True
        agent._write_file = MagicMock(side_effect=capture)
        agent.report_status()

        report = json.loads(captured)
        assert report["agent"] is None  # no name set
        assert report["confidence"] == 0.3
        assert report["tasks_completed"] == 5
        assert report["improvements_made"] == 2


class TestBoot:
    def test_boot_sets_name_and_vessel(self):
        from i2i_agent_bridge import I2IAgentBridge
        agent = I2IAgentBridge("tok")
        agent._api = MagicMock(return_value={})  # create repo
        agent._write_file = MagicMock(return_value=True)
        agent._read_file = MagicMock(return_value=None)
        agent.i2i_send = MagicMock(return_value=True)

        with patch("i2i_agent_bridge.hashlib") as mock_hash:
            mock_hash.md5.return_value.hexdigest.return_value = "abc123"
            name = agent.boot("")

        assert name == "flux-abc123"
        assert agent.agent_name == "flux-abc123"
        assert agent.vessel_repo == "SuperInstance/flux-abc123"
        assert len(agent.diary) > 0


class TestEnergyAndConfidence:
    def test_energy_decreases_per_task(self):
        from i2i_agent_bridge import I2IAgentBridge
        agent = I2IAgentBridge("tok")
        initial = agent.energy
        agent.execute_task({"source": "issue #1", "title": "test", "body": "body"})
        assert agent.energy == initial - 50

    def test_confidence_increases_on_task(self):
        from i2i_agent_bridge import I2IAgentBridge
        agent = I2IAgentBridge("tok")
        initial = agent.confidence
        agent.execute_task({"source": "issue #1", "title": "test", "body": "body"})
        assert agent.confidence > initial

    def test_confidence_capped_at_1(self):
        from i2i_agent_bridge import I2IAgentBridge
        agent = I2IAgentBridge("tok")
        agent.confidence = 0.99
        agent.execute_task({"source": "issue #1", "title": "test", "body": "body"})
        assert agent.confidence <= 1.0
