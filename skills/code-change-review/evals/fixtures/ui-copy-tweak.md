# Repository snapshot

Complete offline artifacts for example/admin PR #303 "fix(export): 明确导出按钮文案". Base 6666666666666666666666666666666666666666; head 7777777777777777777777777777777777777777. No WIP. Locations use target-file coordinates. Supplied checks are author-run, not reviewer-run. The application cannot be started in this offline scenario.

## Requirement and baseline

Owner request: operators confused the list export with the attachment download; label the list export button "导出 Excel" and its tooltip "导出当前筛选结果". No behavior change was requested.

Repository rules (unchanged): docs/development-workflow.md:60 requires a runnable-page walkthrough with screenshots before merging new pages; copy-only changes on existing pages follow the ordinary review path. AGENTS.md:40 requires shared components such as `Button` and `HelpTip` on pages.

## Head diff

`frontend/src/modules/publishing/LivePublishTasks.tsx`:
```diff
@@ -88,3 +88,3 @@
-        <HelpTip content="导出">
-          <Button onClick={exportList}>导出</Button>
+        <HelpTip content="导出当前筛选结果">
+          <Button onClick={exportList}>导出 Excel</Button>
         </HelpTip>
```
`tests/test_publish_tasks_browser.py:41`:
```diff
-    page.get_by_role("button", name="导出").click()
+    page.get_by_role("button", name="导出 Excel").click()
```
No other file references the old label. The author reports the browser test passed 1/1 and supplied no screenshot.
