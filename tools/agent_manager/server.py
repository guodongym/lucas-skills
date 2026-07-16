from __future__ import annotations

import errno
import json
import os
import re
import secrets
import stat
import threading
import webbrowser
from collections.abc import Callable, Mapping, Sequence
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import TextIO

from .instructions import (
    InstructionBatchResult,
    apply_instruction_plan,
    plan_instruction_adoption,
    plan_instruction_set,
)
from .skills import (
    BatchResult,
    apply_adoption,
    apply_plan,
    plan_adoption,
    plan_set,
    scan_inventory,
)


TOOLS = ("claude", "codex", "copilot", "antigravity")
INSTRUCTION_TARGETS = ("shared", "claude", "codex", "copilot", "antigravity")
MAX_REQUEST_BODY = 64 * 1024
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; connect-src 'self'; "
    "img-src 'self' data:; object-src 'none'; base-uri 'none'; "
    "frame-ancestors 'none'"
)
TOKEN_HEADER = "X-Agent-Manager-Token"
WEB_PATH_PARTS = ("tools", "agent_manager", "web")
FINGERPRINT_RE = re.compile(r"^[0-9a-f]{64}$")

READ_ROUTES = {
    "/": "_get_index",
    "/api/status": "_get_status",
    "/api/inventory": "_get_inventory",
}
WRITE_ROUTES = {
    "/api/skills/set": ("_validate_skill_set", "_post_skill_set"),
    "/api/skills/adopt": ("_validate_skill_adopt", "_post_skill_adopt"),
    "/api/instructions/set": (
        "_validate_instruction_set",
        "_post_instruction_set",
    ),
    "/api/instructions/adopt": (
        "_validate_instruction_adopt",
        "_post_instruction_adopt",
    ),
    "/api/shutdown": ("_validate_shutdown", "_post_shutdown"),
}


def _business():
    # Imported lazily so cli.py can import only _serve without an import cycle.
    from . import cli

    return cli


def _error_payload(code: str, message: str) -> dict[str, object]:
    return {"ok": False, "code": code, "message": message}


def _open_directory_chain(root_fd: int, parts: Sequence[str], flags: int) -> int:
    current_fd = os.dup(root_fd)
    try:
        for part in parts:
            next_fd = os.open(part, flags, dir_fd=current_fd)
            os.close(current_fd)
            current_fd = next_fd
        return current_fd
    except BaseException:
        os.close(current_fd)
        raise


def _read_web_index(server: "AgentManagerHTTPServer") -> str:
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    repo_fd: int | None = None
    web_fd: int | None = None
    index_fd: int | None = None
    try:
        repo_fd = os.open(server.repo_root, directory_flags)
        web_fd = _open_directory_chain(repo_fd, WEB_PATH_PARTS, directory_flags)
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


def _failure_status(
    payload: dict[str, object],
    result: BatchResult | InstructionBatchResult,
) -> int:
    failures = [item for item in result.results if not item.ok]
    if not failures:
        return 200
    codes = {item.code for item in failures}
    if "permission-denied" in codes:
        selected_codes = {"permission-denied"}
        code, status = "permission-denied", 403
    elif "state-changed" in codes:
        selected_codes = {"state-changed"}
        code, status = "state-changed", 409
    elif codes & {"blocked", "target-conflict", "unsupported-target"}:
        selected_codes = {"blocked", "target-conflict", "unsupported-target"}
        code, status = "target-conflict", 409
    elif "requires-adopt" in codes:
        selected_codes = {"requires-adopt"}
        code, status = "requires-adopt", 409
    elif codes & {"invalid-plan", "invalid-fingerprint", "invalid-request"}:
        selected_codes = {"invalid-plan", "invalid-fingerprint", "invalid-request"}
        code, status = "invalid-request", 400
    else:
        selected_codes = codes
        code, status = "internal-error", 500
    failure = next(item for item in failures if item.code in selected_codes)
    payload["code"] = code
    payload["message"] = failure.message
    payload["path"] = failure.path
    return status


def _post_rescan_failure(
    payload: dict[str, object],
    result: BatchResult | InstructionBatchResult,
    exc: Exception,
) -> tuple[int, dict[str, object]]:
    business = _business()
    business._add_batch(payload, result)
    business._set_error(
        payload,
        "post-apply-verification-failed",
        "apply completed and returned results, but post-apply state verification "
        f"failed: {exc}",
    )
    return 500, payload


def _handle_skill_set(
    server: "AgentManagerHTTPServer",
    request: Mapping[str, object],
) -> tuple[int, dict[str, object]]:
    business = _business()
    apply = request["apply"]
    mode = "apply" if apply else "plan"
    agent_state = business.build_agent_state(
        server.repo_root, server.home, server.which, server.applications
    )
    state = agent_state.skills
    payload = business._command_payload(
        "set", mode, server.repo_root, agent_state, "skills"
    )
    if state.repository.issues:
        business._set_error(
            payload,
            "invalid-skill",
            business._repository_issue_message(state.repository.issues),
        )
        return 400, payload
    slugs = (
        [skill.slug for skill in state.repository.skills]
        if request["all"] is True
        else [request["skill"]]
    )
    plan = plan_set(state, slugs, [request["tool"]], request["on"])
    payload["changes"] = plan.changes
    if not apply:
        business._set_plan_status(payload, plan.changes)
        return 200, payload

    result = apply_plan(plan, {adapter.key: adapter for adapter in state.adapters})
    changes = payload["changes"]
    try:
        agent_state = business.build_agent_state(
            server.repo_root, server.home, server.which, server.applications
        )
    except Exception as exc:
        return _post_rescan_failure(payload, result, exc)
    payload = business._command_payload(
        "set", mode, server.repo_root, agent_state, "skills"
    )
    payload["changes"] = changes
    business._add_batch(payload, result)
    return _failure_status(payload, result), payload


def _handle_skill_adopt(
    server: "AgentManagerHTTPServer",
    request: Mapping[str, object],
) -> tuple[int, dict[str, object]]:
    business = _business()
    apply = request["apply"]
    mode = "apply" if apply else "plan"
    agent_state = business.build_agent_state(
        server.repo_root, server.home, server.which, server.applications
    )
    state = agent_state.skills
    payload = business._command_payload(
        "adopt", mode, server.repo_root, agent_state, "skills"
    )
    if state.repository.issues:
        business._set_error(
            payload,
            "invalid-skill",
            business._repository_issue_message(state.repository.issues),
        )
        return 400, payload
    plan = plan_adoption(state, server.home / ".local/state/lucas-agent-manager")
    payload["changes"] = business._adoption_changes(plan)
    if not apply:
        business._set_plan_status(payload, plan.link_changes)
        return 200, payload

    result = apply_adoption(plan, {adapter.key: adapter for adapter in state.adapters})
    changes = payload["changes"]
    try:
        agent_state = business.build_agent_state(
            server.repo_root, server.home, server.which, server.applications
        )
    except Exception as exc:
        return _post_rescan_failure(payload, result, exc)
    payload = business._command_payload(
        "adopt", mode, server.repo_root, agent_state, "skills"
    )
    payload["changes"] = changes
    business._add_batch(payload, result)
    return _failure_status(payload, result), payload


def _instruction_plan_payload(
    payload: dict[str, object],
    plan: object,
) -> dict[str, object]:
    payload["changes"] = plan.changes
    payload["fingerprint"] = plan.fingerprint
    payload["snapshot_path"] = plan.snapshot_path
    return payload


def _handle_instruction(
    server: "AgentManagerHTTPServer",
    request: Mapping[str, object],
    command: str,
) -> tuple[int, dict[str, object]]:
    business = _business()
    apply = request["apply"]
    mode = "apply" if apply else "plan"
    agent_state = business.build_agent_state(
        server.repo_root, server.home, server.which, server.applications
    )
    payload = business._command_payload(
        command, mode, server.repo_root, agent_state, "instructions"
    )
    state_dir = server.home / ".local/state/lucas-agent-manager"
    if command == "set":
        targets = (
            INSTRUCTION_TARGETS
            if request["target"] == "all"
            else (request["target"],)
        )
        plan = plan_instruction_set(
            agent_state.instructions,
            targets,
            request["on"],
            state_dir,
        )
    else:
        plan = plan_instruction_adoption(
            agent_state.instructions,
            state_dir,
            replace_existing=request["replace_existing"],
        )
    _instruction_plan_payload(payload, plan)
    if not apply:
        business._set_plan_status(payload, plan.changes)
        return 200, payload

    result = apply_instruction_plan(
        plan,
        server.home,
        expected_fingerprint=request["expected_fingerprint"],
    )
    reviewed = {
        "changes": payload["changes"],
        "fingerprint": payload["fingerprint"],
        "snapshot_path": payload["snapshot_path"],
    }
    business._add_batch(payload, result)
    try:
        agent_state = business.build_agent_state(
            server.repo_root, server.home, server.which, server.applications
        )
    except Exception as exc:
        return _post_rescan_failure(payload, result, exc)
    payload = business._command_payload(
        command, mode, server.repo_root, agent_state, "instructions"
    )
    payload.update(reviewed)
    business._add_batch(payload, result)
    return _failure_status(payload, result), payload


class AgentManagerHTTPServer(ThreadingHTTPServer):
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
        super().__init__(("127.0.0.1", 0), AgentManagerRequestHandler)


class AgentManagerRequestHandler(BaseHTTPRequestHandler):
    server: AgentManagerHTTPServer
    server_version = "AgentManagerHTTP/1.0"
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
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", CONTENT_SECURITY_POLICY)

    def _send_json(self, status: int, payload: Mapping[str, object]) -> None:
        body = json.dumps(
            _business().to_jsonable(dict(payload)), ensure_ascii=False
        ).encode("utf-8")
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
        return self.headers.get_all("Host", failobj=[]) == [f"{host}:{port}"]

    def _check_host(self) -> bool:
        if self._valid_host():
            return True
        self._send_problem(403, "invalid-host", "Host header does not match this service")
        return False

    def _check_write_authorization(self) -> bool:
        host, port = self.server.server_address
        expected_origin = f"http://{host}:{port}"
        tokens = self.headers.get_all(TOKEN_HEADER, failobj=[])
        origins = self.headers.get_all("Origin", failobj=[])
        token_ok = len(tokens) == 1 and secrets.compare_digest(
            tokens[0].encode("utf-8"), self.server.token.encode("utf-8")
        )
        if token_ok and origins == [expected_origin]:
            return True
        self._send_problem(403, "invalid-token", "write request authorization failed")
        return False

    def _read_json_object(self) -> dict[str, object] | None:
        content_types = self.headers.get_all("Content-Type", failobj=[])
        charset = self.headers.get_content_charset()
        if (
            len(content_types) != 1
            or self.headers.get_content_type() != "application/json"
            or (charset is not None and charset.lower() != "utf-8")
        ):
            self._send_problem(
                415,
                "invalid-request",
                "Content-Type must be application/json with optional UTF-8 charset",
            )
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
        if type(payload) is not dict:
            self._send_problem(400, "invalid-request", "request body must be a JSON object")
            return None
        return payload

    def _invalid_contract(self, contract: str) -> bool:
        self._send_problem(400, "invalid-request", f"request does not match {contract}")
        return False

    def _validate_skill_set(self, payload: dict[str, object]) -> bool:
        if set(payload) != {"skill", "all", "tool", "on", "apply"}:
            return self._invalid_contract("the Skills set contract")
        single = type(payload["skill"]) is str and payload["all"] is False
        bulk = payload["skill"] is None and payload["all"] is True
        if (
            (single or bulk)
            and type(payload["all"]) is bool
            and payload["tool"] in (*TOOLS, "all")
            and type(payload["tool"]) is str
            and type(payload["on"]) is bool
            and type(payload["apply"]) is bool
        ):
            return True
        return self._invalid_contract("the Skills set contract")

    def _validate_skill_adopt(self, payload: dict[str, object]) -> bool:
        if set(payload) == {"apply"} and type(payload["apply"]) is bool:
            return True
        return self._invalid_contract("the Skills adopt contract")

    @staticmethod
    def _valid_fingerprint_intent(payload: Mapping[str, object]) -> bool:
        if payload["apply"] is False:
            return payload["expected_fingerprint"] is None
        fingerprint = payload["expected_fingerprint"]
        return type(fingerprint) is str and FINGERPRINT_RE.fullmatch(fingerprint) is not None

    def _validate_instruction_set(self, payload: dict[str, object]) -> bool:
        if set(payload) != {"target", "on", "apply", "expected_fingerprint"}:
            return self._invalid_contract("the Instructions set contract")
        if (
            type(payload["target"]) is str
            and payload["target"] in (*INSTRUCTION_TARGETS, "all")
            and type(payload["on"]) is bool
            and type(payload["apply"]) is bool
            and self._valid_fingerprint_intent(payload)
        ):
            return True
        return self._invalid_contract("the Instructions set contract")

    def _validate_instruction_adopt(self, payload: dict[str, object]) -> bool:
        if set(payload) != {"apply", "replace_existing", "expected_fingerprint"}:
            return self._invalid_contract("the Instructions adopt contract")
        if (
            type(payload["apply"]) is bool
            and type(payload["replace_existing"]) is bool
            and self._valid_fingerprint_intent(payload)
        ):
            return True
        return self._invalid_contract("the Instructions adopt contract")

    def _validate_shutdown(self, payload: dict[str, object]) -> bool:
        if payload == {}:
            return True
        return self._invalid_contract("the shutdown contract")

    def _get_index(self) -> None:
        try:
            template = _read_web_index(self.server)
            if template.count("__AGENT_MANAGER_TOKEN__") != 1:
                raise ValueError("web index must contain exactly one token placeholder")
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
        except (UnicodeError, ValueError):
            self._send_problem(500, "internal-error", "failed to load web interface")
            return
        body = template.replace(
            "__AGENT_MANAGER_TOKEN__", json.dumps(self.server.token)
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self._security_headers()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _get_status(self) -> None:
        business = _business()
        try:
            state = business.build_agent_state(
                self.server.repo_root,
                self.server.home,
                self.server.which,
                self.server.applications,
            )
            self._send_json(200, business._base_payload(state, "status"))
        except PermissionError:
            self._send_problem(403, "permission-denied", "status scan was denied")
        except Exception:
            self._send_problem(500, "internal-error", "status scan failed")

    def _get_inventory(self) -> None:
        business = _business()
        try:
            state = business.build_agent_state(
                self.server.repo_root,
                self.server.home,
                self.server.which,
                self.server.applications,
            )
            inventory = scan_inventory(state.skills, self.server.home)
            issues = business._doctor_issues(state.skills, self.server.home)
            payload = {
                "ok": business._state_ok(state.skills) and not issues,
                "inventory": inventory,
                "issues": issues,
            }
            self._send_json(200, payload)
        except PermissionError:
            self._send_problem(403, "permission-denied", "inventory scan was denied")
        except Exception:
            self._send_problem(500, "internal-error", "inventory scan failed")

    def _post_skill_set(self, payload: dict[str, object]) -> None:
        self._send_operation(lambda: _handle_skill_set(self.server, payload), "skills")

    def _post_skill_adopt(self, payload: dict[str, object]) -> None:
        self._send_operation(lambda: _handle_skill_adopt(self.server, payload), "skills")

    def _post_instruction_set(self, payload: dict[str, object]) -> None:
        self._send_operation(
            lambda: _handle_instruction(self.server, payload, "set"),
            "instructions",
        )

    def _post_instruction_adopt(self, payload: dict[str, object]) -> None:
        self._send_operation(
            lambda: _handle_instruction(self.server, payload, "adopt"),
            "instructions",
        )

    def _post_shutdown(self, payload: dict[str, object]) -> None:
        del payload
        self._send_json(200, {"ok": True, "code": None, "message": ""})
        threading.Thread(target=self.server.shutdown, daemon=True).start()

    def _send_operation(
        self,
        operation: Callable[[], tuple[int, dict[str, object]]],
        domain: str,
    ) -> None:
        try:
            status, response = operation()
            self._send_json(status, response)
        except ValueError as exc:
            code = getattr(exc, "code", "invalid-skill" if domain == "skills" else "invalid-instructions")
            status = 409 if code == "state-changed" else 400
            self._send_problem(status, code, str(exc))
        except PermissionError as exc:
            self._send_problem(403, "permission-denied", str(exc))
        except Exception:
            self._send_problem(500, "internal-error", "request failed")

    def do_GET(self) -> None:
        if not self._check_host():
            return
        handler_name = READ_ROUTES.get(self.path)
        if handler_name is not None:
            getattr(self, handler_name)()
        elif self.path in WRITE_ROUTES:
            self._method_not_allowed("POST")
        else:
            self._send_problem(404, "not-found", "route does not exist")

    def do_POST(self) -> None:
        if not self._check_host():
            return
        if self.path in READ_ROUTES:
            self._method_not_allowed("GET")
            return
        route = WRITE_ROUTES.get(self.path)
        if route is None:
            self._send_problem(404, "not-found", "route does not exist")
            return
        if not self._check_write_authorization():
            return
        payload = self._read_json_object()
        if payload is None:
            return
        validator_name, handler_name = route
        if getattr(self, validator_name)(payload):
            getattr(self, handler_name)(payload)

    def _method_not_allowed(self, allowed: str) -> None:
        body = json.dumps(
            _error_payload("method-not-allowed", "method is not allowed")
        ).encode()
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
        if self.path in READ_ROUTES:
            self._method_not_allowed("GET")
        elif self.path in WRITE_ROUTES:
            self._method_not_allowed("POST")
        else:
            self._send_problem(404, "not-found", "route does not exist")


def create_server(
    repo_root: Path,
    home: Path,
    token: str,
    applications: Path,
    which: Callable[[str], str | None],
) -> AgentManagerHTTPServer:
    if not token:
        raise ValueError("token must not be empty")
    return AgentManagerHTTPServer(repo_root, home, token, applications, which)


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
