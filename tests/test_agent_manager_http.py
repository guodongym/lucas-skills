from __future__ import annotations

import http.client
import io
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from tests.test_agent_manager import write_skill
from tools.agent_manager.cli import main
from tools.agent_manager.instructions import (
    InstructionBatchResult,
    InstructionPlanError,
    InstructionResult,
)
from tools.agent_manager.server import create_server


@contextmanager
def running_http_server(
    repo: Path,
    home: Path,
    applications: Path,
    which=lambda _: None,
):
    server = create_server(repo, home, "test-token", applications, which)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield server, thread, f"http://{host}:{port}"
    finally:
        thread.join(timeout=0.05)
        if thread.is_alive():
            server.shutdown()
        server.server_close()
        thread.join(timeout=2)


class HttpServerTests(unittest.TestCase):
    @staticmethod
    def _write_request(base_url: str, path: str, payload: object):
        body = json.dumps(payload).encode()
        request = urllib.request.Request(
            f"{base_url}{path}",
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Origin": base_url,
                "X-Agent-Manager-Token": "test-token",
            },
        )
        return urllib.request.urlopen(request, timeout=2)

    @staticmethod
    def _error_payload(error: urllib.error.HTTPError) -> dict[str, object]:
        return json.loads(error.read())

    def test_binds_loopback_and_read_apis_recover_from_filesystem(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            skill = write_skill(repo, "docx", "docx")
            target = home / ".claude/skills/docx"
            target.parent.mkdir(parents=True)
            target.symlink_to(skill)

            def read_status() -> dict[str, object]:
                with running_http_server(
                    repo,
                    home,
                    root / "Applications",
                    lambda command: "/bin/claude" if command == "claude" else None,
                ) as (server, _thread, base_url):
                    self.assertEqual(server.server_address[0], "127.0.0.1")
                    response = urllib.request.urlopen(f"{base_url}/api/status", timeout=2)
                    self.assertEqual(response.headers["Cache-Control"], "no-store")
                    self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
                    self.assertNotIn("Access-Control-Allow-Origin", response.headers)
                    return json.loads(response.read())

            first = read_status()
            second = read_status()
            self.assertEqual(
                set(first),
                {
                    "mode", "ok", "code", "message", "repo_root", "skills",
                    "instructions", "surfaces", "summary", "scanned_at",
                },
            )
            self.assertEqual(first["skills"]["targets"], second["skills"]["targets"])
            self.assertTrue(target.is_symlink())

            with running_http_server(repo, home, root / "Applications") as (
                _server,
                _thread,
                base_url,
            ):
                inventory = json.loads(
                    urllib.request.urlopen(f"{base_url}/api/inventory", timeout=2).read()
                )
                self.assertTrue(inventory["ok"])
                self.assertIn("inventory", inventory)
                self.assertTrue(target.is_symlink())

    def test_write_requires_exact_host_origin_and_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            with running_http_server(
                repo,
                home,
                root / "Applications",
                lambda command: "/bin/claude" if command == "claude" else None,
            ) as (server, _thread, base_url):
                body = json.dumps(
                    {
                        "skill": "docx",
                        "all": False,
                        "tool": "claude",
                        "on": True,
                        "apply": True,
                    }
                ).encode()
                missing = urllib.request.Request(
                    f"{base_url}/api/skills/set",
                    data=body,
                    method="POST",
                    headers={"Content-Type": "application/json"},
                )
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    urllib.request.urlopen(missing, timeout=2)
                self.assertEqual(caught.exception.code, 403)
                self.assertEqual(self._error_payload(caught.exception)["code"], "invalid-token")

                wrong_origin = urllib.request.Request(
                    f"{base_url}/api/skills/set",
                    data=body,
                    method="POST",
                    headers={
                        "Content-Type": "application/json",
                        "Origin": "http://127.0.0.1:1",
                        "X-Agent-Manager-Token": "test-token",
                    },
                )
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    urllib.request.urlopen(wrong_origin, timeout=2)
                self.assertEqual(caught.exception.code, 403)

                host, port = server.server_address
                connection = http.client.HTTPConnection(host, port, timeout=2)
                connection.putrequest("GET", "/api/status", skip_host=True)
                connection.putheader("Host", "localhost:9999")
                connection.endheaders()
                response = connection.getresponse()
                self.assertEqual(response.status, 403)
                self.assertEqual(json.loads(response.read())["code"], "invalid-host")
                connection.close()

                connection = http.client.HTTPConnection(host, port, timeout=2)
                connection.putrequest("POST", "/api/skills/set")
                connection.putheader("Content-Type", "application/json")
                connection.putheader("Content-Length", str(len(body)))
                connection.putheader("Origin", base_url)
                connection.putheader("Origin", base_url)
                connection.putheader("X-Agent-Manager-Token", "test-token")
                connection.putheader("X-Agent-Manager-Token", "test-token")
                connection.endheaders(body)
                response = connection.getresponse()
                self.assertEqual(response.status, 403)
                response.read()
                connection.close()

                response = self._write_request(base_url, "/api/skills/set", json.loads(body))
                self.assertTrue(json.loads(response.read())["ok"])
                self.assertEqual(
                    (home / ".claude/skills/docx").resolve(),
                    (repo / "skills/docx").resolve(),
                )

    def test_rejects_invalid_content_type_body_shape_and_size(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            with running_http_server(repo, home, root / "Applications") as (
                server,
                _thread,
                base_url,
            ):
                common = {
                    "Origin": base_url,
                    "X-Agent-Manager-Token": "test-token",
                }
                request = urllib.request.Request(
                    f"{base_url}/api/skills/set",
                    data=b"{}",
                    method="POST",
                    headers={**common, "Content-Type": "text/plain"},
                )
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    urllib.request.urlopen(request, timeout=2)
                self.assertEqual(caught.exception.code, 415)

                for payload in ([], {"apply": True, "unexpected": True}):
                    with self.subTest(payload=payload):
                        with self.assertRaises(urllib.error.HTTPError) as caught:
                            self._write_request(base_url, "/api/skills/adopt", payload)
                        self.assertEqual(caught.exception.code, 400)
                        self.assertEqual(
                            self._error_payload(caught.exception)["code"],
                            "invalid-request",
                        )

                oversized = urllib.request.Request(
                    f"{base_url}/api/skills/set",
                    data=b" " * (64 * 1024 + 1),
                    method="POST",
                    headers={**common, "Content-Type": "application/json"},
                )
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    urllib.request.urlopen(oversized, timeout=2)
                self.assertEqual(caught.exception.code, 413)

                duplicate_body = b'{"apply":false,"apply":true}'
                duplicate = urllib.request.Request(
                    f"{base_url}/api/skills/adopt",
                    data=duplicate_body,
                    method="POST",
                    headers={**common, "Content-Type": "application/json"},
                )
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    urllib.request.urlopen(duplicate, timeout=2)
                self.assertEqual(caught.exception.code, 400)

                host, port = server.server_address
                connection = http.client.HTTPConnection(host, port, timeout=2)
                connection.putrequest("POST", "/api/skills/adopt")
                connection.putheader("Content-Type", "application/json")
                connection.putheader("Origin", base_url)
                connection.putheader("X-Agent-Manager-Token", "test-token")
                connection.endheaders()
                response = connection.getresponse()
                self.assertEqual(response.status, 411)
                response.read()
                connection.close()

            self.assertFalse((home / ".local/state/lucas-skills-manager").exists())

    def test_each_write_route_rejects_non_exact_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            with running_http_server(repo, home, root / "Applications") as (
                _server,
                _thread,
                base_url,
            ):
                cases = (
                    (
                        "/api/skills/set",
                        {"skill": "docx", "all": False, "tool": "codex", "on": True},
                    ),
                    (
                        "/api/skills/set",
                        {
                            "skill": "docx", "all": False, "tool": "codex",
                            "on": True, "apply": False, "expected_fingerprint": None,
                        },
                    ),
                    (
                        "/api/skills/set",
                        {"skill": "docx", "all": False, "tool": "codex", "on": 1, "apply": False},
                    ),
                    (
                        "/api/skills/set",
                        {
                            "skill": "docx", "all": False, "tool": "codex",
                            "on": True, "apply": False, "unknown": 1,
                        },
                    ),
                    ("/api/skills/adopt", {}),
                    ("/api/skills/adopt", {"apply": False, "all": True}),
                    ("/api/skills/adopt", {"apply": 0}),
                    ("/api/skills/adopt", {"apply": False, "unknown": 1}),
                    ("/api/instructions/set", {"target": "codex", "on": True, "apply": False}),
                    (
                        "/api/instructions/set",
                        {
                            "target": "codex", "on": True, "apply": False,
                            "expected_fingerprint": None, "replace_existing": False,
                        },
                    ),
                    (
                        "/api/instructions/set",
                        {"target": "codex", "on": 1, "apply": False, "expected_fingerprint": None},
                    ),
                    (
                        "/api/instructions/set",
                        {
                            "target": "codex", "on": True, "apply": False,
                            "expected_fingerprint": None, "unknown": 1,
                        },
                    ),
                    ("/api/instructions/adopt", {"apply": False, "replace_existing": False}),
                    (
                        "/api/instructions/adopt",
                        {
                            "apply": False, "replace_existing": False,
                            "expected_fingerprint": None, "target": "codex",
                        },
                    ),
                    (
                        "/api/instructions/adopt",
                        {"apply": False, "replace_existing": 0, "expected_fingerprint": None},
                    ),
                    (
                        "/api/instructions/adopt",
                        {
                            "apply": False, "replace_existing": False,
                            "expected_fingerprint": None, "unknown": 1,
                        },
                    ),
                )
                for path, payload in cases:
                    with self.subTest(path=path, payload=payload), self.assertRaises(
                        urllib.error.HTTPError
                    ) as caught:
                        self._write_request(base_url, path, payload)
                    self.assertEqual(caught.exception.code, 400)
                    self.assertEqual(
                        self._error_payload(caught.exception)["code"],
                        "invalid-request",
                    )

                for payload in ({"apply": False}, {"unknown": 1}):
                    with self.subTest(path="/api/shutdown", payload=payload), self.assertRaises(
                        urllib.error.HTTPError
                    ) as caught:
                        self._write_request(base_url, "/api/shutdown", payload)
                    self.assertEqual(caught.exception.code, 400)
                    self.assertEqual(self._error_payload(caught.exception)["code"], "invalid-request")

    def test_rejects_path_traversal_and_unsupported_routes_or_methods(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            web_root = repo / "tools/agent_manager/web"
            web_root.mkdir(parents=True)
            (web_root / "index.html").write_text(
                "<script>const token = __AGENT_MANAGER_TOKEN__;</script>",
                encoding="utf-8",
            )
            with running_http_server(repo, home, root / "Applications") as (
                server,
                _thread,
                base_url,
            ):
                index = urllib.request.urlopen(f"{base_url}/", timeout=2).read().decode()
                self.assertIn('const token = "test-token";', index)

                for path in ("/index.html", "/../cli.py", "/api/unknown"):
                    with self.subTest(path=path), self.assertRaises(
                        urllib.error.HTTPError
                    ) as caught:
                        urllib.request.urlopen(f"{base_url}{path}", timeout=2)
                    self.assertEqual(caught.exception.code, 404)

                outside = root / "outside.html"
                outside.write_text("sensitive", encoding="utf-8")
                (web_root / "index.html").unlink()
                (web_root / "index.html").symlink_to(outside)
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    urllib.request.urlopen(f"{base_url}/", timeout=2)
                self.assertEqual(caught.exception.code, 404)
                self.assertNotIn(b"sensitive", caught.exception.read())

                host, port = server.server_address
                methods = (
                    ("GET", "/api/skills/set"),
                    ("POST", "/api/status"),
                    ("PUT", "/api/skills/set"),
                )
                for method, path in methods:
                    with self.subTest(method=method, path=path):
                        connection = http.client.HTTPConnection(host, port, timeout=2)
                        connection.request(method, path)
                        response = connection.getresponse()
                        self.assertEqual(response.status, 405)
                        self.assertIn("Allow", response.headers)
                        response.read()
                        connection.close()

    def test_rejects_symlinked_web_root_without_reading_external_index(self) -> None:
        for symlinked_component in ("tools", "agent_manager", "web"):
            with self.subTest(symlinked_component=symlinked_component):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp).resolve()
                    repo, home = root / "repo", root / "home"
                    write_skill(repo, "docx", "docx")
                    external = root / f"external-{symlinked_component}"

                    if symlinked_component == "tools":
                        (external / "agent_manager/web").mkdir(parents=True)
                        (external / "agent_manager/web/index.html").write_text(
                            "sensitive-external-file",
                            encoding="utf-8",
                        )
                        (repo / "tools").symlink_to(external)
                    elif symlinked_component == "web":
                        external.mkdir()
                        (external / "index.html").write_text(
                            "sensitive-external-file",
                            encoding="utf-8",
                        )
                        (repo / "tools/agent_manager").mkdir(parents=True)
                        (repo / "tools/agent_manager/web").symlink_to(external)
                    else:
                        (external / "web").mkdir(parents=True)
                        (external / "web/index.html").write_text(
                            "sensitive-external-file",
                            encoding="utf-8",
                        )
                        (repo / "tools").mkdir()
                        (repo / "tools/agent_manager").symlink_to(external)

                    with running_http_server(
                        repo,
                        home,
                        root / "Applications",
                    ) as (_server, _thread, base_url):
                        with self.assertRaises(urllib.error.HTTPError) as caught:
                            urllib.request.urlopen(f"{base_url}/", timeout=2)

                        self.assertIn(caught.exception.code, {403, 404})
                        body = caught.exception.read().decode()
                        self.assertEqual(
                            caught.exception.headers.get_content_type(),
                            "application/json",
                        )
                        self.assertNotIn("sensitive-external-file", body)

    def test_manifest_owner_conflict_is_409_but_invalid_manifest_is_500(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            manifest = home / ".gemini/antigravity-cli/plugins/lucas-skills/plugin.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text('{"name":"other-owner"}\n', encoding="utf-8")

            with running_http_server(
                repo,
                home,
                root / "Applications",
                lambda command: "/bin/agy" if command == "agy" else None,
            ) as (_server, _thread, base_url):
                request = {
                    "skill": "docx",
                    "all": False,
                    "tool": "antigravity",
                    "on": True,
                    "apply": True,
                }
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    self._write_request(base_url, "/api/skills/set", request)
                self.assertEqual(caught.exception.code, 409)
                self.assertEqual(
                    self._error_payload(caught.exception)["code"],
                    "target-conflict",
                )

                manifest.write_text("{\n", encoding="utf-8")
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    self._write_request(base_url, "/api/skills/set", request)
                self.assertEqual(caught.exception.code, 500)
                self.assertEqual(
                    self._error_payload(caught.exception)["code"],
                    "internal-error",
                )

            self.assertFalse(
                os.path.lexists(
                    home / ".gemini/antigravity-cli/plugins/lucas-skills/skills/docx"
                )
            )

    def test_trace_and_connect_are_structured_405_for_static_and_api(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            with running_http_server(repo, home, root / "Applications") as (
                server,
                _thread,
                _base_url,
            ):
                host, port = server.server_address
                requests = (
                    ("TRACE", "/", "GET"),
                    ("CONNECT", "/api/status", "GET"),
                    ("TRACE", "/api/skills/set", "POST"),
                    ("CONNECT", "/api/shutdown", "POST"),
                    ("PROPFIND", "/", "GET"),
                )
                for method, path, allowed in requests:
                    with self.subTest(method=method, path=path):
                        connection = http.client.HTTPConnection(host, port, timeout=2)
                        connection.request(method, path)
                        response = connection.getresponse()
                        self.assertEqual(response.status, 405)
                        self.assertEqual(response.headers["Allow"], allowed)
                        self.assertEqual(
                            response.headers.get_content_type(),
                            "application/json",
                        )
                        self.assertEqual(
                            json.loads(response.read())["code"],
                            "method-not-allowed",
                        )
                        connection.close()

    def test_set_preview_apply_and_invalid_skill_are_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            with running_http_server(
                repo,
                home,
                root / "Applications",
                lambda command: "/bin/claude" if command == "claude" else None,
            ) as (_server, _thread, base_url):
                preview = json.loads(
                    self._write_request(
                        base_url,
                        "/api/skills/set",
                        {"skill": None, "all": True, "tool": "claude", "on": True, "apply": False},
                    ).read()
                )
                self.assertEqual(preview["mode"], "plan")
                self.assertEqual(len(preview["changes"]), 1)
                self.assertFalse(os.path.lexists(home / ".claude/skills/docx"))

                applied = json.loads(
                    self._write_request(
                        base_url,
                        "/api/skills/set",
                        {"skill": None, "all": True, "tool": "claude", "on": True, "apply": True},
                    ).read()
                )
                self.assertEqual(applied["mode"], "apply")
                self.assertTrue((home / ".claude/skills/docx").is_symlink())

                with self.assertRaises(urllib.error.HTTPError) as caught:
                    self._write_request(
                        base_url,
                        "/api/skills/set",
                        {
                            "skill": "../evil",
                            "all": False,
                            "tool": "claude",
                            "on": True,
                            "apply": True,
                        },
                    )
                self.assertEqual(caught.exception.code, 400)
                self.assertEqual(self._error_payload(caught.exception)["code"], "invalid-skill")
                self.assertFalse(os.path.lexists(home / ".claude/evil"))

    def test_conflicted_set_preview_returns_full_plan_then_apply_is_409(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            write_skill(repo, "pdf", "pdf")
            occupied = home / ".claude/skills/pdf"
            occupied.mkdir(parents=True)
            with running_http_server(
                repo,
                home,
                root / "Applications",
                lambda command: "/bin/claude" if command == "claude" else None,
            ) as (_server, _thread, base_url):
                preview_response = self._write_request(
                    base_url,
                    "/api/skills/set",
                    {"skill": None, "all": True, "tool": "claude", "on": True, "apply": False},
                )
                self.assertEqual(preview_response.status, 200)
                preview = json.loads(preview_response.read())
                self.assertFalse(preview["ok"])
                self.assertEqual(preview["code"], "target-conflict")
                self.assertEqual(
                    {item["action"] for item in preview["changes"]},
                    {"create", "blocked"},
                )
                self.assertFalse(os.path.lexists(home / ".claude/skills/docx"))

                with self.assertRaises(urllib.error.HTTPError) as caught:
                    self._write_request(
                        base_url,
                        "/api/skills/set",
                        {"skill": None, "all": True, "tool": "claude", "on": True, "apply": True},
                    )
                self.assertEqual(caught.exception.code, 409)
                applied = self._error_payload(caught.exception)
                self.assertEqual(applied["code"], "target-conflict")
                self.assertEqual(
                    {item["code"] for item in applied["results"]},
                    {"applied", "blocked"},
                )
                self.assertTrue((home / ".claude/skills/docx").is_symlink())
                self.assertTrue(occupied.is_dir())

    def test_conflicted_adoption_preview_is_http_200_with_complete_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            skill = write_skill(repo, "docx", "docx")
            legacy_root = home / "legacy-antigravity"
            legacy_root.mkdir(parents=True)
            (legacy_root / "docx").symlink_to(skill)
            bridge = home / ".gemini/config/plugins/custom-skills/skills"
            bridge.parent.mkdir(parents=True)
            bridge.symlink_to(legacy_root)
            (home / ".gemini/config/skills/docx").mkdir(parents=True)
            applications = root / "Applications"
            (applications / "Antigravity.app").mkdir(parents=True)

            with running_http_server(repo, home, applications) as (
                _server,
                _thread,
                base_url,
            ):
                response = self._write_request(
                    base_url,
                    "/api/skills/adopt",
                    {"apply": False},
                )
                self.assertEqual(response.status, 200)
                preview = json.loads(response.read())
                self.assertFalse(preview["ok"])
                self.assertEqual(preview["code"], "target-conflict")
                self.assertEqual(
                    [item["action"] for item in preview["changes"]["link_changes"]],
                    ["blocked"],
                )
                self.assertEqual(len(preview["changes"]["bridge_removals"]), 1)
                self.assertEqual(
                    preview["changes"]["bridge_removals"][0]["path"],
                    str(bridge),
                )
                self.assertTrue(bridge.is_symlink())

    def test_target_conflict_is_409_and_preserves_occupied_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            occupied = home / ".claude/skills/docx"
            occupied.mkdir(parents=True)
            with running_http_server(
                repo,
                home,
                root / "Applications",
                lambda command: "/bin/claude" if command == "claude" else None,
            ) as (_server, _thread, base_url):
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    self._write_request(
                        base_url,
                        "/api/skills/set",
                        {
                            "skill": "docx",
                            "all": False,
                            "tool": "claude",
                            "on": True,
                            "apply": True,
                        },
                    )
                self.assertEqual(caught.exception.code, 409)
                self.assertEqual(
                    self._error_payload(caught.exception)["code"],
                    "target-conflict",
                )
                self.assertTrue(occupied.is_dir())

    def test_adopt_requires_apply_and_shutdown_stops_service(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            skill = write_skill(repo, "docx", "docx")
            legacy = home / ".cc-switch/skills/docx"
            legacy.parent.mkdir(parents=True)
            legacy.symlink_to(skill)
            target = home / ".claude/skills/docx"
            target.parent.mkdir(parents=True)
            target.symlink_to(legacy)
            with running_http_server(
                repo,
                home,
                root / "Applications",
                lambda command: "/bin/claude" if command == "claude" else None,
            ) as (_server, thread, base_url):
                preview = json.loads(
                    self._write_request(base_url, "/api/skills/adopt", {"apply": False}).read()
                )
                self.assertEqual(preview["mode"], "plan")
                self.assertEqual(Path(os.readlink(target)), legacy)
                preview_snapshot = Path(preview["changes"]["snapshot_path"])
                self.assertEqual(
                    preview_snapshot.parent,
                    home / ".local/state/lucas-agent-manager/snapshots",
                )
                self.assertFalse(preview_snapshot.exists())
                self.assertFalse((home / ".local/state/lucas-skills-manager").exists())

                applied = json.loads(
                    self._write_request(base_url, "/api/skills/adopt", {"apply": True}).read()
                )
                self.assertEqual(applied["mode"], "apply")
                self.assertEqual(target.resolve(), skill.resolve())
                applied_snapshot = Path(applied["changes"]["snapshot_path"])
                self.assertEqual(
                    applied_snapshot.parent,
                    home / ".local/state/lucas-agent-manager/snapshots",
                )
                self.assertTrue(applied_snapshot.is_file())
                self.assertFalse((home / ".local/state/lucas-skills-manager").exists())

                response = self._write_request(base_url, "/api/shutdown", {})
                self.assertTrue(json.loads(response.read())["ok"])
                thread.join(timeout=2)
                self.assertFalse(thread.is_alive())

    def test_index_bootstraps_escaped_token_once_without_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            web_root = repo / "tools/agent_manager/web"
            web_root.mkdir(parents=True)
            (web_root / "index.html").write_text(
                "<script>const token = __AGENT_MANAGER_TOKEN__;</script>",
                encoding="utf-8",
            )
            token = 'test-"token\n'
            server = create_server(repo, home, token, root / "Applications", lambda _: None)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address
            try:
                response = urllib.request.urlopen(f"http://{host}:{port}/", timeout=2)
                body = response.read().decode()
                self.assertEqual(body.count(json.dumps(token)), 1)
                self.assertNotIn("__AGENT_MANAGER_TOKEN__", body)
                self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")
                self.assertEqual(
                    response.headers["Content-Security-Policy"],
                    "default-src 'self'; script-src 'self' 'unsafe-inline'; "
                    "style-src 'self' 'unsafe-inline'; connect-src 'self'; "
                    "img-src 'self' data:; object-src 'none'; base-uri 'none'; "
                    "frame-ancestors 'none'",
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_instruction_set_preview_apply_and_fingerprint_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            (home / ".codex").mkdir(parents=True)
            with running_http_server(repo, home, root / "Applications") as (
                _server,
                _thread,
                base_url,
            ):
                intent = {
                    "target": "codex",
                    "on": True,
                    "apply": False,
                    "expected_fingerprint": None,
                }
                preview = json.loads(
                    self._write_request(base_url, "/api/instructions/set", intent).read()
                )
                self.assertTrue(preview["ok"])
                self.assertRegex(preview["fingerprint"], r"^[0-9a-f]{64}$")
                self.assertFalse((home / ".codex/AGENTS.md").exists())
                self.assertFalse(Path(preview["snapshot_path"]).exists())

                with self.assertRaises(urllib.error.HTTPError) as caught:
                    self._write_request(
                        base_url,
                        "/api/instructions/set",
                        {"target": "codex", "on": True, "apply": True},
                    )
                self.assertEqual(caught.exception.code, 400)
                self.assertEqual(self._error_payload(caught.exception)["code"], "invalid-request")
                self.assertFalse((home / ".codex/AGENTS.md").exists())
                self.assertFalse(Path(preview["snapshot_path"]).exists())

                for bad_fingerprint, expected_status, expected_code in (
                    ("not-a-fingerprint", 400, "invalid-request"),
                    ("0" * 64, 409, "state-changed"),
                ):
                    with self.subTest(bad_fingerprint=bad_fingerprint), self.assertRaises(
                        urllib.error.HTTPError
                    ) as caught:
                        self._write_request(
                            base_url,
                            "/api/instructions/set",
                            {**intent, "apply": True, "expected_fingerprint": bad_fingerprint},
                        )
                    self.assertEqual(caught.exception.code, expected_status)
                    self.assertEqual(self._error_payload(caught.exception)["code"], expected_code)
                    self.assertFalse((home / ".codex/AGENTS.md").exists())
                    self.assertFalse(Path(preview["snapshot_path"]).exists())

                applied = json.loads(
                    self._write_request(
                        base_url,
                        "/api/instructions/set",
                        {**intent, "apply": True, "expected_fingerprint": preview["fingerprint"]},
                    ).read()
                )
                self.assertTrue(applied["ok"])
                self.assertEqual(applied["changes"], preview["changes"])
                self.assertEqual(applied["fingerprint"], preview["fingerprint"])
                self.assertEqual(applied["snapshot_path"], preview["snapshot_path"])
                self.assertEqual((home / ".codex/AGENTS.md").resolve(), (repo / "AGENTS.md").resolve())
                self.assertTrue(Path(applied["snapshot_path"]).is_file())

    def test_instruction_adopt_replace_preview_and_apply_share_reviewed_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            for parent in (".agents", ".claude", ".codex", ".copilot", ".gemini"):
                (home / parent).mkdir(parents=True)
            (home / ".codex/AGENTS.md").write_text("foreign\n", encoding="utf-8")
            with running_http_server(repo, home, root / "Applications") as (
                _server,
                _thread,
                base_url,
            ):
                intent = {
                    "apply": False,
                    "replace_existing": True,
                    "expected_fingerprint": None,
                }
                preview = json.loads(
                    self._write_request(base_url, "/api/instructions/adopt", intent).read()
                )
                self.assertTrue(preview["ok"])
                self.assertIn("replace", {change["action"] for change in preview["changes"]})
                applied = json.loads(
                    self._write_request(
                        base_url,
                        "/api/instructions/adopt",
                        {**intent, "apply": True, "expected_fingerprint": preview["fingerprint"]},
                    ).read()
                )
                self.assertTrue(applied["ok"])
                self.assertEqual(applied["changes"], preview["changes"])
                self.assertEqual(applied["fingerprint"], preview["fingerprint"])
                self.assertEqual(applied["snapshot_path"], preview["snapshot_path"])
                self.assertEqual((home / ".codex/AGENTS.md").resolve(), (repo / "AGENTS.md").resolve())

    def test_instruction_planner_state_changed_is_409_before_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            (home / ".codex").mkdir(parents=True)
            intent = {
                "target": "codex",
                "on": True,
                "apply": False,
                "expected_fingerprint": None,
            }
            with running_http_server(repo, home, root / "Applications") as (
                _server,
                _thread,
                base_url,
            ), patch(
                "tools.agent_manager.server.plan_instruction_set",
                side_effect=InstructionPlanError(
                    "state-changed",
                    "instruction source changed after scan",
                ),
            ), self.assertRaises(urllib.error.HTTPError) as caught:
                self._write_request(base_url, "/api/instructions/set", intent)

            self.assertEqual(caught.exception.code, 409)
            payload = self._error_payload(caught.exception)
            self.assertEqual(payload["code"], "state-changed")
            self.assertEqual(payload["message"], "instruction source changed after scan")
            self.assertFalse((home / ".codex/AGENTS.md").exists())
            self.assertFalse((home / ".local/state/lucas-agent-manager").exists())

    def test_mixed_instruction_failures_describe_status_deciding_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            (home / ".codex").mkdir(parents=True)
            intent = {
                "target": "codex",
                "on": True,
                "apply": False,
                "expected_fingerprint": None,
            }
            with running_http_server(repo, home, root / "Applications") as (
                _server,
                _thread,
                base_url,
            ):
                preview = json.loads(
                    self._write_request(base_url, "/api/instructions/set", intent).read()
                )
                internal_path = home / ".codex/internal"
                blocked_path = home / ".codex/blocked"
                mixed_result = InstructionBatchResult(
                    False,
                    (
                        InstructionResult(
                            False,
                            "rollback-failed",
                            "codex",
                            internal_path,
                            "earlier internal failure",
                        ),
                        InstructionResult(
                            False,
                            "blocked",
                            "codex",
                            blocked_path,
                            "status-deciding conflict",
                        ),
                    ),
                    Path(preview["snapshot_path"]),
                )
                with patch(
                    "tools.agent_manager.server.apply_instruction_plan",
                    return_value=mixed_result,
                ), self.assertRaises(urllib.error.HTTPError) as caught:
                    self._write_request(
                        base_url,
                        "/api/instructions/set",
                        {
                            **intent,
                            "apply": True,
                            "expected_fingerprint": preview["fingerprint"],
                        },
                    )

            self.assertEqual(caught.exception.code, 409)
            payload = self._error_payload(caught.exception)
            self.assertEqual(payload["code"], "target-conflict")
            self.assertEqual(payload["message"], "status-deciding conflict")
            self.assertEqual(payload["path"], str(blocked_path))

    def test_instruction_result_status_mapping_and_unexpected_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            (home / ".codex").mkdir(parents=True)
            intent = {
                "target": "codex",
                "on": True,
                "apply": False,
                "expected_fingerprint": None,
            }
            with running_http_server(repo, home, root / "Applications") as (
                _server,
                _thread,
                base_url,
            ):
                for exception, status, code in (
                    (PermissionError("denied"), 403, "permission-denied"),
                    (RuntimeError("boom"), 500, "internal-error"),
                ):
                    with self.subTest(exception=type(exception).__name__), patch(
                        "tools.agent_manager.server.plan_instruction_set",
                        side_effect=exception,
                    ), self.assertRaises(urllib.error.HTTPError) as caught:
                        self._write_request(base_url, "/api/instructions/set", intent)
                    self.assertEqual(caught.exception.code, status)
                    self.assertEqual(self._error_payload(caught.exception)["code"], code)

                preview = json.loads(
                    self._write_request(base_url, "/api/instructions/set", intent).read()
                )
                rollback_result = InstructionBatchResult(
                    False,
                    (
                        InstructionResult(
                            False,
                            "rollback-failed",
                            "codex",
                            home / ".codex/AGENTS.md",
                            "rollback failed",
                        ),
                    ),
                    Path(preview["snapshot_path"]),
                )
                with patch(
                    "tools.agent_manager.server.apply_instruction_plan",
                    return_value=rollback_result,
                ), self.assertRaises(urllib.error.HTTPError) as caught:
                    self._write_request(
                        base_url,
                        "/api/instructions/set",
                        {**intent, "apply": True, "expected_fingerprint": preview["fingerprint"]},
                    )
                self.assertEqual(caught.exception.code, 500)
                self.assertEqual(self._error_payload(caught.exception)["code"], "internal-error")

    def test_serve_opens_browser_only_when_requested(self) -> None:
        class FakeServer:
            server_address = ("127.0.0.1", 43210)

            def serve_forever(self) -> None:
                return None

            def server_close(self) -> None:
                return None

        for open_browser in (False, True):
            with self.subTest(open_browser=open_browser), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp).resolve()
                output = io.StringIO()
                argv = ["serve"] + (["--open"] if open_browser else [])
                with (
                    patch(
                        "tools.agent_manager.server.secrets.token_urlsafe",
                        return_value="generated-token",
                    ),
                    patch(
                        "tools.agent_manager.server.create_server",
                        return_value=FakeServer(),
                    ) as create,
                    patch("tools.agent_manager.server.webbrowser.open") as browser_open,
                ):
                    code = main(
                        argv,
                        home=root / "home",
                        repo_root=root / "repo",
                        stdout=output,
                        applications=root / "Applications",
                    )

                self.assertEqual(code, 0)
                self.assertEqual(output.getvalue(), "http://127.0.0.1:43210/\n")
                self.assertEqual(browser_open.called, open_browser)
                create.assert_called_once()
