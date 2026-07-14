from __future__ import annotations

import argparse
import dataclasses
import errno
import json
import os
import secrets
import shutil
import stat
import sys
import threading
import webbrowser
from collections.abc import Callable, Mapping, Sequence
from enum import Enum
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import TextIO

from skill_manager_core import (
    AdoptionPlan,
    BatchResult,
    LinkState,
    ManagedState,
    ScanIssue,
    _enabled_codex_plugin_sources,
    apply_adoption,
    apply_plan,
    build_adapters,
    detect_surfaces,
    plan_adoption,
    plan_set,
    scan_inventory,
    scan_managed_state,
    scan_repository,
)


TOOLS = ("claude", "codex", "copilot", "antigravity")
MAX_REQUEST_BODY = 64 * 1024
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; connect-src 'self'; "
    "img-src 'self' data:"
)


def to_jsonable(value: object) -> object:
    if dataclasses.is_dataclass(value):
        return {
            field.name: to_jsonable(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    return value


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="skill-manager")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("status", "doctor"):
        command = subparsers.add_parser(name)
        command.add_argument("--json", action="store_true")

    set_parser = subparsers.add_parser("set")
    set_parser.add_argument("skill", nargs="?", default=None)
    set_parser.add_argument("--all", action="store_true")
    set_parser.add_argument(
        "--tool",
        choices=(*TOOLS, "all"),
        required=True,
    )
    toggle = set_parser.add_mutually_exclusive_group(required=True)
    toggle.add_argument("--on", action="store_true")
    toggle.add_argument("--off", action="store_true")
    set_parser.add_argument("--apply", action="store_true")
    set_parser.add_argument("--json", action="store_true")

    adopt_parser = subparsers.add_parser("adopt")
    adopt_parser.add_argument("--apply", action="store_true")
    adopt_parser.add_argument("--json", action="store_true")

    serve_parser = subparsers.add_parser("serve")
    serve_parser.add_argument("--open", action="store_true")
    return parser


def _build_state(
    repo_root: Path,
    home: Path,
    which: Callable[[str], str | None],
    applications: Path,
) -> ManagedState:
    repository = scan_repository(repo_root)
    adapters = build_adapters(home)
    surfaces = detect_surfaces(which=which, applications=applications)
    return scan_managed_state(repository, adapters, surfaces)


def _state_ok(state: ManagedState) -> bool:
    return not state.repository.issues and all(
        target.state not in {LinkState.CONFLICT, LinkState.ERROR}
        for target in state.targets
    )


def _base_payload(state: ManagedState, mode: str, *, ok: bool | None = None) -> dict[str, object]:
    return {
        "mode": mode,
        "ok": _state_ok(state) if ok is None else ok,
        "code": None,
        "message": "",
        "repo_root": state.repository.repo_root,
        "skills": state.repository.skills,
        "adapters": state.adapters,
        "surfaces": state.surfaces,
        "targets": state.targets,
        "issues": state.repository.issues,
    }


def _empty_adoption_changes() -> dict[str, object]:
    return {
        "link_changes": (),
        "container_changes": (),
        "bridge_removals": (),
        "snapshot_path": None,
    }


def _command_payload(
    command: str,
    mode: str,
    repo_root: Path,
    state: ManagedState | None = None,
) -> dict[str, object]:
    payload = _base_payload(state, mode) if state is not None else {
        "mode": mode,
        "ok": False,
        "code": None,
        "message": "",
        "repo_root": repo_root,
        "skills": (),
        "adapters": (),
        "surfaces": (),
        "targets": (),
        "issues": (),
    }
    if command == "doctor":
        payload["inventory"] = ()
    elif command == "set":
        payload["changes"] = ()
        payload["results"] = ()
    elif command == "adopt":
        payload["changes"] = _empty_adoption_changes()
        payload["results"] = ()
    return payload


def _set_error(payload: dict[str, object], code: str, message: str) -> None:
    payload["ok"] = False
    payload["code"] = code
    payload["message"] = message


def _repository_issue_message(issues: Sequence[ScanIssue]) -> str:
    details = "; ".join(f"{issue.code}: {issue.path}" for issue in issues)
    return (
        "repository contains invalid skills; no changes were planned or applied"
        f": {details}"
    )


def _batch_code(result: BatchResult) -> str | None:
    failures = [item for item in result.results if not item.ok]
    if not failures:
        return None
    if len(failures) != len(result.results):
        return "partial-failure"
    return failures[0].code


def _add_batch(payload: dict[str, object], result: BatchResult) -> None:
    payload["ok"] = result.ok
    payload["results"] = result.results
    code = _batch_code(result)
    if code is not None:
        payload["code"] = code


def _adoption_changes(plan: AdoptionPlan) -> dict[str, object]:
    return {
        "link_changes": plan.link_changes,
        "container_changes": plan.container_changes,
        "bridge_removals": plan.bridge_removals,
        "snapshot_path": plan.snapshot_path,
    }


def _set_plan_status(
    payload: dict[str, object],
    changes: Sequence[object],
) -> bool:
    conflict = next(
        (
            change
            for change in changes
            if getattr(change, "action", None)
            in {"blocked", "conflict", "error", "target-conflict"}
        ),
        None,
    )
    requires_adopt = next(
        (
            change
            for change in changes
            if getattr(change, "action", None) == "requires-adopt"
        ),
        None,
    )
    failure = conflict or requires_adopt
    if failure is None:
        payload["ok"] = True
        payload["code"] = None
        payload["message"] = ""
        payload.pop("path", None)
        return True
    code = "target-conflict" if conflict is not None else "requires-adopt"
    _set_error(payload, code, getattr(failure, "reason", "plan contains a conflict"))
    payload["path"] = getattr(failure, "target", None)
    return False


def _doctor_issues(state: ManagedState, home: Path) -> tuple[ScanIssue, ...]:
    _sources, plugin_issues = _enabled_codex_plugin_sources(home)
    return (*state.repository.issues, *plugin_issues)


def _enabled_counts(state: ManagedState) -> dict[str, int]:
    return {
        tool: len(
            {
                target.slug
                for target in state.targets
                if target.tool == tool
                and target.state in {LinkState.ENABLED, LinkState.LEGACY}
            }
        )
        for tool in TOOLS
    }


def _write_text(
    stdout: TextIO,
    state: ManagedState,
    mode: str,
    payload: Mapping[str, object],
) -> None:
    stdout.write(f"Mode: {mode}\n")
    stdout.write(f"Skills: {len(state.repository.skills)}\n")
    for tool, count in _enabled_counts(state).items():
        stdout.write(f"{tool}: {count} enabled\n")
    conflicts = sum(
        target.state in {LinkState.CONFLICT, LinkState.ERROR}
        for target in state.targets
    )
    stdout.write(f"Conflicts: {conflicts}\n")
    if not payload.get("ok", False) and payload.get("code"):
        stdout.write(f"Error [{payload['code']}]: {payload.get('message', '')}\n")
    if "changes" in payload:
        changes = payload["changes"]
        count = len(changes) if isinstance(changes, (list, tuple)) else sum(
            len(items)
            for key, items in changes.items()
            if key.endswith("_changes") or key == "bridge_removals"
        ) if isinstance(changes, dict) else 0
        stdout.write(f"Changes: {count}\n")
    if "results" in payload:
        results = payload["results"]
        stdout.write(f"Results: {len(results) if isinstance(results, (list, tuple)) else 0}\n")
    next_command = {
        "status": "skill-manager doctor",
        "doctor": "skill-manager set <skill> --tool <tool> --on",
        "plan": "repeat the command with --apply",
        "apply": "skill-manager status",
    }[mode]
    stdout.write(f"Next: {next_command}\n")


def _write_payload(
    stdout: TextIO,
    state: ManagedState,
    mode: str,
    payload: Mapping[str, object],
    json_output: bool,
) -> None:
    if json_output:
        json.dump(to_jsonable(dict(payload)), stdout, ensure_ascii=False, indent=2)
        stdout.write("\n")
    else:
        _write_text(stdout, state, mode, payload)


def _error_payload(code: str, message: str) -> dict[str, object]:
    return {"ok": False, "code": code, "message": message}


def _read_web_index(server: "SkillManagerHTTPServer") -> str:
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    repo_fd: int | None = None
    web_fd: int | None = None
    index_fd: int | None = None
    try:
        repo_fd = os.open(server.repo_root, directory_flags)
        web_fd = os.open("skill_manager_web", directory_flags, dir_fd=repo_fd)
        index_fd = os.open("index.html", os.O_RDONLY | os.O_NOFOLLOW, dir_fd=web_fd)
        if not stat.S_ISREG(os.fstat(index_fd).st_mode):
            raise FileNotFoundError("web index is not a regular file")
        with os.fdopen(index_fd, encoding="utf-8") as stream:
            index_fd = None
            return stream.read()
    finally:
        for descriptor in (index_fd, web_fd, repo_fd):
            if descriptor is not None:
                os.close(descriptor)


def _result_http_status(
    payload: dict[str, object],
    result: BatchResult,
) -> int:
    failures = [item for item in result.results if not item.ok]
    if not failures:
        return 200
    codes = {item.code for item in failures}
    if "permission-denied" in codes:
        code, status = "permission-denied", 403
    elif codes & {"blocked", "target-conflict", "state-changed"}:
        code, status = "target-conflict", 409
    elif "requires-adopt" in codes:
        code, status = "requires-adopt", 409
    elif "invalid-plan" in codes:
        code, status = "invalid-skill", 400
    else:
        code, status = "internal-error", 500
    failure = next(item for item in failures if item.code in codes)
    payload["code"] = code
    payload["message"] = failure.message
    payload["path"] = failure.path
    return status


def _handle_set_request(
    server: "SkillManagerHTTPServer",
    request: Mapping[str, object],
) -> tuple[int, dict[str, object]]:
    apply = request["apply"]
    mode = "apply" if apply else "plan"
    state = _build_state(server.repo_root, server.home, server.which, server.applications)
    payload = _command_payload("set", mode, server.repo_root, state)
    if state.repository.issues:
        _set_error(
            payload,
            "invalid-skill",
            _repository_issue_message(state.repository.issues),
        )
        return 400, payload
    slugs = (
        [skill.slug for skill in state.repository.skills]
        if request.get("all") is True
        else [request["skill"]]
    )
    plan = plan_set(state, slugs, [request["tool"]], request["enabled"])
    payload["changes"] = plan.changes
    if not apply:
        _set_plan_status(payload, plan.changes)
        return 200, payload

    result = apply_plan(plan, {adapter.key: adapter for adapter in state.adapters})
    state = _build_state(server.repo_root, server.home, server.which, server.applications)
    changes = payload["changes"]
    payload = _command_payload("set", mode, server.repo_root, state)
    payload["changes"] = changes
    _add_batch(payload, result)
    return _result_http_status(payload, result), payload


def _handle_adopt_request(
    server: "SkillManagerHTTPServer",
    request: Mapping[str, object],
) -> tuple[int, dict[str, object]]:
    apply = request["apply"]
    mode = "apply" if apply else "plan"
    state = _build_state(server.repo_root, server.home, server.which, server.applications)
    payload = _command_payload("adopt", mode, server.repo_root, state)
    if state.repository.issues:
        _set_error(
            payload,
            "invalid-skill",
            _repository_issue_message(state.repository.issues),
        )
        return 400, payload
    plan = plan_adoption(state, server.home / ".local/state/lucas-skills-manager")
    payload["changes"] = _adoption_changes(plan)
    if not apply:
        _set_plan_status(payload, plan.link_changes)
        return 200, payload

    result = apply_adoption(plan, {adapter.key: adapter for adapter in state.adapters})
    state = _build_state(server.repo_root, server.home, server.which, server.applications)
    changes = payload["changes"]
    payload = _command_payload("adopt", mode, server.repo_root, state)
    payload["changes"] = changes
    _add_batch(payload, result)
    return _result_http_status(payload, result), payload


class SkillManagerHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        repo_root: Path,
        home: Path,
        token: str,
        applications: Path,
        which: Callable[[str], str | None],
    ) -> None:
        self.repo_root = repo_root.expanduser().resolve()
        self.home = home.expanduser().resolve()
        self.token = token
        self.applications = applications.expanduser().resolve()
        self.which = which
        super().__init__(("127.0.0.1", 0), SkillManagerRequestHandler)


class SkillManagerRequestHandler(BaseHTTPRequestHandler):
    server: SkillManagerHTTPServer
    server_version = "SkillManagerHTTP/1.0"
    sys_version = ""

    def log_message(self, format: str, *args: object) -> None:
        del format, args

    def send_error(
        self,
        code: int,
        message: str | None = None,
        explain: str | None = None,
    ) -> None:
        del explain
        if code == 501:
            self._unsupported_method()
            return
        self._send_problem(code, "http-error", message or "HTTP request failed")

    def _security_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", CONTENT_SECURITY_POLICY)

    def _send_json(self, status: int, payload: Mapping[str, object]) -> None:
        body = json.dumps(to_jsonable(dict(payload)), ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._security_headers()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_problem(self, status: int, code: str, message: str) -> None:
        self._send_json(status, _error_payload(code, message))

    def _valid_host(self) -> bool:
        host, port = self.server.server_address
        expected = f"{host}:{port}"
        values = self.headers.get_all("Host", failobj=[])
        return values == [expected]

    def _check_host(self) -> bool:
        if self._valid_host():
            return True
        self._send_problem(403, "invalid-host", "Host header does not match this service")
        return False

    def _check_write_authorization(self) -> bool:
        host, port = self.server.server_address
        expected_origin = f"http://{host}:{port}"
        tokens = self.headers.get_all("X-Skill-Manager-Token", failobj=[])
        origins = self.headers.get_all("Origin", failobj=[])
        token_ok = len(tokens) == 1 and secrets.compare_digest(
            tokens[0], self.server.token
        )
        origin_ok = origins == [expected_origin]
        if token_ok and origin_ok:
            return True
        self._send_problem(403, "invalid-token", "write request authorization failed")
        return False

    def _read_json_object(self) -> dict[str, object] | None:
        content_types = self.headers.get_all("Content-Type", failobj=[])
        if len(content_types) != 1 or self.headers.get_content_type() != "application/json":
            self._send_problem(415, "invalid-request", "Content-Type must be application/json")
            return None
        if self.headers.get("Transfer-Encoding") is not None:
            self._send_problem(400, "invalid-request", "Transfer-Encoding is not supported")
            return None
        lengths = self.headers.get_all("Content-Length", failobj=[])
        if len(lengths) != 1:
            self._send_problem(411, "invalid-request", "Content-Length is required")
            return None
        try:
            length = int(lengths[0], 10)
        except ValueError:
            self._send_problem(400, "invalid-request", "Content-Length is invalid")
            return None
        if length < 0:
            self._send_problem(400, "invalid-request", "Content-Length is invalid")
            return None
        if length > MAX_REQUEST_BODY:
            self._send_problem(413, "request-too-large", "request body exceeds 64 KiB")
            return None

        def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
            result: dict[str, object] = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError(f"duplicate JSON field: {key}")
                result[key] = value
            return result

        def reject_constant(value: str) -> object:
            raise ValueError(f"invalid JSON constant: {value}")

        try:
            payload = json.loads(
                self.rfile.read(length),
                object_pairs_hook=unique_object,
                parse_constant=reject_constant,
            )
        except (UnicodeError, ValueError):
            self._send_problem(400, "invalid-request", "request body must be valid JSON")
            return None
        if not isinstance(payload, dict):
            self._send_problem(400, "invalid-request", "request body must be a JSON object")
            return None
        return payload

    def _validate_set_request(self, payload: dict[str, object]) -> bool:
        single_keys = {"skill", "tool", "enabled", "apply"}
        bulk_keys = {"all", "tool", "enabled", "apply"}
        keys = set(payload)
        single = keys == single_keys and isinstance(payload.get("skill"), str)
        bulk = keys == bulk_keys and payload.get("all") is True
        valid = (
            (single or bulk)
            and payload.get("tool") in (*TOOLS, "all")
            and type(payload.get("enabled")) is bool
            and type(payload.get("apply")) is bool
        )
        if valid:
            return True
        self._send_problem(400, "invalid-request", "request does not match the set contract")
        return False

    def _validate_apply_request(self, payload: dict[str, object]) -> bool:
        if set(payload) == {"apply"} and type(payload.get("apply")) is bool:
            return True
        self._send_problem(400, "invalid-request", "request does not match the adopt contract")
        return False

    def do_GET(self) -> None:
        if not self._check_host():
            return
        if self.path == "/":
            try:
                template = _read_web_index(self.server)
            except FileNotFoundError:
                self._send_problem(404, "not-found", "web interface is not installed")
                return
            except OSError as exc:
                if exc.errno in {errno.ENOENT, errno.ENOTDIR, errno.ELOOP}:
                    self._send_problem(404, "not-found", "web interface is not installed")
                elif exc.errno in {errno.EACCES, errno.EPERM}:
                    self._send_problem(403, "permission-denied", "web interface is not readable")
                else:
                    self._send_problem(500, "internal-error", "failed to load web interface")
                return
            except UnicodeError:
                self._send_problem(500, "internal-error", "failed to load web interface")
                return
            body = template.replace(
                "__SKILL_MANAGER_TOKEN__",
                json.dumps(self.server.token),
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self._security_headers()
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/api/status":
            try:
                state = _build_state(
                    self.server.repo_root,
                    self.server.home,
                    self.server.which,
                    self.server.applications,
                )
                self._send_json(200, _base_payload(state, "status"))
            except PermissionError:
                self._send_problem(403, "permission-denied", "status scan was denied")
            except Exception:
                self._send_problem(500, "internal-error", "status scan failed")
            return
        if self.path == "/api/inventory":
            try:
                state = _build_state(
                    self.server.repo_root,
                    self.server.home,
                    self.server.which,
                    self.server.applications,
                )
                inventory = scan_inventory(state, self.server.home)
                issues = _doctor_issues(state, self.server.home)
                payload = {
                    "ok": _state_ok(state) and not issues,
                    "inventory": inventory,
                    "issues": issues,
                }
                self._send_json(200, payload)
            except PermissionError:
                self._send_problem(403, "permission-denied", "inventory scan was denied")
            except Exception:
                self._send_problem(500, "internal-error", "inventory scan failed")
            return
        if self.path in {"/api/set", "/api/adopt", "/api/shutdown"}:
            self._method_not_allowed("POST")
            return
        self._send_problem(404, "not-found", "route does not exist")

    def do_POST(self) -> None:
        if not self._check_host():
            return
        if self.path in {"/", "/api/status", "/api/inventory"}:
            self._method_not_allowed("GET")
            return
        if self.path not in {"/api/set", "/api/adopt", "/api/shutdown"}:
            self._send_problem(404, "not-found", "route does not exist")
            return
        if not self._check_write_authorization():
            return
        payload = self._read_json_object()
        if payload is None:
            return
        if self.path == "/api/shutdown":
            if payload:
                self._send_problem(400, "invalid-request", "shutdown body must be empty")
                return
            self._send_json(200, {"ok": True, "code": None, "message": ""})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        try:
            if self.path == "/api/set":
                if not self._validate_set_request(payload):
                    return
                status, response = _handle_set_request(self.server, payload)
            else:
                if not self._validate_apply_request(payload):
                    return
                status, response = _handle_adopt_request(self.server, payload)
            self._send_json(status, response)
        except ValueError as exc:
            self._send_problem(400, "invalid-skill", str(exc))
        except PermissionError as exc:
            self._send_problem(403, "permission-denied", str(exc))
        except Exception:
            self._send_problem(500, "internal-error", "request failed")

    def _method_not_allowed(self, allowed: str) -> None:
        body = json.dumps(_error_payload("method-not-allowed", "method is not allowed")).encode()
        self.send_response(405)
        self.send_header("Allow", allowed)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._security_headers()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_PUT(self) -> None:
        self._unsupported_method()

    def do_PATCH(self) -> None:
        self._unsupported_method()

    def do_DELETE(self) -> None:
        self._unsupported_method()

    def do_OPTIONS(self) -> None:
        self._unsupported_method()

    def do_HEAD(self) -> None:
        self._unsupported_method()

    def _unsupported_method(self) -> None:
        if not self._check_host():
            return
        if self.path in {"/", "/api/status", "/api/inventory"}:
            self._method_not_allowed("GET")
        elif self.path in {"/api/set", "/api/adopt", "/api/shutdown"}:
            self._method_not_allowed("POST")
        else:
            self._send_problem(404, "not-found", "route does not exist")


def create_server(
    repo_root: Path,
    home: Path,
    token: str,
    applications: Path,
    which: Callable[[str], str | None],
) -> SkillManagerHTTPServer:
    if not token:
        raise ValueError("token must not be empty")
    return SkillManagerHTTPServer(repo_root, home, token, applications, which)


def _serve(
    stdout: TextIO,
    open_browser: bool,
    repo_root: Path,
    home: Path,
    applications: Path,
    which: Callable[[str], str | None],
) -> int:
    token = secrets.token_urlsafe(32)
    server = create_server(repo_root, home, token, applications, which)
    host, port = server.server_address
    url = f"http://{host}:{port}/"
    stdout.write(f"{url}\n")
    stdout.flush()
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def main(
    argv: Sequence[str] | None = None,
    *,
    home: Path | None = None,
    repo_root: Path | None = None,
    stdout: TextIO | None = None,
    which: Callable[[str], str | None] = shutil.which,
    applications: Path = Path("/Applications"),
) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    stdout = stdout or sys.stdout
    home = (home or Path.home()).expanduser().resolve()
    repo_root = (repo_root or Path(__file__).resolve().parent).expanduser().resolve()
    applications = applications.expanduser().resolve()

    if args.command == "serve":
        return _serve(stdout, args.open, repo_root, home, applications, which)
    if args.command == "set" and bool(args.all) == bool(args.skill):
        parser.error("set requires exactly one of <skill> or --all")

    if args.command in {"set", "adopt"}:
        mode = "apply" if args.apply else "plan"
    else:
        mode = args.command
    state: ManagedState | None = None
    payload = _command_payload(args.command, mode, repo_root)
    try:
        state = _build_state(repo_root, home, which, applications)
        payload = _command_payload(args.command, mode, repo_root, state)
        if args.command == "status":
            _write_payload(stdout, state, "status", payload, args.json)
            return 0 if payload["ok"] else 1

        if args.command == "doctor":
            inventory = scan_inventory(state, home)
            payload["inventory"] = inventory
            issues = _doctor_issues(state, home)
            broken_inventory = any(
                record.source_type == "broken" or record.flags
                for record in inventory
            )
            ok = _state_ok(state) and not issues and not broken_inventory
            payload["ok"] = ok
            payload["issues"] = issues
            _write_payload(stdout, state, "doctor", payload, args.json)
            return 0 if ok else 1

        if state.repository.issues:
            _set_error(
                payload,
                "invalid-skill",
                _repository_issue_message(state.repository.issues),
            )
            _write_payload(stdout, state, mode, payload, args.json)
            return 1

        if args.command == "set":
            slugs = (
                [skill.slug for skill in state.repository.skills]
                if args.all
                else [args.skill]
            )
            plan = plan_set(state, slugs, [args.tool], args.on)
            payload["changes"] = plan.changes
            if not args.apply:
                ok = _set_plan_status(payload, plan.changes)
                _write_payload(stdout, state, "plan", payload, args.json)
                return 0 if ok else 1

            result = apply_plan(plan, {adapter.key: adapter for adapter in state.adapters})
            _add_batch(payload, result)
            state = _build_state(repo_root, home, which, applications)
            changes = payload["changes"]
            payload = _command_payload(args.command, mode, repo_root, state)
            payload["changes"] = changes
            _add_batch(payload, result)
            _write_payload(stdout, state, "apply", payload, args.json)
            return 0 if result.ok else 1

        plan = plan_adoption(state, home / ".local/state/lucas-skills-manager")
        payload["changes"] = _adoption_changes(plan)
        if not args.apply:
            ok = _set_plan_status(payload, plan.link_changes)
            _write_payload(stdout, state, "plan", payload, args.json)
            return 0 if ok else 1

        result = apply_adoption(plan, {adapter.key: adapter for adapter in state.adapters})
        _add_batch(payload, result)
        state = _build_state(repo_root, home, which, applications)
        changes = payload["changes"]
        payload = _command_payload(args.command, mode, repo_root, state)
        payload["changes"] = changes
        _add_batch(payload, result)
        _write_payload(stdout, state, "apply", payload, args.json)
        return 0 if result.ok else 1
    except ValueError as exc:
        if args.command == "set":
            code = "invalid-skill"
        elif args.command == "adopt":
            code = "adoption-failed"
        else:
            code = "internal-error"
        _set_error(payload, code, str(exc))
    except PermissionError as exc:
        _set_error(payload, "permission-denied", str(exc))
    except (OSError, RuntimeError) as exc:
        code = "adoption-failed" if args.command == "adopt" else "verification-failed"
        _set_error(payload, code, str(exc))
    except Exception as exc:
        _set_error(payload, "internal-error", str(exc))

    if args.json:
        json.dump(to_jsonable(payload), stdout, ensure_ascii=False, indent=2)
        stdout.write("\n")
    else:
        stdout.write(f"Error [{payload['code']}]: {payload['message']}\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
