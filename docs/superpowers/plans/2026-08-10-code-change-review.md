# Code Change Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a discoverable `code-change-review` Skill that performs read-only, evidence-first review of implemented code changes and returns calibrated merge readiness.

**Architecture:** Keep orchestration, scope resolution, and the three cross-cutting reasoning rules in `SKILL.md`; place the detailed review dimensions and report schema in two references. Use repository-local `unittest` contract tests plus a self-contained JSON/fixture corpus for deterministic structure, routing, and behavior evaluation. Do not add runtime scripts, dependencies, shared modules, or cross-Skill file coupling.

**Tech Stack:** Markdown Skill instructions, YAML agent metadata, JSON eval manifest, Python 3.11 `unittest`, PyYAML, `uv`, Git.

## Global Constraints

- Work from an isolated `feature/code-change-review` branch and worktree created from the committed spec and plan.
- Treat the reviewed repository as read-only: do not mutate source, index, refs, PRs, issues, or external systems during review.
- Do not change `technical-proposal-review`; trigger separation is verified through the new Skill's description and eval corpus.
- Do not add dependencies, scripts, assets, README files, feedback storage, case history, automated fixes, or GitHub write operations.
- A `P0/P1` requires a concrete location, reachable failure path, actual impact, control/reversibility analysis, and direct remediation. Evidence gaps are `Q`, not confirmed findings.
- Run fresh-context evals only against disposable fixtures. Persist eval output outside the repository and delete nothing from the user's workspace.

---

## Task 0: Capture the behavioral RED baseline before writing the Skill

**Files:**

- Do not create or load `skills/code-change-review/SKILL.md` in this task.
- Keep raw baseline outputs in a temporary directory outside the repository.

### Step 1: Prepare raw bug/safe pressure scenarios

- [ ] Prepare the four bug/safe pairs defined in Task 2 as raw, self-contained review prompts. Each pair must differ by only one named control: transaction boundary, trusted identity re-injection, compatibility alias, or durable idempotency key.
- [ ] Give reviewers the changed code, baseline requirement, callers/consumers, and relevant tests, but do not provide expected findings, severity, or the planned Skill rules.

### Step 2: Run the eight baseline cases without the Skill

- [ ] Start a fresh reviewer context for each of the eight prompts without loading or naming `code-change-review`.
- [ ] Record model, case ID, raw output path, missed reachable-path assertions, false-positive `P0/P1`, scope mistakes, and whether questions were incorrectly emitted as confirmed findings.

Expected RED evidence: at least one missed bug assertion or one safe-control false positive. If all eight cases unexpectedly satisfy the planned assertions, stop and strengthen the scenarios before writing the Skill.

### Step 3: Extract only demonstrated failure patterns

- [ ] Summarize the baseline failure categories that the Skill must correct. Do not copy reviewer prose into the Skill and do not add rules for hypothetical failures absent from the baseline or approved design.

---

## Task 1: Add the contract tests and minimal Skill workflow

**Files:**

- Create: `tests/test_code_change_review_skill.py`
- Create: `skills/code-change-review/SKILL.md`
- Create: `skills/code-change-review/agents/openai.yaml`
- Create: `skills/code-change-review/references/review-rubric.md`
- Create: `skills/code-change-review/references/output-template.md`

### Step 1: Write the failing Skill contract tests

- [ ] Create `tests/test_code_change_review_skill.py` with the following initial contract:

```python
import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "code-change-review"


def load_frontmatter(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        raise AssertionError(f"missing YAML frontmatter: {path}")
    return yaml.safe_load(match.group(1)), text[match.end() :]


class CodeChangeReviewSkillTests(unittest.TestCase):
    def test_minimal_layout(self):
        required = {
            "SKILL.md",
            "agents/openai.yaml",
            "references/review-rubric.md",
            "references/output-template.md",
        }
        for relative in required:
            self.assertTrue((SKILL_ROOT / relative).is_file(), relative)

        forbidden = {"scripts", "assets", "README.md", "feedback", "cases"}
        self.assertFalse(forbidden.intersection({path.name for path in SKILL_ROOT.iterdir()}))

    def test_metadata_encodes_positive_and_negative_routing(self):
        frontmatter, _ = load_frontmatter(SKILL_ROOT / "SKILL.md")
        self.assertEqual(frontmatter["name"], "code-change-review")
        description = frontmatter["description"].lower()
        for phrase in (
            "working tree",
            "staged diff",
            "commit range",
            "branch",
            "pull request",
            "merge readiness",
        ):
            self.assertIn(phrase, description)
        for excluded in (
            "proposal",
            "reviewer comments",
            "debugging",
            "whole-repository",
            "implementation or fixes",
        ):
            self.assertIn(excluded, description)

        metadata = yaml.safe_load(
            (SKILL_ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
        )["interface"]
        self.assertIn("$code-change-review", metadata["default_prompt"])
        self.assertGreaterEqual(len(metadata["short_description"]), 25)
        self.assertLessEqual(len(metadata["short_description"]), 64)

    def test_workflow_contains_scope_readonly_and_reasoning_contracts(self):
        _, body = load_frontmatter(SKILL_ROOT / "SKILL.md")
        for phrase in (
            "Input precedence",
            "Deterministic snapshots",
            "Read-only safety gate",
            "First principles",
            "Adversarial review",
            "Evidence gate",
            "Merge readiness",
        ):
            self.assertIn(phrase, body)
        self.assertIn("references/review-rubric.md", body)
        self.assertIn("references/output-template.md", body)

    def test_output_contract_separates_findings_questions_and_readiness(self):
        template = (SKILL_ROOT / "references" / "output-template.md").read_text(
            encoding="utf-8"
        )
        for phrase in (
            "Confirmed findings",
            "P0-01",
            "P1-01",
            "P2-01",
            "Questions",
            "Q-01",
            "blocking",
            "non-blocking",
            "Unable to determine",
            "Ready with non-blocking follow-ups",
            "未发现有代码证据支持的缺陷",
        ):
            self.assertIn(phrase, template)


if __name__ == "__main__":
    unittest.main()
```

### Step 2: Run the focused test and confirm RED

- [ ] Run:

```bash
uv run python -m unittest tests.test_code_change_review_skill -v
```

Expected: failure because `skills/code-change-review/` does not exist.

### Step 3: Scaffold only the permitted Skill resources

- [ ] Run the system Skill Creator scaffold:

```bash
uv run python /Users/zhaoguodong/.codex/skills/.system/skill-creator/scripts/init_skill.py code-change-review \
  --path skills \
  --resources references \
  --interface 'display_name=代码变更评审' \
  --interface 'short_description=只读审查代码变更中的缺陷、回归风险、测试证据与合并就绪状态' \
  --interface 'default_prompt=Use $code-change-review to review the current code changes for evidence-backed defects, regressions, and merge readiness.'
```

Expected: the Skill root, `agents/openai.yaml`, and `references/` are created; no `scripts/` or `assets/` directories are created.

### Step 4: Implement the minimal orchestration contract

- [ ] Replace the generated `SKILL.md` with concise English instructions containing:

  1. The exact positive/negative routing boundary from the approved design.
  2. Input precedence and the five deterministic snapshot definitions.
  3. Required anchors: repository, branch/detached state, HEAD, base/head or working snapshot, excluded WIP, and requirement source.
  4. The read-only validation safety gate with pre/post state readback.
  5. Baseline reconstruction and impact tracing from diff to callers, state, protocol boundaries, side effects, and direct tests.
  6. Three always-on cross-cutting rules: first principles, risk-triggered adversarial review, and the unified evidence gate.
  7. Targeted verification states: verified, unverified, and not applicable.
  8. Severity and merge-readiness rules, including the separation of confirmed findings from questions.
  9. Explicit prohibition on implementation, index/ref mutation, fetch by default, PR comments, thread resolution, and external writes.

- [ ] Write `references/review-rubric.md` with these review dimensions:

  - observable behavior and requirements;
  - data semantics and state transitions;
  - error handling, retry, idempotency, transaction, concurrency, cancellation, and cleanup;
  - security and trust boundaries;
  - public API, event, schema, storage, migration, and mixed-version compatibility;
  - performance and resource lifetime when the changed path makes them relevant;
  - direct tests, observability, detection, containment, and recovery;
  - maintainability and YAGNI only where complexity creates a concrete change risk.

- [ ] Write `references/output-template.md` with a result-first report containing merge readiness, scope, confirmed findings, separate questions, verification, and coverage boundaries. Include a clean no-op path and all four readiness outcomes.

- [ ] Keep `agents/openai.yaml` limited to the three quoted `interface` fields generated above; do not declare tools or dependencies.

### Step 5: Run focused validation and confirm GREEN

- [ ] Run:

```bash
uv run python -m unittest tests.test_code_change_review_skill -v
uv run python /Users/zhaoguodong/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/code-change-review
git diff --check
```

Expected: 4/4 focused tests pass, Skill validation prints `Skill is valid!`, and `git diff --check` exits 0.

### Step 6: Commit the minimal Skill workflow

- [ ] Stage only the five Skill files and focused test, then commit:

```bash
git add tests/test_code_change_review_skill.py \
  skills/code-change-review/SKILL.md \
  skills/code-change-review/agents/openai.yaml \
  skills/code-change-review/references/review-rubric.md \
  skills/code-change-review/references/output-template.md
git commit -m 'feat(code-change-review): add evidence-first review workflow' \
  -m 'Add a read-only code change review Skill with deterministic scope anchoring, first-principles analysis, risk-triggered adversarial review, and one evidence gate. Keep detailed rubric and output structure in references so the entrypoint remains concise and independently installable.' \
  -m $'验证：\n- uv run python -m unittest tests.test_code_change_review_skill -v\n- uv run python /Users/zhaoguodong/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/code-change-review\n- git diff --check\n\nCo-authored-by: OpenAI Codex <noreply@openai.com>'
```

---

## Task 2: Add the self-contained trigger and behavior eval corpus

**Files:**

- Modify: `tests/test_code_change_review_skill.py`
- Create: `skills/code-change-review/evals/evals.json`
- Create: `skills/code-change-review/evals/fixtures/dual-write-bug.md`
- Create: `skills/code-change-review/evals/fixtures/dual-write-safe.md`
- Create: `skills/code-change-review/evals/fixtures/auth-boundary-bug.md`
- Create: `skills/code-change-review/evals/fixtures/auth-boundary-safe.md`
- Create: `skills/code-change-review/evals/fixtures/compatibility-bug.md`
- Create: `skills/code-change-review/evals/fixtures/compatibility-safe.md`
- Create: `skills/code-change-review/evals/fixtures/retry-idempotency-bug.md`
- Create: `skills/code-change-review/evals/fixtures/retry-idempotency-safe.md`
- Create: `skills/code-change-review/evals/fixtures/empty-range.md`
- Create: `skills/code-change-review/evals/fixtures/low-risk-refactor.md`
- Create: `skills/code-change-review/evals/fixtures/out-of-scope-wip.md`
- Create: `skills/code-change-review/evals/fixtures/external-unavailable.md`

### Step 1: Extend the contract test and confirm RED

- [ ] Add these imports and tests to `tests/test_code_change_review_skill.py`:

```python
import json


    def test_eval_manifest_has_fixed_case_matrix_and_valid_fixtures(self):
        manifest = json.loads(
            (SKILL_ROOT / "evals" / "evals.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["skill_name"], "code-change-review")
        evals = manifest["evals"]
        self.assertEqual(len(evals), 24)
        self.assertEqual(len({case["id"] for case in evals}), 24)

        required = {"id", "kind", "prompt", "expected_output", "files", "assertions"}
        for case in evals:
            self.assertTrue(required.issubset(case), case["id"])
            self.assertIn(case["kind"], {"trigger", "behavior"})
            self.assertTrue(case["assertions"], case["id"])
            for relative in case["files"]:
                fixture = (SKILL_ROOT / relative).resolve()
                self.assertTrue(fixture.is_relative_to(SKILL_ROOT.resolve()), case["id"])
                self.assertTrue(fixture.is_file(), f"{case['id']}: {relative}")

        triggers = [case for case in evals if case["kind"] == "trigger"]
        behavior = [case for case in evals if case["kind"] == "behavior"]
        self.assertEqual(len(triggers), 12)
        self.assertEqual(len(behavior), 12)
        self.assertEqual(
            {case["route"] for case in triggers},
            {"code-change-review", "other-skill", "mixed"},
        )
        self.assertEqual(
            [case["route"] for case in triggers].count("code-change-review"), 5
        )
        self.assertEqual([case["route"] for case in triggers].count("other-skill"), 5)
        self.assertEqual([case["route"] for case in triggers].count("mixed"), 2)

        categories = [case["category"] for case in behavior]
        self.assertEqual(categories.count("bug"), 4)
        self.assertEqual(categories.count("safe"), 4)
        self.assertEqual(categories.count("control"), 4)
        bug_ids = {case["id"] for case in behavior if case["category"] == "bug"}
        safe_controls = {
            case["control_for"] for case in behavior if case["category"] == "safe"
        }
        self.assertEqual(safe_controls, bug_ids)
```

- [ ] Run:

```bash
uv run python -m unittest tests.test_code_change_review_skill -v
```

Expected: the new eval-manifest test fails because `evals/evals.json` is absent.

### Step 2: Create the 12 trigger cases

- [ ] Create `evals/evals.json` with top-level keys `skill_name` and `evals`. Add these stable trigger IDs:

  - Positive route: `trigger-positive-current-branch`, `trigger-positive-pr`, `trigger-positive-staged`, `trigger-positive-commit-range`, `trigger-positive-working-tree`.
  - Negative route: `trigger-negative-proposal`, `trigger-negative-comments`, `trigger-negative-debug`, `trigger-negative-audit`, `trigger-negative-implement`.
  - Mixed route: `trigger-mixed-code-primary`, `trigger-mixed-dual-review`.

- [ ] Every trigger case must have `kind: "trigger"`, a `route` value, no fixture files, and assertions that identify actual Skill selection rather than matching final prose. The five negative cases must name the expected alternative workflow in `expected_output`.

### Step 3: Create four bug/safe fixture pairs

- [ ] Each fixture must be self-contained Markdown with requirement, baseline, changed code or diff, consumer/caller context, relevant test/control evidence, and review scope. Keep each pair identical except for one named control:

  1. `dual-write-bug.md` / `dual-write-safe.md`: transaction boundary is the only material difference.
  2. `auth-boundary-bug.md` / `auth-boundary-safe.md`: trusted identity re-injection after client-data merging is the only material difference.
  3. `compatibility-bug.md` / `compatibility-safe.md`: legacy field alias or mixed-version compatibility adapter is the only material difference.
  4. `retry-idempotency-bug.md` / `retry-idempotency-safe.md`: durable idempotency key check is the only material difference.

- [ ] Add eight behavior entries with `category: "bug"` or `category: "safe"`. Each safe entry must set `control_for` to its paired bug ID. Assertions must require the exact reachable path for bugs and 0 `P0/P1` plus explicit control recognition for safe cases.

### Step 4: Create the four scope/evidence controls

- [ ] Add fixtures and manifest entries for:

  - `behavior-empty-range`: no changed lines; require clean no-op and 0 confirmed findings.
  - `behavior-low-risk-refactor`: behavior-preserving rename with direct tests; require 0 `P0/P1`.
  - `behavior-out-of-scope-wip`: commit range plus unrelated working-tree edit; require explicit exclusion of WIP.
  - `behavior-external-unavailable`: direct code evidence remains reviewable but an external integration cannot run; require separation of code conclusion from unverified runtime evidence.

- [ ] Give all four `category: "control"` and assertions for scope, evidence status, and merge readiness.

### Step 5: Validate the complete corpus

- [ ] Run:

```bash
uv run python -m unittest tests.test_code_change_review_skill -v
python -m json.tool skills/code-change-review/evals/evals.json >/dev/null
uv run python /Users/zhaoguodong/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/code-change-review
git diff --check
```

Expected: 5/5 focused tests pass, JSON parses, all 12 fixture paths resolve, Skill validation passes, and whitespace validation exits 0.

### Step 6: Commit the eval corpus

- [ ] Stage only the contract-test and eval files, then commit:

```bash
git add tests/test_code_change_review_skill.py skills/code-change-review/evals
git commit -m 'test(code-change-review): add routing and behavior eval corpus' \
  -m 'Add deterministic trigger coverage and paired behavioral fixtures so evidence calibration, scope isolation, and safe-control recognition can be reviewed without production repositories or hidden expectations.' \
  -m $'验证：\n- uv run python -m unittest tests.test_code_change_review_skill -v\n- python -m json.tool skills/code-change-review/evals/evals.json\n- uv run python /Users/zhaoguodong/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/code-change-review\n- git diff --check\n\nCo-authored-by: OpenAI Codex <noreply@openai.com>'
```

---

## Task 3: Run fresh-context behavior, routing, and read-only evaluations

**Files:**

- Read: `skills/code-change-review/evals/evals.json`
- Read: `skills/code-change-review/evals/fixtures/*.md`
- Do not create persistent repository files for raw eval output.

### Step 1: Compare GREEN results with the pre-Skill RED baseline

- [ ] Compare the eight paired behavior results with Task 0's raw baseline records.

Expected: every demonstrated baseline failure category is either corrected by the Skill or explicitly documented as an unresolved eval failure; do not claim improvement from wording alone.

### Step 2: Run all behavior cases in fresh contexts

- [ ] For each of the 12 behavior entries, start a fresh reviewer context, explicitly load `$code-change-review`, provide only the fixture and prompt, and grade the raw response against that case's `assertions`.
- [ ] Record model, Skill commit, case ID, each assertion pass/fail, and raw output in a temporary directory outside the repository.

Expected: 12/12 cases pass; all four bug paths are found, all four safe controls have 0 `P0/P1`, and all four scope/evidence controls satisfy their isolation rules.

### Step 3: Run all routing cases in fresh contexts

- [ ] For each of the 12 trigger entries, start a fresh context without explicitly naming a Skill. Determine routing from the actual Skill/tool loading record.

Expected: 5/5 positive routes load `code-change-review`; 5/5 negative routes do not; both mixed cases follow the declared primary-object or dual-review behavior.

### Step 4: Verify read-only behavior on disposable fixtures

- [ ] Before and after representative bug, safe, scope, and external-unavailable cases, compare `HEAD`, refs, index, tracked state, and non-ignored untracked state.

Expected: 4/4 representative runs leave all reviewed state unchanged; only ignored caches explicitly allowed by a fixture may differ.

### Step 5: Run one blinded forward test

- [ ] Select one real but de-identified commit range not used in the fixtures. Give a fresh reviewer only the range and its requirement, not the expected result. Grade the raw output for scope anchoring, evidence, severity calibration, readiness, and read-only behavior.

Expected: all five contract areas pass. A clean result is acceptable; do not require a finding.

---

## Task 4: Independent review and repository-wide verification

**Files:**

- Review: all branch changes relative to the committed plan baseline.
- Modify only files already listed above if review finds a proven defect.

### Step 1: Request an independent code/Skill review

- [ ] Use `superpowers:requesting-code-review` with the approved design, implementation plan, branch base SHA, and branch head SHA.
- [ ] Require the reviewer to check trigger boundaries, read-only guarantees, evidence/readiness consistency, paired safe controls, and unnecessary machinery.

Expected: no unresolved P0/P1 findings. Verify every suggested issue against the repository before changing code.

### Step 2: Run focused and full verification

- [ ] Run:

```bash
uv run python -m unittest tests.test_code_change_review_skill -v
uv run python /Users/zhaoguodong/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/code-change-review
python -m json.tool skills/code-change-review/evals/evals.json >/dev/null
uv run python -m unittest discover -s tests -v
uv lock --check
uv build
git diff --check
git status --short --branch
```

Expected: focused tests, full tests, lock validation, package build, Skill validation, JSON validation, and whitespace checks pass. The final status contains only intentional branch commits and no uncommitted files.

### Step 3: Reconcile implementation against the design

- [ ] Confirm all eight design completion criteria have current evidence: discovery/frontmatter, trigger separation, 12 behavior cases, evidence-gated `P0/P1`, safe/empty controls, read-only verification, repository checks, and one fresh-context forward test.
- [ ] Confirm there are no changes to `technical-proposal-review`, no new dependency, and no forbidden directory or automation.

### Step 4: Prepare the handoff without publishing

- [ ] Report branch/worktree, commit list, exact verification counts, eval pass counts, independent-review outcome, and any unverified boundary.
- [ ] Do not merge, push, create a PR, tag, release, or remove the worktree without separate user authorization.
