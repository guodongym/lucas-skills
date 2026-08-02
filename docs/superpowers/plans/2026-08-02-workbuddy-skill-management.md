# WorkBuddy Skill Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add WorkBuddy Desktop as a fifth Agent Manager Skill tool family, managing per-Skill links under `~/.workbuddy/skills` while leaving WorkBuddy custom instructions and existing local Skills untouched.

**Architecture:** Extend the existing generic Skill adapter, surface detection, planning, apply, inventory, CLI, HTTP, and Web paths. WorkBuddy contributes one Desktop-only adapter and one read-only inventory source; it does not add an Instructions target, CLI surface, plugin manifest, whole-directory link, or WorkBuddy-specific migration behavior.

**Tech Stack:** Python 3.11, `unittest`, `argparse`, stdlib HTTP server, vanilla JavaScript/HTML, `uv`.

**Global Constraints:**

- Execute implementation in an isolated worktree on branch `feature/workbuddy-skill-management`; do not implement on `main`.
- Use only temporary HOME and Applications directories in automated tests. Do not read from or write to the real `~/.workbuddy` during implementation.
- Add `workbuddy` only to Skill tool enumerations. Keep `INSTRUCTION_TARGETS` and the five Instructions file targets unchanged.
- Treat an existing ordinary `~/.workbuddy/skills/<slug>` directory or file as `conflict`; never replace, adopt, move, or delete it.
- Do not add a WorkBuddy CLI detector, plugin manifest, dependency, schema, or whole-directory symlink.
- Follow red-green-refactor for each behavior task and run the stated focused test before committing.

---

## Task 1: Prepare the isolated implementation worktree

**Files:**

- Read: `docs/superpowers/specs/2026-08-02-workbuddy-skill-management-design.md`
- Read: `docs/superpowers/plans/2026-08-02-workbuddy-skill-management.md`

- [ ] **Step 1: Invoke the worktree workflow**

Read and follow `superpowers:using-git-worktrees` before changing runtime or test files.

- [ ] **Step 2: Create the feature worktree from the reviewed planning commit**

Run:

```bash
git status --short --branch
git worktree add ../lucas-skills-workbuddy -b feature/workbuddy-skill-management main
```

Expected: the source checkout remains clean and the new worktree is on `feature/workbuddy-skill-management` at the commit containing both the approved design and this plan.

- [ ] **Step 3: Establish the baseline in the new worktree**

Run from `../lucas-skills-workbuddy`:

```bash
uv run python -m unittest discover -s tests -p 'test_*.py'
git status --short --branch
```

Expected: all existing tests pass and the worktree is clean. If the baseline fails, stop and report the exact failures before implementation.

---

## Task 2: Add the WorkBuddy adapter, Desktop detection, and managed-state behavior

**Files:**

- Modify: `tests/test_agent_manager.py`
- Modify: `tools/agent_manager/skills.py`

- [ ] **Step 1: Write failing adapter and surface tests**

Extend `ManagedStateTests.test_builds_exact_target_roots` so the expected adapter keys include `workbuddy-desktop`, then assert:

```python
self.assertEqual(
    adapters["workbuddy-desktop"].root,
    home / ".workbuddy/skills",
)
self.assertEqual(adapters["workbuddy-desktop"].tool, "workbuddy")
self.assertEqual(
    adapters["workbuddy-desktop"].surfaces,
    ("workbuddy-desktop",),
)
```

Extend `test_detects_exact_surfaces_codex_fallback_and_agy_cli`, create `WorkBuddy.app` beside `Codex.app`, and change its expected surface set to include only `workbuddy-desktop` for WorkBuddy. Keep the expected command probes exactly:

```python
self.assertEqual(commands, ["claude", "codex", "copilot", "agy"])
self.assertTrue(surfaces["workbuddy-desktop"].installed)
self.assertEqual(surfaces["workbuddy-desktop"].detector, "application")
```

Run:

```bash
uv run python -m unittest \
  tests.test_agent_manager.ManagedStateTests.test_builds_exact_target_roots \
  tests.test_agent_manager.ManagedStateTests.test_detects_exact_surfaces_codex_fallback_and_agy_cli
```

Expected: FAIL because the adapter and surface do not exist yet.

- [ ] **Step 2: Implement the adapter and Desktop-only surface**

Add this adapter to `build_adapters`:

```python
TargetAdapter(
    "workbuddy-desktop",
    "workbuddy",
    home,
    home / ".workbuddy/skills",
    ("workbuddy-desktop",),
),
```

Add this entry to `app_candidates` in `detect_surfaces`:

```python
"workbuddy-desktop": (applications / "WorkBuddy.app",),
```

Do not modify `cli_commands`.

- [ ] **Step 3: Verify adapter and surface tests turn green**

Run the two tests from Step 1 again.

Expected: PASS; command probes remain four, proving no WorkBuddy CLI surface was invented.

- [ ] **Step 4: Write failing WorkBuddy state and plan/apply tests**

Add a `WorkBuddyTests` class using `TemporaryDirectory`, `write_skill`, and `build_test_state`. Cover all of these cases:

```python
def test_classifies_disabled_enabled_conflict_and_unavailable(self) -> None:
    # WorkBuddy.app absent -> unavailable and no ~/.workbuddy created.
    # WorkBuddy.app present + missing target -> disabled.
    # Direct link to repo Skill -> enabled.
    # Ordinary same-slug directory -> conflict and remains a directory.

def test_set_on_and_off_apply_only_the_direct_repository_link(self) -> None:
    # With WorkBuddy.app present, plan_set(state, ["docx"], ["workbuddy"], True)
    # yields one create at ~/.workbuddy/skills/docx.
    # apply_plan creates a direct link to repo/skills/docx.
    # A fresh off plan removes that link and nothing else.

def test_all_includes_workbuddy_without_changing_existing_local_directory(self) -> None:
    # --tool all planning includes workbuddy-desktop.
    # An existing ordinary ~/.workbuddy/skills/docx is blocked, preserved,
    # and is never converted into a link.
```

Use concrete assertions for the core contract:

```python
self.assertEqual(change.adapter_key, "workbuddy-desktop")
self.assertEqual(change.target, home / ".workbuddy/skills/docx")
self.assertEqual(change.action, "create")
self.assertEqual(target.resolve(), (repo / "skills/docx").resolve())
self.assertFalse(target.exists())  # after the off apply
```

Run:

```bash
uv run python -m unittest tests.test_agent_manager.WorkBuddyTests
```

Expected: confirm the new tests pass through the existing generic state/planning/apply implementation. If a test fails, make the smallest generic fix in `skills.py`; do not add a WorkBuddy-specific write path.

- [ ] **Step 5: Commit the core adapter behavior**

Run:

```bash
git add tests/test_agent_manager.py tools/agent_manager/skills.py
git commit \
  -m "feat(agent-manager): add WorkBuddy Skill adapter" \
  -m "Add a Desktop-only WorkBuddy target that reuses the existing per-Skill link state and safe apply behavior. Existing WorkBuddy directories remain conflicts and no CLI or plugin surface is introduced." \
  -m "验证：
- uv run python -m unittest tests.test_agent_manager.ManagedStateTests tests.test_agent_manager.WorkBuddyTests" \
  -m "Co-authored-by: OpenAI Codex <noreply@openai.com>"
```

---

## Task 3: Add WorkBuddy to read-only inventory without adopting local Skills

**Files:**

- Modify: `tests/test_agent_manager.py`
- Modify: `tools/agent_manager/skills.py`

- [ ] **Step 1: Write the failing inventory test**

Add `InventoryTests.test_lists_workbuddy_managed_external_and_broken_skills_without_mutation`. In a temporary HOME create:

```text
~/.workbuddy/skills/docx       -> repo/skills/docx
~/.workbuddy/skills/private/      ordinary valid Skill directory
~/.workbuddy/skills/broken        broken symlink
```

Snapshot HOME before and after `scan_inventory`, then assert:

```python
self.assertEqual(self._tree_snapshot(home), before)
self.assertTrue(any(
    record.slug == "docx"
    and record.source_type == "managed"
    and record.tools == ("workbuddy",)
    and record.surfaces == ("workbuddy-desktop",)
    for record in records
))
self.assertTrue(any(
    record.slug == "private"
    and record.source_type == "local-copy"
    and record.tools == ("workbuddy",)
    for record in records
))
self.assertTrue(any(
    record.slug == "broken"
    and record.source_type == "broken"
    for record in records
))
```

Run:

```bash
uv run python -m unittest \
  tests.test_agent_manager.InventoryTests.test_lists_workbuddy_managed_external_and_broken_skills_without_mutation
```

Expected: FAIL because `~/.workbuddy/skills` is not an inventory source.

- [ ] **Step 2: Add the fixed WorkBuddy inventory source**

Add to `_fixed_inventory_sources`:

```python
InventorySource(
    home / ".workbuddy/skills",
    ("workbuddy",),
    ("workbuddy-desktop",),
    "user-root",
),
```

Do not add adoption or migration rules.

- [ ] **Step 3: Verify inventory behavior and regression coverage**

Run:

```bash
uv run python -m unittest tests.test_agent_manager.InventoryTests
```

Expected: all inventory tests pass and the before/after tree snapshots are identical.

- [ ] **Step 4: Commit the inventory extension**

Run:

```bash
git add tests/test_agent_manager.py tools/agent_manager/skills.py
git commit \
  -m "feat(agent-manager): inventory WorkBuddy Skills" \
  -m "Expose WorkBuddy's user Skill root through the existing read-only inventory so managed links, local copies, and broken entries are visible without changing ownership or filesystem state." \
  -m "验证：
- uv run python -m unittest tests.test_agent_manager.InventoryTests" \
  -m "Co-authored-by: OpenAI Codex <noreply@openai.com>"
```

---

## Task 4: Expose WorkBuddy through CLI and HTTP Skill contracts

**Files:**

- Modify: `tests/test_agent_manager.py`
- Modify: `tests/test_agent_manager_http.py`
- Modify: `tools/agent_manager/cli.py`
- Modify: `tools/agent_manager/server.py`

- [ ] **Step 1: Write failing CLI contract tests**

In `UmbrellaParserTests`, add a valid parser execution using a temporary repository/Home rather than calling the parser without dependencies. Add an integration test beside `test_status_json_contains_tools_surfaces_and_targets` that creates `Applications/WorkBuddy.app` and runs:

```python
code = main(
    ["skills", "set", "pdf", "--tool", "workbuddy", "--on", "--json"],
    home=home,
    repo_root=repo,
    stdout=output,
    which=lambda _: None,
    applications=applications,
)
```

Assert exit code `0` and exactly one WorkBuddy preview change:

```python
self.assertEqual(payload["changes"][0]["adapter_key"], "workbuddy-desktop")
self.assertEqual(payload["changes"][0]["action"], "create")
self.assertFalse((home / ".workbuddy").exists())
```

Update `test_status_json_contains_tools_surfaces_and_targets` to expect 6 adapters and 9 surfaces, and assert `workbuddy-desktop` is present while the Instructions target count remains 5.

Run:

```bash
uv run python -m unittest \
  tests.test_agent_manager.UmbrellaParserTests \
  tests.test_agent_manager.CliTests.test_status_json_contains_tools_surfaces_and_targets
```

Expected: FAIL because `workbuddy` is not an accepted CLI tool.

- [ ] **Step 2: Add WorkBuddy only to the CLI Skill tool enumeration**

Change:

```python
TOOLS = ("claude", "codex", "copilot", "antigravity", "workbuddy")
```

Leave this line unchanged:

```python
INSTRUCTION_TARGETS = ("shared", "claude", "codex", "copilot", "antigravity")
```

Run the focused CLI tests again. Expected: PASS.

- [ ] **Step 3: Write the failing HTTP preview/apply contract test**

In `tests/test_agent_manager_http.py`, start `running_http_server` with a temporary `Applications/WorkBuddy.app`, then POST this exact body to `/api/skills/set`:

```python
request = {
    "skill": "docx",
    "all": False,
    "tool": "workbuddy",
    "on": True,
    "apply": False,
}
```

Assert preview returns `200`, one `workbuddy-desktop` create change, and no target exists. Then set `request["apply"] = True`, POST again, and assert the resulting target is a direct link to `repo/skills/docx`. Also send the same shape with `tool="unknown"` and assert the existing structured `400 invalid-request` response.

Run:

```bash
uv run python -m unittest \
  tests.test_agent_manager_http.HttpServerTests.test_workbuddy_skill_set_preview_and_apply
```

Expected: FAIL with `400` for WorkBuddy before the server enumeration changes.

- [ ] **Step 4: Add WorkBuddy only to the HTTP Skill tool enumeration**

In `server.py`, change:

```python
TOOLS = ("claude", "codex", "copilot", "antigravity", "workbuddy")
```

Keep `INSTRUCTION_TARGETS` unchanged. Run:

```bash
uv run python -m unittest \
  tests.test_agent_manager_http.HttpServerTests.test_workbuddy_skill_set_preview_and_apply
```

Expected: PASS; unknown tools still return `400`.

- [ ] **Step 5: Commit CLI and HTTP support**

Run:

```bash
git add tests/test_agent_manager.py tests/test_agent_manager_http.py \
  tools/agent_manager/cli.py tools/agent_manager/server.py
git commit \
  -m "feat(agent-manager): expose WorkBuddy Skill controls" \
  -m "Allow WorkBuddy in the existing CLI and HTTP Skills set contracts while deliberately preserving the original Instructions target enumeration." \
  -m "验证：
- uv run python -m unittest tests.test_agent_manager.UmbrellaParserTests
- uv run python -m unittest tests.test_agent_manager_http.HttpServerTests.test_workbuddy_skill_set_preview_and_apply" \
  -m "Co-authored-by: OpenAI Codex <noreply@openai.com>"
```

---

## Task 5: Render WorkBuddy correctly in the Web console

**Files:**

- Modify: `tests/test_agent_manager_web.py`
- Modify: `tools/agent_manager/web/app.js`
- Modify: `tools/agent_manager/web/index.html`

- [ ] **Step 1: Write failing static UI contract tests**

Extend the existing HTML select tests to require a `workbuddy` option in both `#skills-bulk-tool` and `#inventory-tool-filter`:

```html
<option value="workbuddy">WorkBuddy</option>
```

Add a JavaScript export assertion that the WorkBuddy label is recognized by inventory presentation:

```python
self.assertEqual(
    self._run_exports("AgentManagerTest.inventoryToolLabel('workbuddy')"),
    "WorkBuddy",
)
```

Run:

```bash
uv run python -m unittest tests.test_agent_manager_web.WebPageTests
```

Expected: FAIL because the family and options are absent.

- [ ] **Step 2: Write the failing Desktop-only topology test**

Add a payload with:

```python
{
    "surfaces": [
        {"key": "workbuddy-desktop", "installed": True, "detector": "application"},
    ],
    "skills": {
        "records": [{"slug": "docx"}],
        "adapters": [{
            "key": "workbuddy-desktop",
            "tool": "workbuddy",
            "home": "/Users/test",
            "root": "/Users/test/.workbuddy/skills",
            "surfaces": ["workbuddy-desktop"],
        }],
        "targets": [{
            "slug": "docx",
            "adapter_key": "workbuddy-desktop",
            "tool": "workbuddy",
            "state": "disabled",
            "path": "/Users/test/.workbuddy/skills/docx",
        }],
    },
    "instructions": {"targets": [], "manual_surfaces": []},
}
```

Assert the WorkBuddy route:

```python
self.assertEqual(route["label"], "WorkBuddy")
self.assertEqual(route["surfaces"], [
    {"key": "workbuddy-desktop", "label": "Desktop", "installed": True},
])
self.assertEqual(route["skills"]["roots"][0]["fullPath"], "/Users/test/.workbuddy/skills")
self.assertEqual(route["instructions"]["statusLabel"], "手动配置")
self.assertIn("自定义指令", route["instructions"]["messages"][0])
```

Expected: FAIL because the current topology assumes every family has both Desktop and CLI, and an empty Instructions route is reported as needing attention.

- [ ] **Step 3: Add WorkBuddy family metadata and manual Instructions presentation**

Represent the family with explicit surface and instruction presentation metadata:

```javascript
{ key: "workbuddy", label: "WorkBuddy", surfaces: ["desktop"], instructionsManual: true },
```

Update `toolSurfaceRows` to use `family.surfaces` when declared and otherwise retain `["desktop", "cli"]`:

```javascript
const family = TOOL_FAMILIES.find((item) => item.key === tool);
const surfaceKinds = family && family.surfaces ? family.surfaces : ["desktop", "cli"];
return surfaceKinds.map((kind) => {
  const key = `${tool}-${kind}`;
  const surface = asArray(surfaces).find((item) => item.key === key);
  return {
    key,
    label: kind === "desktop" ? "Desktop" : "CLI",
    installed: Boolean(surface && surface.installed),
  };
});
```

Inside `buildTopology`, synthesize presentation-only manual information when `family.instructionsManual` is true and the API has no WorkBuddy Instructions target:

```javascript
const presentedInstructions = family.instructionsManual && toolInstructions.length === 0
  ? [{
      key: `${family.key}-custom-instructions`,
      state: "manual",
      path: "",
      surfaces: [`${family.key}-desktop`],
      message: "WorkBuddy 自定义指令需在应用内的“个性化 → 自定义指令”手工维护。",
    }]
  : toolInstructions;
```

Use `presentedInstructions` only for rendering/status. Do not add it to HTTP payloads, `INSTRUCTION_TARGETS`, write actions, or Instructions target counts.

Add `<option value="workbuddy">WorkBuddy</option>` to the two Skill/inventory tool selects in `index.html`.

- [ ] **Step 4: Verify Web behavior and existing family coverage**

Run the full Web test module:

```bash
uv run python -m unittest tests.test_agent_manager_web
```

Expected: all tests pass; existing Claude/Codex/Copilot/Antigravity routes still show their prior Desktop/CLI surfaces and WorkBuddy has only Desktop.

- [ ] **Step 5: Commit the Web console support**

Run:

```bash
git add tests/test_agent_manager_web.py tools/agent_manager/web/app.js \
  tools/agent_manager/web/index.html
git commit \
  -m "feat(agent-manager): show WorkBuddy in Web console" \
  -m "Add WorkBuddy to Skill controls, inventory filters, and topology while presenting its application-only custom instructions as a manual boundary instead of a managed or failing target." \
  -m "验证：
- uv run python -m unittest tests.test_agent_manager_web" \
  -m "Co-authored-by: OpenAI Codex <noreply@openai.com>"
```

---

## Task 6: Update the user contract and documentation

**Files:**

- Modify: `tests/test_agent_manager.py`
- Modify: `README.md`

- [ ] **Step 1: Update README contract tests first**

In `ReadmeTests`, require these exact concepts and paths:

```python
for text in (
    "WorkBuddy",
    "WorkBuddy.app",
    "~/.workbuddy/skills/<skill>",
    "个性化 → 自定义指令",
    "五个工具族、九个检测表面",
    "六个 Skill 根目录",
    "五个 Instructions 文件入口",
):
    self.assertIn(text, readme)
```

Replace obsolete count assertions for four tool families/eight surfaces/five Skill roots. Add an explicit negative/unchanged contract assertion that the Instructions table still has no `workbuddy` target row.

Run:

```bash
uv run python -m unittest tests.test_agent_manager.ReadmeTests
```

Expected: FAIL until README is updated.

- [ ] **Step 2: Document the fifth Skill family and the Instructions boundary**

Update the Agent Manager introduction and support matrix to say:

- five tool families;
- nine detected surfaces;
- six managed Skill roots;
- WorkBuddy row: Desktop `WorkBuddy.app`, no managed CLI, `~/.workbuddy/skills/<skill>`;
- `doctor` scans the WorkBuddy user Skill root read-only;
- WorkBuddy custom instructions remain manual at “个性化 → 自定义指令” and are not an `AGENTS.md` target;
- after enabling a WorkBuddy Skill, create a new WorkBuddy task to verify discovery; do not promise hot reload.

Keep the existing five-row Instructions table unchanged.

- [ ] **Step 3: Verify documentation tests**

Run:

```bash
uv run python -m unittest tests.test_agent_manager.ReadmeTests
```

Expected: PASS.

- [ ] **Step 4: Commit documentation**

Run:

```bash
git add tests/test_agent_manager.py README.md
git commit \
  -m "docs(agent-manager): document WorkBuddy Skill support" \
  -m "Describe WorkBuddy's Desktop Skill path, read-only inventory behavior, and new-task verification while keeping application custom instructions outside automated AGENTS.md management." \
  -m "验证：
- uv run python -m unittest tests.test_agent_manager.ReadmeTests" \
  -m "Co-authored-by: OpenAI Codex <noreply@openai.com>"
```

---

## Task 7: Run full verification and review the implementation

**Files:**

- Verify: `tools/agent_manager/skills.py`
- Verify: `tools/agent_manager/cli.py`
- Verify: `tools/agent_manager/server.py`
- Verify: `tools/agent_manager/web/app.js`
- Verify: `tools/agent_manager/web/index.html`
- Verify: `tests/test_agent_manager.py`
- Verify: `tests/test_agent_manager_http.py`
- Verify: `tests/test_agent_manager_web.py`
- Verify: `README.md`

- [ ] **Step 1: Run the complete automated suite**

Run:

```bash
uv run python -m unittest discover -s tests -p 'test_*.py'
```

Expected: all tests pass with zero failures and zero errors.

- [ ] **Step 2: Run packaging and whitespace verification**

Run:

```bash
uv build --wheel
git diff --check main...HEAD
git status --short --branch
```

Expected: wheel build succeeds, `git diff --check` is silent, and only expected build output is present. Remove only untracked build artifacts created by this verification after resolving their exact paths; do not delete user files.

- [ ] **Step 3: Audit scope and safety contracts**

Run:

```bash
git diff --stat main...HEAD
git diff main...HEAD -- \
  tools/agent_manager/skills.py \
  tools/agent_manager/cli.py \
  tools/agent_manager/server.py \
  tools/agent_manager/web/app.js \
  tools/agent_manager/web/index.html \
  tests/test_agent_manager.py \
  tests/test_agent_manager_http.py \
  tests/test_agent_manager_web.py \
  README.md
rg -n "INSTRUCTION_TARGETS|workbuddy|WorkBuddy" \
  tools/agent_manager tests README.md
```

Confirm all of the following:

- `workbuddy` appears in Skill tool enumeration but not `INSTRUCTION_TARGETS`;
- only `workbuddy-desktop` exists, with no `workbuddy-cli` detector or adapter;
- managed target is exactly `~/.workbuddy/skills/<slug>`;
- no WorkBuddy-specific overwrite/adoption path exists;
- no real HOME command or fixture path was used;
- unrelated files are unchanged.

- [ ] **Step 4: Invoke verification and review workflows**

Read and follow `superpowers:verification-before-completion`, then `superpowers:requesting-code-review`. Address only verified in-scope findings, rerun affected focused tests, and rerun the complete suite after any change.

- [ ] **Step 5: Prepare handoff without real HOME apply, merge, or push**

Report:

- branch and worktree path;
- commit list;
- exact full-suite pass count;
- wheel build and `git diff --check` result;
- confirmation that real `~/.workbuddy` was not modified;
- any residual risk around WorkBuddy version/path drift;
- the next independent authorization gate: previewing one non-conflicting Skill against real HOME.

Do not apply to real HOME, merge to `main`, rewrite history, or push unless the user separately requests that action.
