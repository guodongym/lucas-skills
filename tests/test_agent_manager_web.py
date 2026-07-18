from __future__ import annotations

import json
import subprocess
import unittest
from html.parser import HTMLParser
from pathlib import Path


WEB_ROOT = Path("tools/agent_manager/web")


class ShellParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.start_tags: list[tuple[str, dict[str, str | None]]] = []
        self.inline_script_bodies: list[str] = []
        self._inline_script = False

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        values = dict(attrs)
        self.start_tags.append((tag, values))
        if tag == "script" and "src" not in values:
            self._inline_script = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self._inline_script = False

    def handle_data(self, data: str) -> None:
        if self._inline_script and data.strip():
            self.inline_script_bodies.append(data)


class WebPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.page = (WEB_ROOT / "index.html").read_text(encoding="utf-8")
        css_path = WEB_ROOT / "app.css"
        javascript_path = WEB_ROOT / "app.js"
        cls.css = css_path.read_text(encoding="utf-8") if css_path.exists() else ""
        cls.javascript = (
            javascript_path.read_text(encoding="utf-8")
            if javascript_path.exists()
            else ""
        )
        cls.parser = ShellParser()
        cls.parser.feed(cls.page)

    @staticmethod
    def _run_exports(expression: str) -> object:
        script_path = json.dumps(str(WEB_ROOT / "app.js"))
        completed = subprocess.run(
            [
                "node",
                "-e",
                (
                    "const fs = require('fs'); const vm = require('vm');"
                    "globalThis.__AGENT_MANAGER_TEST__ = true;"
                    f"vm.runInThisContext(fs.readFileSync({script_path}, 'utf8'));"
                    f"console.log(JSON.stringify({expression}));"
                ),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return json.loads(completed.stdout)

    @staticmethod
    def _run_async_exports(expression: str) -> object:
        script_path = json.dumps(str(WEB_ROOT / "app.js"))
        completed = subprocess.run(
            [
                "node",
                "-e",
                (
                    "const fs = require('fs'); const vm = require('vm');"
                    "globalThis.__AGENT_MANAGER_TEST__ = true;"
                    f"vm.runInThisContext(fs.readFileSync({script_path}, 'utf8'));"
                    f"(async () => console.log(JSON.stringify(await ({expression}))))()"
                    ".catch(error => { console.error(error); process.exitCode = 1; });"
                ),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return json.loads(completed.stdout)

    def test_shell_has_external_assets_and_accessible_information_architecture(self) -> None:
        tags = self.parser.start_tags
        self.assertEqual(sum(tag == "main" for tag, _ in tags), 1)
        self.assertEqual(
            sum(attrs.get("aria-live") == "polite" for _, attrs in tags),
            1,
        )
        self.assertFalse(any(tag == "style" for tag, _ in tags))
        self.assertEqual(self.parser.inline_script_bodies, [])
        self.assertTrue(
            any(tag == "link" and attrs.get("href") == "/app.css" for tag, attrs in tags)
        )
        self.assertTrue(
            any(tag == "script" and attrs.get("src") == "/app.js" for tag, attrs in tags)
        )
        self.assertTrue(
            any(
                tag == "meta"
                and attrs.get("name") == "viewport"
                and "width=device-width" in (attrs.get("content") or "")
                for tag, attrs in tags
            )
        )
        self.assertTrue(
            any(
                tag == "meta"
                and attrs.get("name") == "agent-manager-token"
                and attrs.get("content") == "__AGENT_MANAGER_TOKEN__"
                for tag, attrs in tags
            )
        )
        for label in ("总览", "Skills", "个人约束", "全局库存"):
            self.assertIn(label, self.page)
        for element_id in (
            "overview-view",
            "skills-view",
            "instructions-view",
            "inventory-view",
            "status-summary",
            "topology-board",
            "attention-list",
            "skills-table",
            "instructions-list",
            "inventory-table",
            "details-drawer",
            "confirmation-dialog",
            "toast-region",
            "shutdown-button",
        ):
            self.assertIn(f'id="{element_id}"', self.page)
        nav_controls = [
            attrs
            for tag, attrs in tags
            if tag == "button" and attrs.get("data-view")
        ]
        self.assertEqual(
            {attrs["data-view"] for attrs in nav_controls},
            {"overview", "skills", "instructions", "inventory"},
        )
        self.assertTrue(all(attrs.get("type") == "button" for attrs in nav_controls))

    def test_skill_details_guidance_names_the_status_cell_entry_point(self) -> None:
        self.assertIn("点击工具状态格查看完整路径、说明和操作。", self.page)
        self.assertNotIn("选择一行可查看各工具的完整路径与服务端说明。", self.page)

    def test_shell_is_self_contained_and_server_strings_are_not_inserted_as_html(self) -> None:
        for source in (self.page, self.css):
            self.assertNotIn("http://", source)
            self.assertNotIn("https://", source)
        self.assertNotIn('fetch("http://', self.javascript)
        self.assertNotIn('fetch("https://', self.javascript)
        self.assertNotIn("innerHTML", self.javascript)
        for primitive in ("createElement", "textContent", "setAttribute", "addEventListener"):
            self.assertIn(primitive, self.javascript)

    def test_visual_system_matches_approved_tokens_and_accessibility_contracts(self) -> None:
        for color in (
            "#0052D9", "#366EF4", "#F2F3FF",
            "#F3F3F3", "#E7E7E7", "#DCDCDC", "#181818", "#4B4B4B", "#5E5E5E",
            "#2BA471", "#006C45", "#E3F9E9",
            "#E37318", "#954500", "#FFF1E9",
            "#D54941", "#B11F1F", "#FFF0ED",
            "#EEEEEE", "#0B1F3A",
        ):
            self.assertIn(color, self.css)
        for retired in ("#F4F6F8", "#171A1F", "#69717D", "#2563EB", "#16825D", "#B86B12"):
            self.assertNotIn(retired, self.css)
        for typeface in ("Avenir Next", "system-ui", "SFMono-Regular"):
            self.assertIn(typeface, self.css)
        for contract in (
            ":focus-visible",
            "@media (max-width: 1160px)",
            "@media (max-width: 800px)",
            "@media (max-width: 720px)",
            "@media (prefers-reduced-motion: reduce)",
            "thead th",
            "tbody th",
            "position: sticky",
            "240px",
            "88px",
            "180ms",
        ):
            self.assertIn(contract, self.css)
        for shadow_token in ("--shadow-1:", "--shadow-2:", "--shadow-3:"):
            self.assertIn(shadow_token, self.css)
        self.assertRegex(
            self.css,
            r"\.status-value \{[^}]*font-size: 36px;",
        )
        self.assertIn("font-variant-numeric: tabular-nums", self.css)
        self.assertNotIn("backdrop-filter", self.css)
        self.assertIn("scroll-hint", self.css)
        self.assertRegex(
            self.css,
            r"\.route-channel \{(?:.|\n)*?min-width: 0;",
        )
        self.assertRegex(
            self.css,
            r"\.source-node \{[^}]*min-width: 0;",
        )
        self.assertRegex(
            self.css,
            r"\.repository-bar \{[^}]*flex-wrap: wrap;",
        )
        self.assertRegex(
            self.css,
            r"@media \(max-width: 800px\) \{[^@]*\.route-node \{ grid-template-columns: 1fr; \}",
        )
        self.assertIn(".route-list::before {", self.css)
        self.assertIn(".route-node::before { border-top: 2px solid var(--panel-line-ok);", self.css)
        self.assertIn(".route-node::after { border-top: 2px dashed var(--panel-line-ok);", self.css)

    def test_routing_board_is_semantic_content_without_decorative_svg(self) -> None:
        topology = next(
            (tag, attrs)
            for tag, attrs in self.parser.start_tags
            if attrs.get("id") == "topology-board"
        )
        self.assertEqual(topology[0], "figure")
        self.assertNotEqual(topology[1].get("role"), "img")
        self.assertNotIn("topology-lines", self.page)
        self.assertIn('node("ul", null, "route-list")', self.javascript)
        self.assertIn("route-node-${channel}-${status}", self.javascript)
        self.assertIn('setAttribute("aria-label"', self.javascript)

    def test_navigation_icons_are_inline_svg_with_semantic_generation(self) -> None:
        icons = self._run_exports("AgentManagerTest.NAV_ICONS")
        self.assertEqual(
            set(icons),
            {"overview", "skills", "instructions", "inventory"},
        )
        self.assertTrue(all(isinstance(d, str) and d for d in icons.values()))
        self.assertIn(
            'document.createElementNS("http://www.w3.org/2000/svg"',
            self.javascript,
        )
        self.assertIn('svg.setAttribute("aria-hidden", "true")', self.javascript)

    def test_button_hierarchy_defines_primary_text_and_solid_danger(self) -> None:
        self.assertIn('node("button", "确认执行", "primary-action")', self.javascript)
        for contract in (".primary-action {", "#danger-apply-button {", ".text-action {"):
            self.assertIn(contract, self.css)
        self.assertRegex(self.css, r"\.primary-action \{[^}]*background: var\(--brand\);")
        self.assertRegex(
            self.css,
            r"#danger-apply-button \{[^}]*background: var\(--error-text\);",
        )
        self.assertIn('class="text-action"', self.page)

    def test_repository_path_shortens_home_prefix_with_full_title(self) -> None:
        self.assertEqual(
            self._run_exports(
                "AgentManagerTest.repositoryHome("
                "{skills:{adapters:[{home:'/Users/test'},{home:'/Users/other'}]}})"
            ),
            "/Users/test",
        )
        self.assertEqual(self._run_exports("AgentManagerTest.repositoryHome({})"), "")
        self.assertIn(
            "appendRepositoryPath(payload.repo_root, repositoryHome(payload))",
            self.javascript,
        )
        self.assertIn("target.textContent = compactHomePath(path, home)", self.javascript)

    def test_state_presentation_separates_error_states_from_pending_states(self) -> None:
        cases = {
            "enabled": ["已启用", "state-enabled"],
            "partial": ["部分启用", "state-partial"],
            "conflict": ["冲突", "state-attention"],
            "legacy": ["旧链接", "state-attention"],
            "error": ["异常", "state-error"],
            "broken": ["链接损坏", "state-error"],
            "disabled": ["未启用", "state-muted"],
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(
                    self._run_exports(
                        f"AgentManagerTest.statePresentation({json.dumps(value)})"
                    ),
                    expected,
                )

    def test_status_badges_use_light_backgrounds_with_deep_text(self) -> None:
        for contract in (
            ".state-enabled { background: var(--success-light); color: var(--success-text); }",
            ".state-attention { background: var(--warning-light); color: var(--warning-text); }",
            ".state-error { background: var(--error-light); color: var(--error-text); }",
            ".state-partial { background: var(--warning-light); color: var(--warning-text); }",
            ".state-muted { background: var(--neutral-light); color: var(--muted); }",
            ".status-badge-healthy { background: var(--success-light); color: var(--success-text); }",
            ".status-badge-attention { background: var(--warning-light); color: var(--warning-text); }",
            ".source-managed { background: var(--brand-light); color: var(--brand); }",
            ".source-broken { background: var(--error-light); color: var(--error-text); }",
        ):
            self.assertIn(contract, self.css)
        self.assertRegex(self.css, r"\.state-text \{[^}]*border-radius: 3px;")
        self.assertRegex(self.css, r"\.state-text \{[^}]*font-size: 12px;")
        self.assertRegex(
            self.css,
            r"\.route-status-button:hover[^{]*\{[^}]*box-shadow: var\(--shadow-1\);",
        )

    def test_server_messages_render_with_chinese_labels(self) -> None:
        cases = {
            "direct repository link": "已直接链接到仓库",
            "target differs from repository source": "内容与仓库源不一致",
            "link resolves through another entry": "经其他入口间接链接到仓库",
            "surface not installed": "未检测到该工具",
            "target is absent": "目标不存在",
            "unmapped server message": "unmapped server message",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(
                    self._run_exports(
                        f"AgentManagerTest.messageLabel({json.dumps(raw)})"
                    ),
                    expected,
                )

    def test_attention_entries_are_deduplicated_with_view_links(self) -> None:
        self.assertNotIn(
            'records.push({ label: payload.code || "状态异常", message: payload.message });',
            self.javascript,
        )
        self.assertIn('view: "instructions"', self.javascript)
        self.assertIn('view: "skills"', self.javascript)
        self.assertIn(
            "if (!records.some((record) => record.message === topMessage))",
            self.javascript,
        )

    def test_attention_records_carry_jump_anchors_only_for_target_rows(self) -> None:
        payload = {
            "ok": True,
            "skills": {
                "issues": [
                    {
                        "code": "scan-issue",
                        "message": "broken skill dir",
                        "path": "/repo/skills/broken",
                    }
                ],
                "targets": [
                    {
                        "slug": "docx",
                        "tool": "codex",
                        "state": "conflict",
                        "message": "target differs from repository source",
                    },
                    {
                        "slug": "pdf",
                        "tool": "codex",
                        "state": "enabled",
                        "message": "direct repository link",
                    },
                ],
            },
            "instructions": {
                "issues": [
                    {
                        "code": "source-missing",
                        "message": "instruction source missing",
                        "path": "/repo/AGENTS.md",
                    }
                ],
                "targets": [
                    {"key": "codex", "state": "broken", "message": "broken symlink"},
                ],
            },
        }
        records = self._run_exports(
            f"AgentManagerTest.collectAttention({json.dumps(payload)})"
        )
        by_label = {record["label"]: record for record in records}
        self.assertNotIn("view", by_label["Skill 扫描 · scan-issue"])
        self.assertNotIn("view", by_label["个人约束扫描 · source-missing"])
        self.assertEqual(
            by_label["Skill 扫描 · scan-issue"]["path"], "/repo/skills/broken"
        )
        self.assertEqual(
            by_label["个人约束扫描 · source-missing"]["path"], "/repo/AGENTS.md"
        )
        self.assertIn(
            'appendPath(copy, record.path, "path-text attention-path")',
            self.javascript,
        )
        skill_record = by_label["Skill · docx · Codex"]
        self.assertEqual(skill_record["view"], "skills")
        self.assertEqual(skill_record["slug"], "docx")
        instruction_record = by_label["个人约束 · codex"]
        self.assertEqual(instruction_record["view"], "instructions")
        self.assertEqual(instruction_record["key"], "codex")

    def test_attention_jump_presets_filters_and_highlights_landing_row(self) -> None:
        self.assertIn("function jumpToAttentionTarget(", self.javascript)
        self.assertIn(
            'document.getElementById("skill-state-filter").value = "attention"',
            self.javascript,
        )
        self.assertIn(
            'document.getElementById("skill-query").value = record.slug || ""',
            self.javascript,
        )
        self.assertIn("jump-highlight", self.javascript)
        self.assertIn("scrollIntoView", self.javascript)
        self.assertIn("jumpToAttentionTarget(record)", self.javascript)
        self.assertIn(".jump-highlight", self.css)

    def test_nonzero_summary_numbers_anchor_to_the_attention_list(self) -> None:
        self.assertIn("function focusAttentionList(", self.javascript)
        self.assertIn('addEventListener("click", focusAttentionList)', self.javascript)
        self.assertIn("查看需要处理列表", self.javascript)
        self.assertIn(".status-value-button", self.css)

    def test_instruction_row_actions_match_server_semantics_per_state(self) -> None:
        cases = {
            "enabled": (["disable"], None),
            "missing": (["enable"], None),
            "indirect-link": (["adopt"], None),
            "matching-copy": (["adopt"], None),
            "conflict": (["resolve"], None),
            "broken": (["resolve"], None),
            "manual": ([], None),
        }
        for state, (kinds, note) in cases.items():
            with self.subTest(state=state):
                result = self._run_exports(
                    "AgentManagerTest.instructionRowActions("
                    f"{json.dumps(state)}, 'link cannot be resolved')"
                )
                self.assertEqual([a["kind"] for a in result["actions"]], kinds)
                self.assertEqual(result["note"], note)

    def test_instruction_row_actions_block_unsupported_targets(self) -> None:
        for message, note in (
            ("target is a directory", "目录不支持接管"),
            ("target is a special file", "特殊文件不支持接管"),
        ):
            with self.subTest(message=message):
                result = self._run_exports(
                    "AgentManagerTest.instructionRowActions("
                    f"'conflict', {json.dumps(message)})"
                )
                self.assertEqual(result["actions"], [])
                self.assertEqual(result["note"], note)

    def test_duplicate_groups_fall_back_to_slug_when_name_is_missing(self) -> None:
        result = self._run_exports(
            "AgentManagerTest.inventorySummary(["
            "{slug:'a',name:null,source_type:'plugin',flags:['duplicate-name']},"
            "{slug:'a',name:null,source_type:'plugin',flags:['duplicate-name']},"
            "{slug:'b',name:'b',source_type:'plugin',flags:[]}"
            "], [])"
        )
        self.assertEqual(result["duplicateGroups"], 1)
        self.assertEqual(result["flagged"], 2)

    def test_inventory_refresh_failure_preserves_cached_records(self) -> None:
        self.assertEqual(
            self._run_exports("typeof AgentManagerTest.inventoryFailureMode"),
            "function",
        )
        self.assertEqual(
            self._run_exports("AgentManagerTest.inventoryFailureMode(true)"),
            "stale",
        )
        self.assertEqual(
            self._run_exports("AgentManagerTest.inventoryFailureMode(false)"),
            "empty",
        )
        self.assertIn(
            'if (inventoryFailureMode(state.inventoryLoaded) === "stale")',
            self.javascript,
        )
        self.assertIn("以下为上次成功扫描的结果", self.javascript)
        self.assertIn("（数据可能过期）", self.javascript)
        self.assertIn("inventory-name-repeat-prefix", self.javascript)

    def test_switching_views_closes_the_details_drawer(self) -> None:
        switch_view = self.javascript.split("function switchView(view) {", 1)[1]
        self.assertIn("closeDrawer();", switch_view.split("}", 3)[0])

    def test_topology_targets_attention_color_to_the_matching_channel(self) -> None:
        self.assertEqual(
            self._run_exports(
                "typeof AgentManagerTest.routeNodeClass"
            ),
            "function",
        )
        cases = (
            (
                "{skills:{status:'attention'},instructions:{status:'muted'}}",
                "route-node route-node-skills-attention route-node-instructions-muted",
            ),
            (
                "{skills:{status:'healthy'},instructions:{status:'attention'}}",
                "route-node route-node-instructions-attention",
            ),
            (
                "{skills:{status:'attention'},instructions:{status:'attention'}}",
                "route-node route-node-skills-attention route-node-instructions-attention",
            ),
            (
                "{skills:{status:'partial'},instructions:{status:'healthy'}}",
                "route-node route-node-skills-partial",
            ),
        )
        for route, expected in cases:
            with self.subTest(route=route):
                self.assertEqual(
                    self._run_exports(
                        f"AgentManagerTest.routeNodeClass({route})"
                    ),
                    expected,
                )
        self.assertIn(".route-node::before { border-top: 2px solid var(--panel-line-ok);", self.css)
        self.assertIn(".route-node::after { border-top: 2px dashed var(--panel-line-ok);", self.css)
        self.assertIn(
            ".route-node-skills-attention::before { border-top-color: var(--panel-line-warn); }",
            self.css,
        )
        self.assertIn(
            ".route-node-instructions-attention::after { border-top-color: var(--panel-line-warn); }",
            self.css,
        )
        self.assertIn(
            ".route-node-skills-muted::before { border-top-color: var(--panel-muted); }",
            self.css,
        )
        self.assertIn(
            ".route-node-instructions-muted::after { border-top-color: var(--panel-muted); }",
            self.css,
        )
        self.assertIn(
            ".route-node-skills-partial::before { border-top-color: var(--panel-line-warn); }",
            self.css,
        )
        self.assertIn(
            ".route-node-instructions-partial::after { border-top-color: var(--panel-line-warn); }",
            self.css,
        )
        self.assertIn(".route-channel.line-dashed::before { border-top-style: dashed; }", self.css)

    def test_topology_panel_is_dark_with_dedicated_focus_and_badge_tokens(self) -> None:
        self.assertRegex(self.css, r"\.topology-board \{[^}]*background: var\(--panel-deep\);")
        self.assertRegex(self.css, r"\.topology-board \{[^}]*border-radius: 12px;")
        self.assertRegex(self.css, r"\.topology-board \{[^}]*padding: 32px;")
        self.assertRegex(
            self.css,
            r"\.topology-board :focus-visible \{[^}]*"
            r"outline: 2px solid var\(--focus-ring-dark\);",
        )
        for contract in (
            ".route-channel.status-healthy { color: var(--panel-line-ok); }",
            ".route-channel.status-attention { color: var(--panel-line-warn); }",
            ".route-channel.status-muted { color: var(--panel-muted); }",
            "rgba(86, 192, 141, 0.16)",
            "rgba(250, 149, 80, 0.16)",
        ):
            self.assertIn(contract, self.css)

    def test_bootstrap_exposes_server_truth_renderers_and_guarded_write_routes(self) -> None:
        for function_name in (
            "loadStatus",
            "renderOverview",
            "renderSkills",
            "renderInstructions",
            "renderInventory",
        ):
            self.assertIn(f"function {function_name}(", self.javascript)
        self.assertIn('fetch("/api/status"', self.javascript)
        self.assertIn('fetch("/api/inventory"', self.javascript)
        for route in (
            "/api/skills/set",
            "/api/skills/adopt",
            "/api/instructions/set",
            "/api/instructions/adopt",
            "/api/shutdown",
        ):
            self.assertIn(route, self.javascript)
        self.assertNotIn("Promise.all", self.javascript)
        self.assertIn("tokenMeta.remove()", self.javascript)
        self.assertIn("scanned_at", self.javascript)
        self.assertIn(".title =", self.javascript)
        self.assertIn('["Skills（至少一处）"', self.javascript)

    def test_contextual_request_builders_preserve_exact_preview_intent_for_apply(self) -> None:
        requests = self._run_exports(
            "(() => {"
            "const single = AgentManagerTest.buildSkillRequest("
            "{kind:'set', skill:'docx', tool:'codex', on:true}, false);"
            "const bulk = AgentManagerTest.buildSkillRequest("
            "{kind:'set', skill:null, tool:'all', on:false}, false);"
            "const skillAdopt = AgentManagerTest.buildSkillRequest({kind:'adopt'}, false);"
            "const instructionSet = AgentManagerTest.buildInstructionRequest("
            "'codex', {kind:'set', on:true}, false, null);"
            "const instructionAdopt = AgentManagerTest.buildInstructionRequest("
            "null, {kind:'adopt', replaceExisting:false}, false, null);"
            "const replacePreview = AgentManagerTest.buildInstructionRequest("
            "null, {kind:'adopt', replaceExisting:true}, false, null);"
            "return { single, bulk, skillAdopt, instructionSet, instructionAdopt, "
            "replacePreview, replacementApply: AgentManagerTest.buildApplyRequest("
            "replacePreview, {fingerprint:'a'.repeat(64)}) }; })()"
        )
        self.assertEqual(
            requests["single"],
            {"path": "/api/skills/set", "body": {
                "skill": "docx", "all": False, "tool": "codex",
                "on": True, "apply": False,
            }},
        )
        self.assertEqual(
            requests["bulk"],
            {"path": "/api/skills/set", "body": {
                "skill": None, "all": True, "tool": "all",
                "on": False, "apply": False,
            }},
        )
        self.assertEqual(
            requests["skillAdopt"],
            {"path": "/api/skills/adopt", "body": {"apply": False}},
        )
        self.assertEqual(
            requests["instructionSet"],
            {"path": "/api/instructions/set", "body": {
                "target": "codex", "on": True, "apply": False,
                "expected_fingerprint": None,
            }},
        )
        self.assertEqual(
            requests["instructionAdopt"],
            {"path": "/api/instructions/adopt", "body": {
                "apply": False, "replace_existing": False,
                "expected_fingerprint": None,
            }},
        )
        self.assertTrue(requests["replacePreview"]["body"]["replace_existing"])
        self.assertEqual(
            requests["replacementApply"],
            {"path": "/api/instructions/adopt", "body": {
                "apply": True, "replace_existing": True,
                "expected_fingerprint": "a" * 64,
            }},
        )

    def test_replace_apply_requires_a_successful_server_replace_preview(self) -> None:
        result = self._run_exports(
            "(() => { const blocked = {ok:false, code:'target-conflict', changes:["
            "{action:'blocked', target:'/tmp/occupied'}]};"
            "const replaced = {ok:true, fingerprint:'b'.repeat(64), snapshot_path:'/tmp/snapshot',"
            "changes:[{action:'replace', target:'/tmp/occupied'}]};"
            "return {blocked: AgentManagerTest.dangerPreviewModel(blocked),"
            "replaced: AgentManagerTest.dangerPreviewModel(replaced)}; })()"
        )
        self.assertIsNone(result["blocked"])
        self.assertEqual(result["replaced"]["fingerprint"], "b" * 64)
        self.assertEqual(result["replaced"]["changes"][0]["action"], "replace")
        self.assertEqual(result["replaced"]["snapshotPath"], "/tmp/snapshot")

    def test_drawer_and_dialog_have_complete_keyboard_focus_contracts(self) -> None:
        for function_name in (
            "openDrawer", "closeDrawer", "openDangerDialog", "closeDangerDialog",
            "trapModalFocus",
        ):
            self.assertIn(f"function {function_name}(", self.javascript)
        self.assertIn("document.activeElement", self.javascript)
        self.assertIn("previousDrawerFocus", self.javascript)
        self.assertIn("previousDialogFocus", self.javascript)
        self.assertIn('event.key === "Escape"', self.javascript)
        self.assertIn('event.key !== "Tab"', self.javascript)
        self.assertIn("focusableControls", self.javascript)
        self.assertIn("controls[0].focus()", self.javascript)
        self.assertIn("restoreCapturedFocus(previousDrawerFocus, document)", self.javascript)
        self.assertIn("restoreCapturedFocus(previousDialogFocus, document)", self.javascript)

    def test_async_preview_captures_focus_before_busy_disables_the_trigger(self) -> None:
        request_preview = self.javascript[
            self.javascript.index("async function requestPreview("):
            self.javascript.index("function syncWriteBusy(")
        ]
        capture = "const returnFocus = document.activeElement;"
        self.assertIn(capture, request_preview)
        if capture in request_preview:
            self.assertLess(
                request_preview.index(capture),
                request_preview.index("await previewCoordinator.run("),
            )
        self.assertRegex(
            request_preview,
            r"renderPlanDrawer\(\s*reviewed\.payload,\s*reviewed\.request,"
            r"\s*reviewed\.allowReplacement,\s*problem,\s*null,\s*returnFocus,",
        )
        self.assertIn("returnFocus", self.javascript[
            self.javascript.index("function renderPlanDrawer("):
            self.javascript.index("async function requestPreview(")
        ])

    def test_danger_dialog_waits_for_coordinator_busy_release_before_initial_focus(self) -> None:
        coordinator = self.javascript[
            self.javascript.index("function createPreviewCoordinator("):
            self.javascript.index("async function settleApplyOperation(")
        ]
        request_preview = self.javascript[
            self.javascript.index("async function requestPreview("):
            self.javascript.index("function syncWriteBusy(")
        ]
        self.assertRegex(coordinator, r"finally \{\s*setBusy\(false\);\s*\}")
        self.assertLess(
            request_preview.index("const outcome = await previewCoordinator.run("),
            request_preview.index("openDangerDialog(reviewed.payload);"),
        )

    def test_focus_helpers_filter_disabled_controls_and_wrap_both_tab_directions(self) -> None:
        result = self._run_exports(
            "(() => {"
            "const calls = [];"
            "const first = {hidden:false, focus:() => calls.push('first')};"
            "const last = {hidden:false, focus:() => calls.push('last')};"
            "const singleControl = {hidden:false, focus:() => calls.push('single')};"
            "let selector = '';"
            "const container = {querySelectorAll:(value) => {selector=value; return [first,last];}};"
            "globalThis.document = {activeElement:first};"
            "const backward = {key:'Tab',shiftKey:true,preventDefault:() => calls.push('prevent-back')};"
            "AgentManagerTest.trapModalFocus(backward,container,() => calls.push('close'));"
            "globalThis.document.activeElement=last;"
            "const forward = {key:'Tab',shiftKey:false,preventDefault:() => calls.push('prevent-forward')};"
            "AgentManagerTest.trapModalFocus(forward,container,() => calls.push('close'));"
            "const singleContainer = {querySelectorAll:() => [singleControl]};"
            "globalThis.document.activeElement=singleControl;"
            "const single = {key:'Tab',shiftKey:false,preventDefault:() => calls.push('prevent-single')};"
            "AgentManagerTest.trapModalFocus(single,singleContainer,() => calls.push('close'));"
            "return {selector,calls};"
            "})()"
        )
        self.assertEqual(
            result["selector"],
            'button:not([disabled]), input:not([disabled]), select:not([disabled]), '
            'textarea:not([disabled]), [tabindex]:not([tabindex="-1"]):not([disabled])',
        )
        self.assertEqual(
            result["calls"],
            [
                "prevent-back", "last",
                "prevent-forward", "first",
                "prevent-single", "single",
            ],
        )

    def test_focus_restore_resolves_the_same_stable_control_after_rerender(self) -> None:
        helper = "function restoreCapturedFocus("
        self.assertIn(helper, self.javascript)
        if helper not in self.javascript:
            return
        result = self._run_exports(
            "(() => { const calls=[];"
            "const replacement={id:'instruction-codex-adopt',isConnected:true,"
            "focus:()=>calls.push('replacement')};"
            "const detached={id:'instruction-codex-adopt',isConnected:false,"
            "focus:()=>calls.push('detached')};"
            "const fakeDocument={getElementById:(id)=>{calls.push(id);return replacement;}};"
            "const restored=AgentManagerTest.restoreCapturedFocus(detached,fakeDocument);"
            "return {restored,calls};})()"
        )
        self.assertEqual(
            result,
            {
                "restored": True,
                "calls": ["instruction-codex-adopt", "replacement"],
            },
        )
        for stable_id in (
            "instruction-${record.key}-${action.id}",
            "skill-${record.slug}-${family.key}-details",
        ):
            self.assertIn(stable_id, self.javascript)
        self.assertIn(
            "button.title = `查看 ${record.name || record.slug} · ${family.label} 详情`",
            self.javascript,
        )
        for action_id in ('id: "enable"', 'id: "disable"', 'id: "adopt"'):
            self.assertIn(action_id, self.javascript)

    def test_apply_outcome_model_keeps_execution_results_separate_from_reviewed_preview(self) -> None:
        model = self._run_exports(
            "AgentManagerTest.buildApplyOutcomeModel("
            "{mode:'plan',changes:[{action:'replace',target:'/tmp/reviewed'}]},"
            "{ok:false,code:'post-apply-verification-failed',message:'rescan failed',path:'/tmp/state',"
            "changes:[{action:'replace',target:'/tmp/executed'}],results:["
            "{ok:true,code:'applied',key:'codex',path:'/tmp/executed',message:'replaced'},"
            "{ok:false,code:'blocked',key:'claude',path:'/tmp/blocked',message:'occupied'}]},"
            "{code:'status-refresh-failed',message:'status endpoint unavailable'})"
        )
        self.assertEqual(model["kind"], "execution-error")
        self.assertEqual(model["reviewedChanges"][0]["target"], "/tmp/reviewed")
        self.assertEqual(model["executionChanges"][0]["target"], "/tmp/executed")
        self.assertEqual([item["code"] for item in model["results"]], ["applied", "blocked"])
        self.assertEqual(model["problem"]["code"], "post-apply-verification-failed")
        self.assertEqual(
            model["verificationProblem"]["code"],
            "post-apply-verification-failed",
        )
        self.assertEqual(model["refreshProblem"]["code"], "status-refresh-failed")

        state_changed = self._run_exports(
            "AgentManagerTest.buildApplyOutcomeModel("
            "{mode:'plan',changes:[{action:'create',target:'/tmp/reviewed'}]},"
            "{ok:false,code:'state-changed',message:'fingerprint mismatch'},null)"
        )
        self.assertEqual(state_changed["kind"], "preview-error")
        self.assertEqual(state_changed["results"], [])
        self.assertEqual(state_changed["executionChanges"], [])

    def test_settle_apply_operation_preserves_http_error_payload_when_refresh_also_fails(self) -> None:
        settled = self._run_async_exports(
            "(() => {"
            "const reviewed={mode:'plan',changes:[{action:'replace',target:'/tmp/reviewed'}]};"
            "const payload={ok:false,code:'post-apply-verification-failed',message:'rescan failed',"
            "path:'/tmp/state',changes:[{action:'replace',target:'/tmp/executed'}],results:["
            "{ok:true,code:'applied',key:'codex',path:'/tmp/executed',message:'replaced'}]};"
            "const error=new Error(payload.message);error.payload=payload;"
            "return AgentManagerTest.settleApplyOperation("
            "reviewed,async()=>{throw error;},async()=>({ok:false,code:'status-refresh-failed',"
            "message:'status endpoint unavailable'}));})()"
        )
        self.assertEqual(settled["executionPayload"]["results"][0]["code"], "applied")
        self.assertEqual(settled["problem"]["path"], "/tmp/state")
        self.assertEqual(settled["refreshProblem"]["code"], "status-refresh-failed")
        self.assertEqual(settled["outcome"]["kind"], "execution-error")
        self.assertEqual(
            settled["outcome"]["executionChanges"][0]["target"],
            "/tmp/executed",
        )

    def test_http_shaped_state_changed_stays_on_reviewed_preview_without_retry(self) -> None:
        settled = self._run_async_exports(
            "(() => {let writes=0;"
            "const reviewed={mode:'plan',changes:[{action:'link',target:'/tmp/reviewed'}]};"
            "const payload={ok:false,code:'state-changed',message:'instruction state changed after review',"
            "path:'/tmp/home/.codex/AGENTS.md',changes:[{action:'link',target:'/tmp/reviewed'}],"
            "results:[{ok:false,code:'state-changed',key:'*',path:'/tmp/home/.codex/AGENTS.md',"
            "message:'instruction state changed after review'}]};"
            "const error=new Error(payload.message);error.payload=payload;"
            "return AgentManagerTest.settleApplyOperation(reviewed,async()=>{writes+=1;throw error;},"
            "async()=>({ok:true})).then(value=>({...value,writes}));})()"
        )
        self.assertEqual(settled["writes"], 1)
        self.assertIsNone(settled["outcome"])
        self.assertEqual(settled["problem"]["code"], "state-changed")
        self.assertEqual(
            settled["problem"]["message"],
            "instruction state changed after review",
        )
        self.assertEqual(settled["problem"]["path"], "/tmp/home/.codex/AGENTS.md")

    def test_mixed_state_changed_batch_remains_an_execution_outcome(self) -> None:
        model = self._run_exports(
            "AgentManagerTest.buildApplyOutcomeModel("
            "{mode:'plan',changes:[{action:'link',target:'/tmp/a'},{action:'link',target:'/tmp/b'}]},"
            "{ok:false,code:'state-changed',message:'second target changed',path:'/tmp/b',"
            "changes:[{action:'link',target:'/tmp/a'},{action:'link',target:'/tmp/b'}],results:["
            "{ok:true,code:'applied',key:'codex',path:'/tmp/a',message:'linked'},"
            "{ok:false,code:'state-changed',key:'claude',path:'/tmp/b',message:'changed'}]},null)"
        )
        self.assertEqual(model["kind"], "execution-error")
        self.assertEqual([item["code"] for item in model["results"]], ["applied", "state-changed"])
        self.assertEqual(len(model["executionChanges"]), 2)
        self.assertTrue(model["showSessionReminder"])

    def test_session_reminder_is_only_attached_to_execution_outcomes(self) -> None:
        result = self._run_exports(
            "(() => {"
            "const reviewed={changes:[{action:'link',target:'/tmp/reviewed'}]};"
            "const success=AgentManagerTest.buildApplyOutcomeModel(reviewed,"
            "{ok:true,results:[{ok:true,code:'applied'}]},null);"
            "const postVerify=AgentManagerTest.buildApplyOutcomeModel(reviewed,"
            "{ok:false,code:'post-apply-verification-failed',results:[{ok:false,code:'state-changed'}]},null);"
            "const prewrite=AgentManagerTest.buildApplyOutcomeModel(reviewed,"
            "{ok:false,code:'state-changed',results:[{ok:false,code:'not-applied'}]},null);"
            "return {success:success.showSessionReminder,postVerify:postVerify.showSessionReminder,"
            "prewrite:prewrite.showSessionReminder,prewriteKind:prewrite.kind};})()"
        )
        self.assertEqual(
            result,
            {
                "success": True,
                "postVerify": True,
                "prewrite": False,
                "prewriteKind": "preview-error",
            },
        )
        self.assertRegex(
            self.javascript,
            r"if \(outcome\.showSessionReminder\) \{(?:.|\n)*?"
            r"请开始新会话；若缓存规则仍生效，请重启 Desktop 或 CLI。",
        )

    def test_apply_guard_deduplicates_concurrent_writes_and_releases_in_finally(self) -> None:
        result = self._run_async_exports(
            "(() => { let writes=0; let release;"
            "const gate=new Promise(resolve => {release=resolve;});"
            "const guard=AgentManagerTest.createApplyGuard();"
            "const first=guard.run(async()=>{writes+=1;await gate;return 'first';});"
            "const duplicate=guard.run(async()=>{writes+=1;return 'duplicate';});"
            "release();"
            "return Promise.all([first,duplicate]).then(async values=>{"
            "const afterSuccess=await guard.run(async()=>{writes+=1;return 'after-success';});"
            "let failed=false;try{await guard.run(async()=>{writes+=1;throw new Error('boom');});}catch(_e){failed=true;}"
            "const afterFailure=await guard.run(async()=>{writes+=1;return 'after-failure';});"
            "return {writes,values,afterSuccess,failed,afterFailure};});})()"
        )
        self.assertEqual(
            result,
            {
                "writes": 4,
                "values": ["first", None],
                "afterSuccess": "after-success",
                "failed": True,
                "afterFailure": "after-failure",
            },
        )
        self.assertIn(
            '.dialog-actions button, #danger-apply-button',
            self.javascript,
        )

    def test_reviewed_preview_generation_rejects_out_of_order_response_atomically(self) -> None:
        result = self._run_async_exports(
            "typeof AgentManagerTest.createPreviewCoordinator !== 'function'"
            "? {missing:true} : (async()=>{"
            "let resolveA,resolveB,loadedB,current=null;const commits=[],busy=[];"
            "const coordinator=AgentManagerTest.createPreviewCoordinator({"
            "commit:(value)=>{current=value;commits.push(value?value.payload.marker:null);},"
            "setBusy:(value)=>busy.push(value)});"
            "const requestA={path:'/api/skills/set',body:{skill:'A',all:false,tool:'codex',on:true,apply:false}};"
            "const requestB={path:'/api/skills/set',body:{skill:'B',all:false,tool:'codex',on:false,apply:false}};"
            "const pendingA=coordinator.run(requestA,false,()=>new Promise(resolve=>{resolveA=resolve;}));"
            "const pendingB=coordinator.run(requestB,true,(intent)=>{loadedB=intent;"
            "return new Promise(resolve=>{resolveB=resolve;});});"
            "requestB.path='/mutated';requestB.body.skill='mutated';"
            "resolveB({ok:true,marker:'B',changes:[{action:'create'}]});"
            "const outcomeB=await pendingB;"
            "resolveA({ok:true,marker:'A',changes:[{action:'remove'}]});"
            "const outcomeA=await pendingA;"
            "const apply=AgentManagerTest.buildApplyRequest(current.request,current.payload);"
            "return {missing:false,acceptedA:outcomeA.accepted,acceptedB:outcomeB.accepted,"
            "marker:current.payload.marker,skill:current.request.body.skill,"
            "allowReplacement:current.allowReplacement,applySkill:apply.body.skill,"
            "loaded:[loadedB.path,loadedB.body.skill,Object.isFrozen(loadedB),Object.isFrozen(loadedB.body)],"
            "frozen:[current,current.request,current.request.body,current.payload,current.payload.changes]"
            ".map(Object.isFrozen),commits,busy};})()"
        )
        self.assertFalse(result.get("missing", False))
        self.assertFalse(result["acceptedA"])
        self.assertTrue(result["acceptedB"])
        self.assertEqual(result["marker"], "B")
        self.assertEqual(result["skill"], "B")
        self.assertEqual(result["applySkill"], "B")
        self.assertTrue(result["allowReplacement"])
        self.assertEqual(result["loaded"], ["/api/skills/set", "B", True, True])
        self.assertEqual(result["frozen"], [True, True, True, True, True])
        self.assertEqual(result["commits"], [None, None, "B"])
        self.assertEqual(result["busy"], [True, True, False, False])

    def test_write_busy_state_covers_danger_dialog_and_restores_prior_disabled_state(self) -> None:
        result = self._run_exports(
            "(() => {"
            "const apply={disabled:false,dataset:{}};"
            "const cancel={disabled:false,dataset:{}};"
            "const alreadyDisabled={disabled:true,dataset:{}};"
            "const buttons=[apply,cancel,alreadyDisabled];const selectors=[];"
            "const fakeDocument={querySelectorAll:(selector)=>{selectors.push(selector);"
            "return selector==='[data-write-busy]'"
            "?buttons.filter(button=>Object.hasOwn(button.dataset,'writeBusy')):buttons;}};"
            "AgentManagerTest.updateWriteBusy(fakeDocument,true);"
            "const during=buttons.map(button=>button.disabled);"
            "AgentManagerTest.updateWriteBusy(fakeDocument,false);"
            "return {during,after:buttons.map(button=>button.disabled),selectors};})()"
        )
        self.assertEqual(result["during"], [True, True, True])
        self.assertEqual(result["after"], [False, False, True])
        self.assertIn(".dialog-actions button", result["selectors"][0])
        self.assertIn("#danger-apply-button", result["selectors"][0])

    def test_write_busy_survives_rerender_and_covers_refresh_controls(self) -> None:
        result = self._run_exports(
            "(()=>{const selectors=[];"
            "const operation={kind:'operation',disabled:false,dataset:{}};"
            "const priorDisabled={kind:'operation',disabled:true,dataset:{}};"
            "const refresh={kind:'refresh',disabled:false,dataset:{}};"
            "let buttons=[operation,priorDisabled,refresh];"
            "const fakeDocument={querySelectorAll:(selector)=>{selectors.push(selector);"
            "if(selector==='[data-write-busy]')return buttons.filter(button=>Object.hasOwn(button.dataset,'writeBusy'));"
            "return buttons.filter(button=>button.kind==='operation'||(button.kind==='refresh'&&selector.includes('#refresh-button')));}};"
            "AgentManagerTest.updateWriteBusy(fakeDocument,true);"
            "const rerendered={kind:'operation',disabled:false,dataset:{}};"
            "buttons=[operation,priorDisabled,refresh,rerendered];"
            "AgentManagerTest.updateWriteBusy(fakeDocument,true);"
            "AgentManagerTest.updateWriteBusy(fakeDocument,false);"
            "return {states:[operation.disabled,priorDisabled.disabled,refresh.disabled,rerendered.disabled],selectors};})()"
        )
        self.assertEqual(result["states"], [False, True, False, False])
        self.assertIn("#refresh-button", result["selectors"][0])

    def test_refresh_completion_updates_restore_state_during_write_busy(self) -> None:
        result = self._run_exports(
            "(()=>{if(typeof AgentManagerTest.releaseWriteBusyControl!=='function')"
            "return {missing:true};const refresh={disabled:true,dataset:{}};"
            "const fakeDocument={querySelectorAll:(selector)=>selector==='[data-write-busy]'"
            "?[refresh].filter(button=>Object.hasOwn(button.dataset,'writeBusy')):[refresh]};"
            "AgentManagerTest.updateWriteBusy(fakeDocument,true);"
            "AgentManagerTest.releaseWriteBusyControl(refresh);const released=refresh.disabled;"
            "AgentManagerTest.updateWriteBusy(fakeDocument,true);const held=refresh.disabled;"
            "AgentManagerTest.updateWriteBusy(fakeDocument,false);"
            "return {missing:false,released,held,final:refresh.disabled,tagged:Object.hasOwn(refresh.dataset,'writeBusy')};})()"
        )
        self.assertFalse(result.get("missing", False))
        self.assertFalse(result["released"])
        self.assertTrue(result["held"])
        self.assertFalse(result["final"])
        self.assertFalse(result["tagged"])

    def test_apply_preview_captures_one_reviewed_preview_object_at_start(self) -> None:
        apply_preview = self.javascript[
            self.javascript.index("async function applyPreview("):
            self.javascript.index("function renderStoppedPage(")
        ]
        self.assertIn("const reviewed = state.reviewedPreview;", apply_preview)
        self.assertIn(
            "buildApplyRequest(reviewed.request, reviewed.payload)",
            apply_preview,
        )
        self.assertRegex(
            apply_preview,
            r"settleApplyOperation\(\s*reviewed\.payload,",
        )
        self.assertIn("reviewed.allowReplacement", apply_preview)
        self.assertNotIn("state.previewRequest", apply_preview)
        self.assertNotIn("state.previewPayload", apply_preview)

    def test_apply_preview_connects_guard_execution_outcome_and_refresh_failure_rendering(self) -> None:
        self.assertIn("const applyGuard = createApplyGuard();", self.javascript)
        self.assertRegex(
            self.javascript,
            r"async function applyPreview\(\) \{(?:.|\n)*?return applyGuard\.run\(async \(\) => \{",
        )
        for contract in (
            "renderApplyOutcomeDrawer(settled.outcome)",
            'node("h3", "已确认的变更计划")',
            'node("h3", "已执行结果")',
            'node("h3", "后续验证失败")',
            'node("h3", "后续刷新失败")',
        ):
            self.assertIn(contract, self.javascript)
        self.assertRegex(
            self.javascript,
            r"settleApplyOperation\(\s*reviewed\.payload,",
        )

    def test_copy_text_uses_clipboard_then_focused_textarea_then_manual_guidance(self) -> None:
        result = self._run_async_exports(
            "(() => { const calls = []; return AgentManagerTest.copyText('rules', "
            "{writeText: async () => { calls.push('clipboard'); throw new Error('denied'); }}, "
            "() => { calls.push('textarea'); return false; }, "
            "() => calls.push('manual')).then(ok => ({ok, calls})); })()"
        )
        self.assertEqual(
            result,
            {"ok": False, "calls": ["clipboard", "textarea", "manual"]},
        )
        self.assertLess(
            self.javascript.index("textarea.focus();"),
            self.javascript.index("textarea.select();"),
        )

    def test_build_topology_returns_four_tool_routes_with_text_status_and_line_semantics(self) -> None:
        state = {
            "repo_root": "/Users/test/Codes/lucas-skills",
            "skills": {
                "adapters": [
                    {"key": "claude-shared", "tool": "claude", "home": "/Users/test", "root": "/Users/test/.claude/skills"},
                    {"key": "codex", "tool": "codex", "home": "/Users/test", "root": "/Users/test/.codex/skills"},
                    {"key": "copilot", "tool": "copilot", "home": "/Users/test", "root": "/Users/test/.copilot/skills"},
                    {"key": "antigravity", "tool": "antigravity", "home": "/Users/test", "root": "/Users/test/.gemini/antigravity/skills"},
                ],
                "targets": [
                    {"tool": "claude", "state": "enabled"},
                    {"tool": "codex", "state": "enabled"},
                    {"tool": "copilot", "state": "conflict"},
                    {"tool": "antigravity", "state": "disabled"},
                ],
            },
            "instructions": {
                "targets": [
                    {"key": "claude", "state": "enabled", "path": "/Users/test/.claude/CLAUDE.md"},
                    {"key": "codex", "state": "enabled", "path": "/Users/test/.codex/AGENTS.md"},
                    {"key": "copilot", "state": "manual", "path": "/Users/test/.copilot/copilot-instructions.md"},
                    {"key": "antigravity", "state": "broken", "path": "/Users/test/.gemini/AGENTS.md"},
                ],
            },
        }
        result = self._run_exports(
            f"AgentManagerTest.buildTopology({json.dumps(state)})"
        )
        self.assertEqual([route["tool"] for route in result], ["claude", "codex", "copilot", "antigravity"])
        self.assertTrue(all(route["skills"]["lineStyle"] == "solid" for route in result))
        self.assertTrue(all(route["instructions"]["lineStyle"] == "dashed" for route in result))
        self.assertEqual(result[0]["skills"]["statusLabel"], "正常")
        self.assertEqual(result[2]["skills"]["statusLabel"], "需要处理")
        self.assertEqual(result[3]["skills"]["statusLabel"], "未启用")
        self.assertEqual(result[3]["instructions"]["statusLabel"], "需要处理")

    def test_multi_adapter_routes_are_partial_and_preserve_every_root_and_message(self) -> None:
        payload = {
            "repo_root": "/Users/test/Codes/lucas-skills",
            "surfaces": [
                {"key": "antigravity-desktop", "installed": True, "detector": "application"},
                {"key": "antigravity-cli", "installed": True, "detector": "command:agy"},
            ],
            "skills": {
                "adapters": [
                    {
                        "key": "antigravity-desktop",
                        "tool": "antigravity",
                        "home": "/Users/test",
                        "root": "/Users/test/.gemini/config/skills",
                        "surfaces": ["antigravity-desktop"],
                    },
                    {
                        "key": "antigravity-cli",
                        "tool": "antigravity",
                        "home": "/Users/test",
                        "root": "/Users/test/.gemini/antigravity-cli/plugins/lucas-skills/skills",
                        "surfaces": ["antigravity-cli"],
                    },
                ],
                "targets": [
                    {
                        "slug": "docx",
                        "adapter_key": "antigravity-desktop",
                        "tool": "antigravity",
                        "state": "enabled",
                        "path": "/Users/test/.gemini/config/skills/docx",
                        "message": "desktop route enabled",
                    },
                    {
                        "slug": "docx",
                        "adapter_key": "antigravity-cli",
                        "tool": "antigravity",
                        "state": "disabled",
                        "path": "/Users/test/.gemini/antigravity-cli/plugins/lucas-skills/skills/docx",
                        "message": "CLI route disabled",
                    },
                ],
            },
            "instructions": {"targets": []},
        }
        topology = self._run_exports(
            f"AgentManagerTest.buildTopology({json.dumps(payload)})"
        )
        route = next(item for item in topology if item["tool"] == "antigravity")
        self.assertEqual(route["skills"]["status"], "partial")
        self.assertEqual(route["skills"]["statusLabel"], "部分启用")
        self.assertEqual(
            [root["fullPath"] for root in route["skills"]["roots"]],
            [
                "/Users/test/.gemini/config/skills",
                "/Users/test/.gemini/antigravity-cli/plugins/lucas-skills/skills",
            ],
        )
        self.assertEqual(
            route["skills"]["messages"],
            ["desktop route enabled", "CLI route disabled"],
        )

        aggregate = self._run_exports(
            "AgentManagerTest.aggregateSkillTarget("
            f"{json.dumps(payload['skills']['targets'])}, 'antigravity')"
        )
        self.assertEqual(aggregate["state"], "partial")
        self.assertEqual(len(aggregate["records"]), 2)
        self.assertEqual(
            [record["path"] for record in aggregate["records"]],
            [
                "/Users/test/.gemini/config/skills/docx",
                "/Users/test/.gemini/antigravity-cli/plugins/lucas-skills/skills/docx",
            ],
        )

    def test_shared_instruction_surfaces_affect_every_family_and_preserve_coverage(self) -> None:
        family_surfaces = {
            "claude": ["claude-desktop", "claude-cli"],
            "codex": ["codex-desktop", "codex-cli"],
            "copilot": ["copilot-cli"],
            "antigravity": ["antigravity-desktop", "antigravity-cli"],
        }
        shared_surfaces = [
            surface
            for surfaces in family_surfaces.values()
            for surface in surfaces
        ]
        payload = {
            "repo_root": "/Users/test/Codes/lucas-skills",
            "surfaces": [
                {"key": surface, "installed": True}
                for surface in (
                    "claude-desktop", "claude-cli", "codex-desktop", "codex-cli",
                    "copilot-desktop", "copilot-cli",
                    "antigravity-desktop", "antigravity-cli",
                )
            ],
            "skills": {
                "adapters": [
                    {
                        "key": family,
                        "tool": family,
                        "home": "/Users/test",
                        "root": f"/Users/test/.{family}/skills",
                        "surfaces": surfaces,
                    }
                    for family, surfaces in family_surfaces.items()
                ],
                "targets": [],
            },
            "instructions": {
                "targets": [
                    {
                        "key": "shared",
                        "state": "broken",
                        "path": "/Users/test/.agents/AGENTS.md",
                        "surfaces": shared_surfaces,
                        "message": "shared route broken",
                    },
                    *[
                        {
                            "key": family,
                            "state": "enabled",
                            "path": f"/Users/test/.{family}/AGENTS.md",
                            "surfaces": surfaces,
                            "message": f"{family} route enabled",
                        }
                        for family, surfaces in family_surfaces.items()
                    ],
                ],
                "manual_surfaces": [
                    {
                        "key": "copilot-desktop",
                        "state": "manual",
                        "message": "configure Copilot Desktop manually",
                    }
                ],
            },
        }

        broken = self._run_exports(
            f"AgentManagerTest.buildTopology({json.dumps(payload)})"
        )
        missing_payload = json.loads(json.dumps(payload))
        missing_payload["instructions"]["targets"][0]["state"] = "missing"
        missing_payload["instructions"]["targets"][0]["message"] = "shared route missing"
        missing = self._run_exports(
            f"AgentManagerTest.buildTopology({json.dumps(missing_payload)})"
        )

        self.assertEqual(
            [route["instructions"]["status"] for route in broken],
            ["attention", "attention", "attention", "attention"],
        )
        self.assertEqual(
            [route["instructions"]["status"] for route in missing],
            ["partial", "partial", "partial", "partial"],
        )
        for route in broken:
            roots = route["instructions"]["roots"]
            self.assertEqual(roots[0]["key"], "shared")
            self.assertIn(route["tool"], [root["key"] for root in roots])
            self.assertIn("shared route broken", route["instructions"]["messages"])
            self.assertIn(
                f"{route['tool']} route enabled",
                route["instructions"]["messages"],
            )
            self.assertTrue(roots[0]["coverageLabel"])
        copilot = next(route for route in broken if route["tool"] == "copilot")
        self.assertEqual(
            [root["key"] for root in copilot["instructions"]["roots"]],
            ["shared", "copilot", "copilot-desktop"],
        )
        self.assertEqual(
            copilot["instructions"]["messages"],
            [
                "shared route broken",
                "copilot route enabled",
                "configure Copilot Desktop manually",
            ],
        )

    def test_surface_rows_preserve_desktop_and_cli_install_truth(self) -> None:
        surfaces = [
            {"key": "claude-desktop", "installed": True, "detector": "application"},
            {"key": "claude-cli", "installed": False, "detector": "command:claude"},
        ]
        rows = self._run_exports(
            f"AgentManagerTest.toolSurfaceRows({json.dumps(surfaces)}, 'claude')"
        )
        self.assertEqual(
            rows,
            [
                {"key": "claude-desktop", "label": "Desktop", "installed": True},
                {"key": "claude-cli", "label": "CLI", "installed": False},
            ],
        )

    def test_load_path_rows_keep_repository_and_every_adapter_root(self) -> None:
        payload = {
            "repo_root": "/Users/test/Codes/lucas-skills",
            "skills": {
                "adapters": [
                    {"key": "antigravity-desktop", "tool": "antigravity", "home": "/Users/test", "root": "/Users/test/.gemini/config/skills", "surfaces": ["antigravity-desktop"]},
                    {"key": "antigravity-cli", "tool": "antigravity", "home": "/Users/test", "root": "/Users/test/.gemini/antigravity-cli/plugins/lucas-skills/skills", "surfaces": ["antigravity-cli"]},
                ]
            },
        }
        rows = self._run_exports(
            f"AgentManagerTest.loadPathRows({json.dumps(payload)})"
        )
        self.assertEqual(
            [row["path"] for row in rows],
            [
                "/Users/test/Codes/lucas-skills/skills",
                "/Users/test/.gemini/config/skills",
                "/Users/test/.gemini/antigravity-cli/plugins/lucas-skills/skills",
            ],
        )
        self.assertEqual(
            [row["displayPath"] for row in rows[1:]],
            [
                "~/.gemini/config/skills",
                "~/.gemini/antigravity-cli/plugins/lucas-skills/skills",
            ],
        )

    def test_copy_path_falls_back_then_guides_manual_copy(self) -> None:
        path = "/Users/test/.claude/skills"
        copied = self._run_async_exports(
            "AgentManagerTest.copyRootPath("
            f"{json.dumps(path)}, {{ writeText: async () => {{ throw new Error('not focused'); }} }}, "
            "() => true)"
        )
        self.assertEqual(
            copied,
            {"ok": True, "method": "fallback", "message": f"已复制路径：{path}"},
        )
        manual = self._run_async_exports(
            "AgentManagerTest.copyRootPath("
            f"{json.dumps(path)}, {{ writeText: async () => {{ throw new Error('denied'); }} }}, "
            "() => false)"
        )
        self.assertEqual(
            manual,
            {
                "ok": False,
                "method": "manual",
                "message": f"浏览器阻止自动复制，请手动复制：{path}",
            },
        )
        self.assertLess(
            self.javascript.index("textarea.focus();"),
            self.javascript.index("textarea.select();"),
        )

    def test_inventory_details_use_a_native_button_instead_of_clickable_rows(self) -> None:
        self.assertIn("inventory-detail-button", self.javascript)
        self.assertIn("detailButton.addEventListener", self.javascript)
        self.assertNotIn('row.addEventListener("click"', self.javascript)

    def test_inventory_view_explains_and_filters_records(self) -> None:
        for element_id in (
            "inventory-summary",
            "inventory-result-count",
            "inventory-query",
            "inventory-tool-filter",
            "inventory-source-filter",
            "inventory-status-filter",
            "inventory-clear-filters",
            "inventory-source-legend",
        ):
            self.assertIn(f'id="{element_id}"', self.page)
        scope_buttons = [
            attrs
            for tag, attrs in self.parser.start_tags
            if tag == "button" and attrs.get("data-inventory-scope")
        ]
        self.assertEqual(
            {attrs["data-inventory-scope"] for attrs in scope_buttons},
            {"managed-or-flagged", "all", "managed", "flagged"},
        )
        selected = [attrs for attrs in scope_buttons if attrs.get("aria-pressed") == "true"]
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["data-inventory-scope"], "managed-or-flagged")
        legend = next(
            tag
            for tag, attrs in self.parser.start_tags
            if attrs.get("id") == "inventory-source-legend"
        )
        self.assertEqual(legend, "details")
        for heading in ("Skill", "来源", "工具", "状态", "路径", "操作"):
            self.assertIn(f">{heading}</th>", self.page)

    def test_inventory_refresh_preserves_filters_and_clear_restores_defaults(self) -> None:
        for contract in (
            "inventoryRecords: []",
            'inventoryScope: "managed-or-flagged"',
            "state.inventoryRecords = asArray(payload.inventory)",
            "renderInventory()",
            "resetInventoryFilters",
            'state.inventoryScope = "managed-or-flagged"',
            'document.getElementById("inventory-query").value = ""',
            'document.getElementById("inventory-tool-filter").value = "all"',
            'document.getElementById("inventory-source-filter").value = "all"',
            'document.getElementById("inventory-status-filter").value = "all"',
            "当前筛选下没有库存记录。",
            "全局库存为空。请确认各工具已安装，并在扫描后重试。",
            "库存摘要不可用：最近一次刷新失败",
            "inventory-name-repeat",
            "组重名",
        ):
            self.assertIn(contract, self.javascript)
        for css_class in (
            ".data-panel",
            ".list-toolbar",
            ".segmented-control",
            ".status-badge",
            ".table-action",
            ".inventory-row-managed",
            ".inventory-row-flagged",
        ):
            self.assertIn(css_class, self.css)
        self.assertRegex(
            self.css,
            r"\.inventory-path-cell \.path-text \{(?:.|\n)*?display: block;",
        )

    def test_management_lists_share_alignment_contract(self) -> None:
        for contract in (
            "skill-identity",
            "skill-description-clamped",
            "route-status-button",
            "compact-action",
        ):
            self.assertIn(contract, self.javascript)
        self.assertIn('class="instruction-grid-header"', self.page)
        for heading in ("目标", "加载位置", "覆盖工具", "状态", "操作"):
            self.assertIn(f">{heading}<", self.page)
        for panel in ("skills-panel", "instructions-panel", "inventory-panel"):
            self.assertIn(panel, self.page)
        self.assertGreaterEqual(self.page.count("data-panel"), 3)
        for css_class in (
            ".skill-identity",
            ".skill-description-clamped",
            ".route-status-button",
            ".instruction-grid-header",
            ".compact-action",
        ):
            self.assertIn(css_class, self.css)

    def test_inventory_presentations_use_chinese_labels(self) -> None:
        result = self._run_exports(
            "(() => ({"
            "sources: ['managed','plugin','built-in','local-copy','external-link','broken','mystery']"
            ".map(value => AgentManagerTest.inventorySourcePresentation(value)),"
            "flags: ['duplicate-name','broken-link','invalid-skill:missing SKILL.md','mystery']"
            ".map(value => AgentManagerTest.inventoryFlagPresentation(value))"
            "}))()"
        )
        self.assertEqual(
            [item["label"] for item in result["sources"]],
            [
                "仓库受管",
                "插件提供",
                "工具内置",
                "本地独立",
                "外部链接",
                "无效条目",
                "其他来源",
            ],
        )
        self.assertEqual(
            [item["label"] for item in result["flags"]],
            ["名称重复", "链接已失效", "Skill 无效", "未知标记"],
        )
        self.assertEqual(result["flags"][2]["raw"], "invalid-skill:missing SKILL.md")
        self.assertEqual(result["flags"][3]["raw"], "mystery")

    def test_filter_inventory_records_combines_all_filters(self) -> None:
        records = self._inventory_filter_records()
        result = self._run_exports(
            "(() => { const records = "
            f"{json.dumps(records)};"
            "return {"
            "defaultScope: AgentManagerTest.filterInventoryRecords(records, "
            "{scope:'managed-or-flagged',query:'',tool:'all',source:'all',status:'all'}),"
            "combined: AgentManagerTest.filterInventoryRecords(records, "
            "{scope:'all',query:'shared',tool:'claude',source:'plugin',status:'flagged'}),"
            "clean: AgentManagerTest.filterInventoryRecords(records, "
            "{scope:'all',query:'',tool:'codex',source:'plugin',status:'clean'})"
            "}; })()"
        )
        self.assertEqual(
            [record["slug"] for record in result["defaultScope"]],
            ["docx", "pdf", "reader"],
        )
        self.assertEqual([record["slug"] for record in result["combined"]], ["reader"])
        self.assertEqual([record["slug"] for record in result["clean"]], ["creator"])

    def test_inventory_summary_and_sorting(self) -> None:
        records = self._inventory_filter_records()
        result = self._run_exports(
            "(() => { const records = "
            f"{json.dumps(records)};"
            "const visible = AgentManagerTest.filterInventoryRecords(records, "
            "{scope:'managed-or-flagged',query:'',tool:'all',source:'all',status:'all'});"
            "const original = records.map(record => record.slug);"
            "const sorted = AgentManagerTest.sortInventoryRecords(records);"
            "return {summary: AgentManagerTest.inventorySummary(records, visible),"
            "sorted: sorted.map(record => record.slug), original,"
            "after: records.map(record => record.slug)}; })()"
        )
        self.assertEqual(
            result["summary"],
            {"managed": 2, "flagged": 2, "duplicateGroups": 1, "total": 5, "visible": 3},
        )
        self.assertEqual(result["sorted"], ["pdf", "reader", "docx", "creator", "writer"])
        self.assertEqual(result["after"], result["original"])

    @staticmethod
    def _inventory_filter_records() -> list[dict[str, object]]:
        return [
            {
                "slug": "docx",
                "name": "Word documents",
                "source_type": "managed",
                "tools": ["claude"],
                "path": "/repo/skills/docx",
                "flags": [],
            },
            {
                "slug": "pdf",
                "name": "PDF",
                "source_type": "managed",
                "tools": ["codex"],
                "path": "/repo/skills/pdf",
                "flags": ["duplicate-name"],
            },
            {
                "slug": "reader",
                "name": "Reader",
                "source_type": "plugin",
                "tools": ["claude"],
                "path": "/plugins/reader",
                "resolved_target": "/shared/reader",
                "flags": ["broken-link"],
            },
            {
                "slug": "creator",
                "name": "Creator",
                "source_type": "plugin",
                "tools": ["codex"],
                "path": "/plugins/creator",
                "flags": [],
            },
            {
                "slug": "writer",
                "name": "Writer",
                "source_type": "local-copy",
                "tools": ["copilot"],
                "path": "/local/writer",
                "raw_target": "/shared/writer",
                "flags": [],
            },
        ]

    def test_filter_skill_rows_combines_query_and_state_filter(self) -> None:
        rows = [
            {"slug": "docx", "name": "Word documents", "description": "Create documents", "states": ["enabled", "disabled"]},
            {"slug": "pdf", "name": "PDF", "description": "Inspect files", "states": ["enabled"]},
            {"slug": "broken", "name": "Broken", "description": "Needs repair", "states": ["conflict"]},
        ]
        result = self._run_exports(
            f"AgentManagerTest.filterSkillRows({json.dumps(rows)}, 'document', 'disabled')"
        )
        self.assertEqual([row["slug"] for row in result], ["docx"])

    def test_compact_home_path_only_shortens_the_exact_home_prefix(self) -> None:
        paths = [
            "/Users/test",
            "/Users/test/.claude/skills",
            "/Users/tester/.claude/skills",
            "/tmp/Users/test/cache",
        ]
        result = self._run_exports(
            f"{json.dumps(paths)}.map(path => AgentManagerTest.compactHomePath(path, '/Users/test'))"
        )
        self.assertEqual(
            result,
            ["~", "~/.claude/skills", "/Users/tester/.claude/skills", "/tmp/Users/test/cache"],
        )

    def test_summarize_plan_counts_actions_and_codes(self) -> None:
        plan = {
            "changes": [
                {"action": "create", "code": "ready"},
                {"action": "create", "code": "ready"},
                {"action": "blocked", "code": "target-conflict"},
                {"action": "noop"},
            ]
        }
        result = self._run_exports(
            f"AgentManagerTest.summarizePlan({json.dumps(plan)})"
        )
        self.assertEqual(
            result,
            {
                "total": 4,
                "byAction": {"create": 2, "blocked": 1, "noop": 1},
                "byCode": {"ready": 2, "target-conflict": 1, "none": 1},
            },
        )


if __name__ == "__main__":
    unittest.main()
