(function () {
  "use strict";

  const TOOL_FAMILIES = [
    { key: "claude", label: "Claude" },
    { key: "codex", label: "Codex" },
    { key: "copilot", label: "Copilot" },
    { key: "antigravity", label: "Antigravity" },
  ];
  const ATTENTION_STATES = new Set(["conflict", "error", "broken", "legacy"]);
  const NAV_ICONS = {
    overview: "M3 3h8v8H3zM13 3h8v8h-8zM3 13h8v8H3zM13 13h8v8h-8z",
    skills: "M12 2 2 7l10 5 10-5-10-5zM2 12l10 5 10-5M2 17l10 5 10-5",
    instructions: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6zM14 2v6h6M9 13h6M9 17h6",
    inventory: "M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 8zM3.3 7l8.7 5 8.7-5M12 22V12",
  };
  const MESSAGE_LABELS = {
    "direct repository link": "已直接链接到仓库",
    "recognized legacy link": "旧结构链接，可接管为直链",
    "whole-directory link requires adoption": "整目录旧链接，需要接管",
    "broken symlink": "链接已损坏",
    "surface not installed": "未检测到该工具",
    "target differs from repository source": "内容与仓库源不一致",
    "target does not exist": "目标不存在",
    "target is absent": "目标不存在",
    "target is a directory": "目标是目录，不支持接管",
    "target is a special file": "目标是特殊文件，不支持接管",
    "file content matches repository source": "内容与仓库源一致（普通文件副本）",
    "link resolves through another entry": "经其他入口间接链接到仓库",
    "link resolves to another source": "链接指向其他来源",
    "link cannot be resolved": "链接无法解析",
    "already in requested state": "已处于目标状态",
    "already a direct repository link": "已是仓库直链",
    "create direct repository link": "创建仓库直链",
    "remove direct repository link": "移除仓库直链",
    "adopt existing instruction entry": "接管现有入口为仓库直链",
    "replace conflicting instruction entry": "替换冲突入口（原文件保存到快照）",
    "symlink belongs to another source": "链接指向其他来源",
    "target is not a symlink": "目标不是软链",
    "target root is a broken symlink": "目标根目录链接已损坏",
    "target root is an unmanaged symlink": "目标根目录是未受管链接",
    "target root is not a directory": "目标根目录不是目录",
    "configure repository instructions manually in Copilot Desktop Settings":
      "需在 Copilot Desktop 设置中手动配置",
  };
  const state = {
    status: null,
    inventoryLoaded: false,
    inventoryLoading: false,
    inventoryRecords: [],
    inventoryScope: "managed-or-flagged",
    activeView: "overview",
    token: "",
    selectedSkills: new Set(),
    reviewedPreview: null,
    writeBusyCount: 0,
    lastStatusProblem: null,
    lastInventoryProblem: null,
    openAttentionGroups: new Set(),
  };

  function asArray(value) {
    return Array.isArray(value) ? value : [];
  }

  function compactHomePath(path, home) {
    if (typeof path !== "string" || typeof home !== "string" || !home) return path;
    const normalizedHome = home.length > 1 ? home.replace(/\/+$/, "") : home;
    if (path === normalizedHome) return "~";
    if (path.startsWith(`${normalizedHome}/`)) return `~${path.slice(normalizedHome.length)}`;
    return path;
  }

  function repositoryHome(payload) {
    const adapters = asArray(payload && payload.skills && payload.skills.adapters);
    return (adapters.length && adapters[0].home) || "";
  }

  function filterSkillRows(rows, query, stateFilter) {
    const needle = String(query || "").trim().toLocaleLowerCase();
    const wantedState = stateFilter || "all";
    return asArray(rows).filter((row) => {
      const searchable = [row.slug, row.name, row.description]
        .filter(Boolean)
        .join(" ")
        .toLocaleLowerCase();
      const matchesQuery = !needle || searchable.includes(needle);
      const states = asArray(row.states);
      const matchesState = wantedState === "all"
        || (wantedState === "attention"
          ? states.some((item) => ATTENTION_STATES.has(item))
          : states.includes(wantedState));
      return matchesQuery && matchesState;
    });
  }

  function inventorySourcePresentation(sourceType) {
    const presentations = {
      managed: ["仓库受管", "由当前仓库统一管理并链接到工具加载位置。"],
      plugin: ["插件提供", "由已安装插件提供，不受当前仓库直接管理。"],
      "built-in": ["工具内置", "随工具提供，不受当前仓库管理。"],
      "local-copy": ["本地独立", "工具目录中的独立副本，未链接到当前仓库。"],
      "external-link": ["外部链接", "链接到当前仓库之外的位置。"],
      broken: ["无效条目", "路径或链接当前无法正常读取。"],
    };
    const [label, description] = presentations[sourceType] || [
      "其他来源",
      `服务端返回了未识别的来源类型：${sourceType || "空值"}。`,
    ];
    return { label, description };
  }

  function inventoryFlagPresentation(flag) {
    const raw = String(flag || "");
    let label = "未知标记";
    if (raw === "duplicate-name") label = "名称重复";
    else if (raw === "broken-link") label = "链接已失效";
    else if (raw.startsWith("invalid-skill:")) label = "Skill 无效";
    return { label, raw };
  }

  function inventoryRecordIsFlagged(record) {
    return asArray(record && record.flags).length > 0
      || (record && record.source_type) === "broken";
  }

  function inventorySummary(records, visibleRecords) {
    const allRecords = asArray(records);
    const flaggedRecords = allRecords.filter(inventoryRecordIsFlagged);
    const duplicateGroups = new Set(
      flaggedRecords
        .filter((record) => asArray(record.flags).includes("duplicate-name"))
        .map((record) => record.name || record.slug),
    ).size;
    return {
      managed: allRecords.filter((record) => record.source_type === "managed").length,
      flagged: flaggedRecords.length,
      duplicateGroups,
      total: allRecords.length,
      visible: asArray(visibleRecords).length,
    };
  }

  function inventoryFailureMode(hasLoadedInventory) {
    return hasLoadedInventory ? "stale" : "empty";
  }

  function filterInventoryRecords(records, filters) {
    const selected = filters || {};
    const scope = selected.scope || "managed-or-flagged";
    const query = String(selected.query || "").trim().toLocaleLowerCase();
    const tool = selected.tool || "all";
    const source = selected.source || "all";
    const status = selected.status || "all";
    return asArray(records).filter((record) => {
      const flagged = inventoryRecordIsFlagged(record);
      const matchesScope = scope === "all"
        || (scope === "managed" && record.source_type === "managed")
        || (scope === "flagged" && flagged)
        || (scope === "managed-or-flagged" && (
          record.source_type === "managed" || flagged
        ));
      const searchable = [
        record.name,
        record.slug,
        record.path,
        record.raw_target,
        record.resolved_target,
      ].filter(Boolean).join(" ").toLocaleLowerCase();
      const matchesQuery = !query || searchable.includes(query);
      const matchesTool = tool === "all" || asArray(record.tools).includes(tool);
      const matchesSource = source === "all" || record.source_type === source;
      const matchesStatus = status === "all"
        || (status === "flagged" && flagged)
        || (status === "clean" && !flagged);
      return matchesScope && matchesQuery && matchesTool && matchesSource && matchesStatus;
    });
  }

  function sortInventoryRecords(records) {
    const tier = (record) => {
      if (inventoryRecordIsFlagged(record)) return 0;
      if (record.source_type === "managed") return 1;
      return 2;
    };
    const compareText = (left, right) => String(left || "").localeCompare(
      String(right || ""), "zh-CN", { sensitivity: "base" },
    );
    return [...asArray(records)].sort((left, right) => (
      tier(left) - tier(right)
      || compareText(left.name || left.slug, right.name || right.slug)
      || compareText(asArray(left.tools).join(","), asArray(right.tools).join(","))
      || compareText(left.path, right.path)
    ));
  }

  function summarizePlan(plan) {
    const changes = asArray(plan && plan.changes);
    const byAction = {};
    const byCode = {};
    changes.forEach((change) => {
      const action = change && change.action ? String(change.action) : "unknown";
      const code = change && change.code ? String(change.code) : "none";
      byAction[action] = (byAction[action] || 0) + 1;
      byCode[code] = (byCode[code] || 0) + 1;
    });
    return { total: changes.length, byAction, byCode };
  }

  function buildSkillRequest(action, apply) {
    if (action.kind === "adopt") {
      return { path: "/api/skills/adopt", body: { apply: Boolean(apply) } };
    }
    const all = action.skill === null;
    return {
      path: "/api/skills/set",
      body: {
        skill: all ? null : action.skill,
        all,
        tool: action.tool,
        on: action.on,
        apply: Boolean(apply),
      },
    };
  }

  function buildInstructionRequest(target, action, apply, fingerprint) {
    if (action.kind === "adopt") {
      return {
        path: "/api/instructions/adopt",
        body: {
          apply: Boolean(apply),
          replace_existing: Boolean(action.replaceExisting),
          expected_fingerprint: apply ? fingerprint : null,
        },
      };
    }
    return {
      path: "/api/instructions/set",
      body: {
        target,
        on: action.on,
        apply: Boolean(apply),
        expected_fingerprint: apply ? fingerprint : null,
      },
    };
  }

  function buildApplyRequest(previewRequest, preview) {
    const body = { ...previewRequest.body, apply: true };
    if (Object.prototype.hasOwnProperty.call(body, "expected_fingerprint")) {
      body.expected_fingerprint = preview.fingerprint;
    }
    return { path: previewRequest.path, body };
  }

  function flattenedChanges(payload) {
    if (Array.isArray(payload && payload.changes)) return payload.changes;
    const changes = payload && payload.changes ? payload.changes : {};
    return [
      ...asArray(changes.link_changes),
      ...asArray(changes.container_changes),
      ...asArray(changes.bridge_removals),
    ];
  }

  function dangerPreviewModel(preview) {
    const changes = flattenedChanges(preview);
    if (
      !preview
      || preview.ok !== true
      || !/^[0-9a-f]{64}$/.test(String(preview.fingerprint || ""))
      || !changes.some((change) => change.action === "replace")
    ) return null;
    return {
      fingerprint: preview.fingerprint,
      snapshotPath: preview.snapshot_path || "",
      changes,
    };
  }

  function buildApplyOutcomeModel(reviewedPreview, executionPayload, refreshProblem) {
    const hasExecutionResults = Boolean(
      executionPayload && Array.isArray(executionPayload.results),
    );
    const preWriteStateChanged = Boolean(
      hasExecutionResults
      && executionPayload.code === "state-changed"
      && executionPayload.results.every((result) => (
        result
        && result.ok === false
        && ["state-changed", "not-applied"].includes(result.code)
      )),
    );
    const isExecutionOutcome = hasExecutionResults && !preWriteStateChanged;
    return {
      kind: isExecutionOutcome
        ? (executionPayload.ok === false ? "execution-error" : "execution-success")
        : "preview-error",
      reviewedChanges: flattenedChanges(reviewedPreview),
      executionChanges: isExecutionOutcome ? flattenedChanges(executionPayload) : [],
      results: isExecutionOutcome ? executionPayload.results : [],
      problem: executionPayload && executionPayload.ok === false ? executionPayload : null,
      verificationProblem: executionPayload
        && executionPayload.code === "post-apply-verification-failed"
        ? executionPayload
        : null,
      refreshProblem: refreshProblem || null,
      showSessionReminder: isExecutionOutcome,
    };
  }

  function createApplyGuard() {
    let inFlight = false;
    return {
      async run(operation) {
        if (inFlight) return null;
        inFlight = true;
        try {
          return await operation();
        } finally {
          inFlight = false;
        }
      },
    };
  }

  function deepFreeze(value) {
    if (!value || typeof value !== "object" || Object.isFrozen(value)) return value;
    Object.values(value).forEach(deepFreeze);
    return Object.freeze(value);
  }

  function createReviewedPreview(request, payload, allowReplacement) {
    return deepFreeze({
      request: { path: request.path, body: { ...request.body } },
      payload,
      allowReplacement: Boolean(allowReplacement),
    });
  }

  function createPreviewCoordinator({ commit, setBusy }) {
    let generation = 0;
    return {
      async run(request, allowReplacement, load) {
        const currentGeneration = ++generation;
        const intent = deepFreeze({ path: request.path, body: { ...request.body } });
        commit(null);
        setBusy(true);
        try {
          let payload;
          let problem = null;
          try {
            payload = await load(intent);
          } catch (error) {
            problem = error.payload || { code: "request-failed", message: error.message };
            payload = error.payload || {
              mode: "plan",
              ok: false,
              changes: [],
              fingerprint: null,
              snapshot_path: null,
              message: problem.message,
              code: problem.code,
            };
          }
          if (currentGeneration !== generation) {
            return { accepted: false, reviewed: null, problem: null };
          }
          const reviewed = createReviewedPreview(intent, payload, allowReplacement);
          commit(reviewed);
          return { accepted: true, reviewed, problem };
        } finally {
          setBusy(false);
        }
      },
    };
  }

  async function settleApplyOperation(reviewedPreview, write, refresh) {
    let executionPayload = null;
    let problem = null;
    let refreshProblem = null;
    try {
      executionPayload = await write();
    } catch (error) {
      problem = error.payload || { code: "request-failed", message: error.message };
      if (Array.isArray(problem.results)) executionPayload = problem;
    }
    try {
      const refreshResult = await refresh();
      refreshProblem = refreshResult.ok ? null : refreshResult;
    } catch (error) {
      refreshProblem = error.payload || {
        ok: false,
        code: "status-refresh-failed",
        message: error.message,
      };
    }
    const outcome = executionPayload && Array.isArray(executionPayload.results)
      ? buildApplyOutcomeModel(reviewedPreview, executionPayload, refreshProblem)
      : null;
    return {
      executionPayload,
      problem,
      refreshProblem,
      outcome: outcome && outcome.kind !== "preview-error" ? outcome : null,
    };
  }

  const FOCUSABLE_SELECTOR = 'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"]):not([disabled])';
  const WRITE_BUSY_SELECTOR = ".operation-actions button, .instruction-actions button, .operation-bar button, .dialog-actions button, #danger-apply-button, #refresh-button, #inventory-refresh-button";

  function focusableControls(container) {
    return [...container.querySelectorAll(FOCUSABLE_SELECTOR)]
      .filter((control) => !control.hidden);
  }

  function restoreCapturedFocus(element, documentObject) {
    if (!element) return false;
    const target = element.isConnected === false && element.id
      ? documentObject.getElementById(element.id)
      : element;
    if (!target || typeof target.focus !== "function") return false;
    target.focus();
    return true;
  }

  function trapModalFocus(event, container, close) {
    if (event.key === "Escape") {
      event.preventDefault();
      close();
      return;
    }
    if (event.key !== "Tab") return;
    const controls = focusableControls(container);
    if (!controls.length) return;
    const first = controls[0];
    const last = controls[controls.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  function updateWriteBusy(documentObject, busy) {
    if (busy) {
      documentObject.querySelectorAll(WRITE_BUSY_SELECTOR).forEach((button) => {
        if (!Object.prototype.hasOwnProperty.call(button.dataset, "writeBusy")) {
          button.dataset.writeBusy = button.disabled ? "disabled" : "enabled";
        }
        button.disabled = true;
      });
      return;
    }
    documentObject.querySelectorAll("[data-write-busy]").forEach((button) => {
      button.disabled = button.dataset.writeBusy === "disabled";
      delete button.dataset.writeBusy;
    });
  }

  function releaseWriteBusyControl(control) {
    control.disabled = false;
    if (Object.prototype.hasOwnProperty.call(control.dataset, "writeBusy")) {
      control.dataset.writeBusy = "enabled";
    }
  }

  function toolSurfaceRows(surfaces, tool) {
    return [`${tool}-desktop`, `${tool}-cli`].map((key) => {
      const surface = asArray(surfaces).find((item) => item.key === key);
      return {
        key,
        label: key.endsWith("-desktop") ? "Desktop" : "CLI",
        installed: Boolean(surface && surface.installed),
      };
    });
  }

  function surfaceCoverageLabel(surfaces, includeTool) {
    return [...new Set(asArray(surfaces).map((surface) => {
      const suffix = surface.endsWith("-desktop")
        ? "Desktop"
        : (surface.endsWith("-cli") ? "CLI" : surface);
      if (!includeTool || suffix === surface) return suffix;
      const tool = surface.replace(/-(desktop|cli)$/, "");
      const family = TOOL_FAMILIES.find((item) => item.key === tool);
      return `${family ? family.label : tool} ${suffix}`;
    }))].join(" + ");
  }

  function loadPathRows(payload) {
    const rows = [{
      key: "repository",
      tool: "repository",
      label: "统一来源",
      scope: "仓库 Skills",
      path: `${payload.repo_root}/skills`,
      displayPath: `${payload.repo_root}/skills`,
      surfaces: [],
    }];
    asArray(payload.skills && payload.skills.adapters).forEach((adapter) => {
      const family = TOOL_FAMILIES.find((item) => item.key === adapter.tool);
      const surfaceLabels = asArray(adapter.surfaces).map((surface) => (
        surface.endsWith("-desktop") ? "Desktop" : "CLI"
      ));
      rows.push({
        key: adapter.key,
        tool: adapter.tool,
        label: family ? family.label : adapter.tool,
        scope: surfaceLabels.join(" + ") || adapter.key,
        path: adapter.root,
        displayPath: compactHomePath(adapter.root, adapter.home),
        surfaces: asArray(adapter.surfaces),
      });
    });
    return rows;
  }

  function uniqueMessages(records) {
    return [...new Set(asArray(records).map((record) => record.message).filter(Boolean))];
  }

  function routeStatus(records, missingIsAttention) {
    if (!records.length) {
      return missingIsAttention
        ? { status: "attention", statusLabel: "需要处理" }
        : { status: "muted", statusLabel: "未启用" };
    }
    const hasAttention = records.some((record) => ATTENTION_STATES.has(record.state));
    if (hasAttention) return { status: "attention", statusLabel: "需要处理" };
    const applicable = records.filter((record) => record.state !== "unavailable");
    const enabled = applicable.filter((record) => record.state === "enabled").length;
    if (applicable.length > 0 && enabled === applicable.length) {
      return { status: "healthy", statusLabel: "正常" };
    }
    if (enabled > 0) return { status: "partial", statusLabel: "部分启用" };
    if (records.every((record) => record.state === "manual")) {
      return { status: "muted", statusLabel: "手动配置" };
    }
    return { status: "muted", statusLabel: "未启用" };
  }

  function aggregateSkillTarget(targets, tool) {
    const matches = asArray(targets).filter((target) => target.tool === tool);
    if (!matches.length) {
      return {
        state: "unavailable",
        records: [],
        messages: [],
        message: "服务端未返回此工具的加载记录。",
      };
    }
    const attentionState = ["conflict", "error", "legacy", "broken"]
      .find((candidate) => matches.some((target) => target.state === candidate));
    const applicable = matches.filter((target) => target.state !== "unavailable");
    const enabled = applicable.filter((target) => target.state === "enabled").length;
    let selectedState;
    if (attentionState) selectedState = attentionState;
    else if (applicable.length > 0 && enabled === applicable.length) selectedState = "enabled";
    else if (enabled > 0) selectedState = "partial";
    else if (matches.every((target) => target.state === "unavailable")) selectedState = "unavailable";
    else selectedState = "disabled";
    const messages = uniqueMessages(matches);
    return {
      state: selectedState,
      records: matches,
      messages,
      message: messages.join("\n") || "服务端未返回补充说明。",
    };
  }

  function fallbackCopyText(path) {
    if (typeof document === "undefined" || !document.body) return false;
    const textarea = document.createElement("textarea");
    textarea.value = path;
    textarea.setAttribute("class", "copy-fallback");
    textarea.setAttribute("aria-hidden", "true");
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();
    let copied = false;
    try {
      copied = Boolean(document.execCommand && document.execCommand("copy"));
    } finally {
      textarea.remove();
    }
    return copied;
  }

  async function copyRootPath(path, clipboard, fallback = fallbackCopyText) {
    try {
      if (!clipboard || typeof clipboard.writeText !== "function") throw new Error("clipboard unavailable");
      await clipboard.writeText(path);
      return { ok: true, method: "clipboard", message: `已复制路径：${path}` };
    } catch (_error) {
      if (fallback(path)) {
        return { ok: true, method: "fallback", message: `已复制路径：${path}` };
      }
      return {
        ok: false,
        method: "manual",
        message: `浏览器阻止自动复制，请手动复制：${path}`,
      };
    }
  }

  async function copyText(
    text,
    clipboard = typeof navigator === "undefined" ? null : navigator.clipboard,
    fallback = fallbackCopyText,
    manual = () => {},
  ) {
    try {
      if (!clipboard || typeof clipboard.writeText !== "function") {
        throw new Error("clipboard unavailable");
      }
      await clipboard.writeText(text);
      return true;
    } catch (_error) {
      if (fallback(text)) return true;
      manual(text);
      return false;
    }
  }

  function buildTopology(payload) {
    const skills = payload && payload.skills ? payload.skills : {};
    const instructions = payload && payload.instructions ? payload.instructions : {};
    const adapters = asArray(skills.adapters);
    const skillTargets = asArray(skills.targets);
    const instructionTargets = asArray(instructions.targets);
    const manualInstructions = asArray(instructions.manual_surfaces);
    const repoSkillCount = asArray(skills.records).length;
    const pathRows = loadPathRows(payload);
    return TOOL_FAMILIES.map((family) => {
      const familySurfaceKeys = new Set(
        toolSurfaceRows(payload.surfaces, family.key).map((surface) => surface.key),
      );
      const toolAdapters = adapters.filter((adapter) => adapter.tool === family.key);
      const toolSkills = skillTargets.filter((target) => target.tool === family.key);
      const toolInstructions = [
        ...instructionTargets.filter((target) => (
          asArray(target.surfaces).some((surface) => familySurfaceKeys.has(surface))
        )),
        ...manualInstructions.filter((target) => (
          familySurfaceKeys.has(target.key)
          || asArray(target.surfaces).some((surface) => familySurfaceKeys.has(surface))
        )),
      ];
      const skillRoots = pathRows
        .filter((row) => row.tool === family.key)
        .map((row) => {
          const targets = toolSkills.filter((target) => target.adapter_key === row.key);
          return {
            key: row.key,
            fullPath: row.path,
            displayPath: row.displayPath,
            surfaces: row.surfaces,
            ...routeStatus(targets, false),
            messages: uniqueMessages(targets),
          };
        });
      const instructionHome = toolAdapters[0] && toolAdapters[0].home;
      const instructionRoots = toolInstructions.map((instruction) => {
        const declaredSurfaces = asArray(instruction.surfaces);
        const applicableSurfaces = declaredSurfaces.length
          ? declaredSurfaces.filter((surface) => familySurfaceKeys.has(surface))
          : [instruction.key].filter((surface) => familySurfaceKeys.has(surface));
        return {
          key: instruction.key,
          fullPath: instruction.path || "",
          displayPath: instruction.path
            ? compactHomePath(instruction.path, instructionHome || "")
            : "需要在工具设置中手动配置",
          surfaces: declaredSurfaces,
          coverageLabel: surfaceCoverageLabel(applicableSurfaces, false),
          ...routeStatus([instruction], true),
          messages: uniqueMessages([instruction]),
        };
      });
      const enabledSlugs = new Set(
        toolSkills
          .filter((target) => target.state === "enabled" || target.state === "legacy")
          .map((target) => target.slug),
      );
      return {
        tool: family.key,
        label: family.label,
        surfaces: toolSurfaceRows(payload.surfaces, family.key),
        skills: {
          lineStyle: "solid",
          ...routeStatus(toolSkills, toolAdapters.length === 0),
          roots: skillRoots,
          messages: uniqueMessages(toolSkills),
          countLabel: repoSkillCount
            ? `${enabledSlugs.size}/${repoSkillCount}`
            : null,
        },
        instructions: {
          lineStyle: "dashed",
          ...routeStatus(toolInstructions, true),
          roots: instructionRoots,
          messages: uniqueMessages(toolInstructions),
          attentionKey: (() => {
            const flagged = toolInstructions.filter((target) => (
              target.state === "conflict" || target.state === "broken"
            ));
            return flagged.length === 1 ? flagged[0].key : null;
          })(),
        },
      };
    });
  }

  function routeNodeClass(route) {
    const classes = ["route-node"];
    ["skills", "instructions"].forEach((channel) => {
      const status = route[channel] && route[channel].status;
      if (status && status !== "healthy") {
        classes.push(`route-node-${channel}-${status}`);
      }
    });
    return classes.join(" ");
  }

  if (globalThis.__AGENT_MANAGER_TEST__ === true) {
    globalThis.AgentManagerTest = Object.freeze({
      NAV_ICONS,
      buildTopology,
      routeNodeClass,
      messageLabel,
      statePresentation,
      repositoryHome,
      collectAttention,
      groupAttentionRecords,
      skillChannelActions,
      instructionRowActions,
      filterSkillRows,
      inventorySourcePresentation,
      inventoryFlagPresentation,
      inventorySummary,
      inventoryFailureMode,
      filterInventoryRecords,
      sortInventoryRecords,
      compactHomePath,
      summarizePlan,
      aggregateSkillTarget,
      toolSurfaceRows,
      surfaceCoverageLabel,
      loadPathRows,
      copyRootPath,
      copyText,
      buildSkillRequest,
      buildInstructionRequest,
      buildApplyRequest,
      dangerPreviewModel,
      buildApplyOutcomeModel,
      createApplyGuard,
      createPreviewCoordinator,
      settleApplyOperation,
      focusableControls,
      restoreCapturedFocus,
      trapModalFocus,
      updateWriteBusy,
      releaseWriteBusyControl,
    });
  }

  if (typeof document === "undefined") return;

  let previousDrawerFocus = null;
  let previousDialogFocus = null;

  function node(tag, text, className) {
    const element = document.createElement(tag);
    if (text !== undefined && text !== null) element.textContent = String(text);
    if (className) element.setAttribute("class", className);
    return element;
  }

  function clearNode(element) {
    while (element.firstChild) element.removeChild(element.firstChild);
  }

  function appendPath(parent, value, className) {
    const path = node("span", value || "—", className);
    path.title = value || "";
    parent.appendChild(path);
    return path;
  }

  function statePresentation(value) {
    const presentations = {
      enabled: ["已启用", "state-enabled"],
      missing: ["未启用", "state-muted"],
      disabled: ["未启用", "state-muted"],
      "matching-copy": ["内容相同", "state-partial"],
      "indirect-link": ["间接链接", "state-partial"],
      unavailable: ["未安装", "state-muted"],
      partial: ["部分启用", "state-partial"],
      manual: ["手动配置", "state-muted"],
      legacy: ["旧链接", "state-attention"],
      conflict: ["冲突", "state-attention"],
      broken: ["链接损坏", "state-error"],
      error: ["异常", "state-error"],
    };
    return presentations[value] || [value || "未知", "state-muted"];
  }

  function messageLabel(message) {
    const text = String(message == null ? "" : message);
    return MESSAGE_LABELS[text] || text;
  }

  function instructionRowActions(state, message) {
    const note = {
      "target is a directory": "目录不支持接管",
      "target is a special file": "特殊文件不支持接管",
    }[String(message == null ? "" : message)] || null;
    const actions = [];
    if (state === "missing") {
      actions.push({ kind: "enable", id: "enable", label: "启用" });
    }
    if (state === "enabled") {
      actions.push({ kind: "disable", id: "disable", label: "停用" });
    }
    if (state === "indirect-link" || state === "matching-copy") {
      actions.push({ kind: "adopt", id: "adopt", label: "转为直链" });
    }
    if ((state === "conflict" || state === "broken") && !note) {
      actions.push({ kind: "resolve", id: "adopt", label: "处理冲突" });
    }
    return { actions, note };
  }

  function skillChannelActions(state) {
    if (state === "enabled") {
      return { actions: [{ kind: "disable", label: "停用" }], note: null };
    }
    if (state === "partial") {
      return {
        actions: [
          { kind: "enable", label: "启用" },
          { kind: "disable", label: "停用" },
        ],
        note: null,
      };
    }
    if (state === "disabled" || state === "missing") {
      return { actions: [{ kind: "enable", label: "启用" }], note: null };
    }
    if (state === "legacy") {
      return {
        actions: [{ kind: "adopt", label: "接管旧链接" }],
        note: "接管操作会处理所有旧结构链接，预览会列出全部变更。",
      };
    }
    if (state === "conflict" || state === "broken" || state === "error") {
      return {
        actions: [{ kind: "enable", label: "启用" }],
        note: "加载位置被占用或损坏，预览会展示阻塞原因。",
      };
    }
    return { actions: [], note: null };
  }

  function exactMessage(record) {
    return record && record.message ? messageLabel(record.message) : "服务端未返回补充说明。";
  }

  function showToast(message) {
    document.getElementById("toast-region").textContent = message;
  }

  function openDrawer(model, returnFocus = document.activeElement) {
    const drawer = document.getElementById("details-drawer");
    if (drawer.hidden) previousDrawerFocus = returnFocus;
    document.getElementById("drawer-title").textContent = model.title;
    const body = document.getElementById("drawer-body");
    clearNode(body);
    model.render(body);
    drawer.hidden = false;
    const controls = focusableControls(drawer);
    if (controls.length) controls[0].focus();
  }

  function closeDrawer() {
    document.getElementById("details-drawer").hidden = true;
    restoreCapturedFocus(previousDrawerFocus, document);
    previousDrawerFocus = null;
  }

  function openDangerDialog(preview) {
    const model = dangerPreviewModel(preview);
    if (!model) return false;
    const dialog = document.getElementById("confirmation-dialog");
    previousDialogFocus = document.activeElement;
    const body = document.getElementById("confirmation-body");
    clearNode(body);
    body.appendChild(node("p", "将执行以下替换。请核对所有路径与快照位置。", "attention-copy"));
    appendChangeList(body, model.changes);
    appendDetail(body, "计划指纹", model.fingerprint);
    appendDetail(body, "快照位置", model.snapshotPath || "服务端未要求快照");
    dialog.showModal();
    const controls = focusableControls(dialog);
    if (controls.length) controls[0].focus();
    return true;
  }

  function closeDangerDialog() {
    const dialog = document.getElementById("confirmation-dialog");
    if (dialog.open) dialog.close();
    restoreCapturedFocus(previousDialogFocus, document);
    previousDialogFocus = null;
  }

  function appendDetail(parent, label, value) {
    const wrapper = node("div", null, "plan-detail");
    wrapper.appendChild(node("strong", label));
    appendPath(wrapper, value || "—", "path-text");
    parent.appendChild(wrapper);
  }

  function showDetails(title, fields, message, rawMessage) {
    openDrawer({
      title,
      render(body) {
        const list = node("dl", null, "detail-list");
        fields.forEach(([label, value, copyable]) => {
          list.appendChild(node("dt", label));
          const description = node("dd");
          appendPath(description, value || "—", "path-text");
          if (copyable && value) {
            const copyButton = node("button", "复制", "copy-path-button");
            copyButton.setAttribute("type", "button");
            copyButton.addEventListener("click", async () => {
              const result = await copyRootPath(value, navigator.clipboard);
              showToast(result.message);
            });
            description.appendChild(copyButton);
          }
          list.appendChild(description);
        });
        list.appendChild(node("dt", "服务端说明"));
        const messageNode = node("dd", message);
        if (rawMessage && rawMessage !== message) messageNode.title = rawMessage;
        list.appendChild(messageNode);
        body.appendChild(list);
      },
    });
  }

  function showManualCopy(text) {
    let textarea;
    openDrawer({
      title: "手工复制个人约束",
      render(body) {
        body.appendChild(node("p", "自动复制被浏览器阻止。请选中以下完整文本并复制。", "operation-error"));
        textarea = node("textarea", null, "manual-copy-text");
        textarea.value = text;
        textarea.readOnly = true;
        textarea.setAttribute("aria-label", "待复制的仓库个人约束");
        body.appendChild(textarea);
      },
    });
    textarea.focus();
    textarea.select();
  }

  async function api(path, body) {
    const options = { method: "POST", credentials: "same-origin", headers: {
      "Content-Type": "application/json",
      "X-Agent-Manager-Token": state.token,
    }, body: JSON.stringify(body) };
    const response = await fetch(path, options);
    const payload = await response.json();
    if (!response.ok) {
      const error = new Error(payload.message || `请求失败：HTTP ${response.status}`);
      error.payload = payload;
      throw error;
    }
    return payload;
  }

  function appendChangeList(parent, changes) {
    const list = node("ol", null, "plan-change-list");
    if (!changes.length) {
      list.appendChild(node("li", "服务端计划不包含文件变更。"));
    }
    changes.forEach((change) => {
      const item = node("li");
      item.appendChild(node("strong", change.action || "unknown"));
      appendPath(item, change.target || change.path || change.root || "—", "path-text");
      if (change.reason || change.message) {
        item.appendChild(node("span", change.reason || change.message, "plan-reason"));
      }
      list.appendChild(item);
    });
    parent.appendChild(list);
  }

  function formatProblem(problem) {
    if (!problem) return "unknown-error：请求失败";
    const path = problem.path ? ` · ${problem.path}` : "";
    return `${problem.code || "request-failed"}：${problem.message || "请求失败"}${path}`;
  }

  function recordOperationError(problem) {
    state.operationError = problem;
    if (state.status) {
      renderAttention(state.status);
      renderSkills(state.status);
      renderInstructions(state.status);
    }
    syncWriteBusy();
  }

  function renderPlanDrawer(
    payload,
    request,
    allowReplacement,
    problem,
    refreshProblem = null,
    returnFocus = document.activeElement,
  ) {
    openDrawer({
      title: payload.mode === "apply" ? "执行结果" : "确认变更",
      render(body) {
        if (problem) body.appendChild(node("p", formatProblem(problem), "operation-error"));
        if (refreshProblem) {
          body.appendChild(node("h3", "后续刷新失败"));
          body.appendChild(node("p", formatProblem(refreshProblem), "operation-error"));
        }
        if (payload.message) {
          body.appendChild(node("p", formatProblem(payload), payload.ok ? "plan-copy" : "operation-error"));
        }
        const changes = flattenedChanges(payload);
        appendChangeList(body, changes);
        if (payload.fingerprint) appendDetail(body, "计划指纹", payload.fingerprint);
        const snapshot = payload.snapshot_path
          || (payload.changes && payload.changes.snapshot_path);
        if (snapshot) appendDetail(body, "快照位置", snapshot);
        const blocked = payload.ok !== true || changes.some((change) => (
          ["blocked", "conflict", "error", "target-conflict", "unsupported-target"]
            .includes(change.action)
        ));
        const actions = node("div", null, "operation-actions");
        const applyButton = node("button", "确认执行", "primary-action");
        applyButton.setAttribute("type", "button");
        applyButton.disabled = blocked;
        applyButton.addEventListener("click", applyPreview);
        actions.appendChild(applyButton);
        if (
          blocked
          && allowReplacement
          && request.path === "/api/instructions/adopt"
          && request.body.replace_existing === false
        ) {
          const replacement = node("button", "替换现有文件…", "danger-button");
          replacement.setAttribute("type", "button");
          replacement.addEventListener("click", () => previewInstruction(
            null,
            { kind: "adopt", replaceExisting: true },
          ));
          actions.appendChild(replacement);
        }
        body.appendChild(actions);
        if (blocked) {
          body.appendChild(node(
            "p",
            "以下变更包含阻塞项，无法执行。请先处理上方问题后重试。",
            "operation-error",
          ));
        }
      },
    }, returnFocus);
  }

  const previewCoordinator = createPreviewCoordinator({
    commit(reviewed) {
      state.reviewedPreview = reviewed;
    },
    setBusy: setWriteBusy,
  });

  async function requestPreview(request, allowReplacement) {
    const returnFocus = document.activeElement;
    const outcome = await previewCoordinator.run(
      request,
      allowReplacement,
      (current) => api(current.path, current.body),
    );
    if (!outcome.accepted) return null;

    const { reviewed, problem } = outcome;
    if (problem) {
      recordOperationError(problem);
    } else {
      state.operationError = null;
      if (state.status) {
        renderAttention(state.status);
        renderSkills(state.status);
        renderInstructions(state.status);
      }
    }
    if (reviewed.request.body.replace_existing === true && dangerPreviewModel(reviewed.payload)) {
      closeDrawer();
      openDangerDialog(reviewed.payload);
    } else {
      renderPlanDrawer(
        reviewed.payload,
        reviewed.request,
        reviewed.allowReplacement,
        problem,
        null,
        returnFocus,
      );
    }
    syncWriteBusy();
    return problem ? null : reviewed.payload;
  }

  function syncWriteBusy() {
    updateWriteBusy(document, state.writeBusyCount > 0);
  }

  function setWriteBusy(busy) {
    state.writeBusyCount = Math.max(0, state.writeBusyCount + (busy ? 1 : -1));
    syncWriteBusy();
  }

  async function previewSkillSelection(action) {
    let selectedSkill = action.skill;
    if (action.kind !== "adopt" && selectedSkill === undefined) {
      const selected = [...state.selectedSkills];
      const total = skillRows(state.status || {}).length;
      if (selected.length === 1) selectedSkill = selected[0];
      else if (selected.length > 0 && selected.length === total) selectedSkill = null;
      else {
        showToast("批量接口仅支持单个 Skill 或全部 Skills；请选择一项或选择全部。");
        return null;
      }
    }
    return requestPreview(buildSkillRequest({ ...action, skill: selectedSkill }, false), false);
  }

  async function previewInstruction(target, action, allowReplacement = false) {
    return requestPreview(
      buildInstructionRequest(target, action, false, null),
      allowReplacement,
    );
  }

  async function refreshAfterWrite() {
    const statusPayload = await loadStatus();
    if (!statusPayload) {
      return state.lastStatusProblem || {
        ok: false,
        code: "status-refresh-failed",
        message: "status refresh failed",
      };
    }
    if (state.activeView === "inventory") {
      const inventoryPayload = await loadInventory(true);
      if (!inventoryPayload) {
        return state.lastInventoryProblem || {
          ok: false,
          code: "inventory-refresh-failed",
          message: "inventory refresh failed",
        };
      }
    }
    return { ok: true };
  }

  function appendResultList(parent, results) {
    const list = node("ol", null, "plan-change-list execution-result-list");
    if (!results.length) list.appendChild(node("li", "服务端返回空的执行结果列表。"));
    results.forEach((result) => {
      const item = node("li");
      item.appendChild(node(
        "strong",
        `${result.ok ? "成功" : "失败"} · ${result.code || "unknown"}`,
      ));
      const identity = result.key || result.slug || result.tool;
      if (identity) item.appendChild(node("span", identity, "plan-reason"));
      appendPath(item, result.path || "—", "path-text");
      if (result.message) item.appendChild(node("span", result.message, "plan-reason"));
      list.appendChild(item);
    });
    parent.appendChild(list);
  }

  function renderApplyOutcomeDrawer(outcome) {
    openDrawer({
      title: outcome.kind === "execution-success"
        ? (outcome.refreshProblem ? "应用完成，刷新失败" : "应用完成")
        : "应用结果需要处理",
      render(body) {
        body.appendChild(node("h3", "已确认的变更计划"));
        appendChangeList(body, outcome.reviewedChanges);
        body.appendChild(node("h3", "已执行结果"));
        appendResultList(body, outcome.results);
        if (outcome.executionChanges.length) {
          body.appendChild(node("h3", "服务端返回的执行变更"));
          appendChangeList(body, outcome.executionChanges);
        }
        if (outcome.verificationProblem) {
          body.appendChild(node("h3", "后续验证失败"));
          body.appendChild(node(
            "p",
            formatProblem(outcome.verificationProblem),
            "operation-error",
          ));
        } else if (outcome.problem) {
          body.appendChild(node("h3", "应用错误"));
          body.appendChild(node("p", formatProblem(outcome.problem), "operation-error"));
        }
        if (outcome.refreshProblem) {
          body.appendChild(node("h3", "后续刷新失败"));
          body.appendChild(node(
            "p",
            formatProblem(outcome.refreshProblem),
            "operation-error",
          ));
        }
        if (outcome.showSessionReminder) {
          body.appendChild(node(
            "p",
            "请开始新会话；若缓存规则仍生效，请重启 Desktop 或 CLI。",
            "plan-copy",
          ));
        }
      },
    });
  }

  const applyGuard = createApplyGuard();

  async function applyPreview() {
    const reviewed = state.reviewedPreview;
    if (!reviewed) return;
    return applyGuard.run(async () => {
      const request = buildApplyRequest(reviewed.request, reviewed.payload);
      setWriteBusy(true);
      let settled;
      try {
        settled = await settleApplyOperation(
          reviewed.payload,
          () => api(request.path, request.body),
          refreshAfterWrite,
        );
      } finally {
        setWriteBusy(false);
      }

      if (settled.problem) recordOperationError(settled.problem);
      else state.operationError = null;
      closeDangerDialog();
      if (settled.outcome) {
        renderApplyOutcomeDrawer(settled.outcome);
        if (!settled.problem && !settled.refreshProblem) {
          showToast("已应用。请开始新会话；若缓存规则仍生效，请重启 Desktop 或 CLI。");
        }
        return settled.executionPayload;
      }

      renderPlanDrawer(
        reviewed.payload,
        reviewed.request,
        reviewed.allowReplacement,
        settled.problem,
        settled.refreshProblem,
      );
      return null;
    });
  }

  function renderStoppedPage() {
    clearNode(document.body);
    const main = node("main", null, "stopped-service");
    main.setAttribute("tabindex", "-1");
    main.appendChild(node("span", "LOCAL ROUTING", "eyebrow"));
    main.appendChild(node("h1", "Agent Manager 已停止"));
    main.appendChild(node("p", "本地服务已安全关闭。需要继续管理时，请重新启动命令。"));
    document.body.appendChild(main);
    main.focus();
  }

  async function shutdownService() {
    const button = document.getElementById("shutdown-button");
    button.disabled = true;
    try {
      await api("/api/shutdown", {});
      renderStoppedPage();
    } catch (error) {
      const problem = error.payload || { code: "request-failed", message: error.message };
      recordOperationError(problem);
      showToast(`关闭失败：${formatProblem(problem)}`);
      button.disabled = false;
    }
  }

  async function loadStatus() {
    const refresh = document.getElementById("refresh-button");
    refresh.disabled = true;
    try {
      const payload = await fetch("/api/status", { method: "GET", credentials: "same-origin" })
        .then(async (response) => {
          const body = await response.json();
          if (!response.ok) {
            const error = new Error(body.message || `请求失败：HTTP ${response.status}`);
            error.payload = body;
            throw error;
          }
          return body;
        });
      state.lastStatusProblem = null;
      state.status = payload;
      document.getElementById("repository-name").textContent = "lucas-skills";
      appendRepositoryPath(payload.repo_root, repositoryHome(payload));
      document.getElementById("scanned-at").textContent = `最近扫描：${payload.scanned_at || "未提供"}`;
      renderOverview(payload);
      renderSkills(payload);
      renderInstructions(payload);
      return payload;
    } catch (error) {
      state.lastStatusProblem = error.payload || {
        ok: false,
        code: "status-refresh-failed",
        message: error.message,
      };
      renderLoadError(error);
      return null;
    } finally {
      releaseWriteBusyControl(refresh);
      syncWriteBusy();
    }
  }

  function appendRepositoryPath(path, home) {
    const target = document.getElementById("repository-path");
    target.textContent = compactHomePath(path, home) || "仓库路径不可用";
    target.title = path || "";
  }

  function renderOverview(payload) {
    const summary = payload.summary || {};
    const summaryNode = document.getElementById("status-summary");
    clearNode(summaryNode);
    [
      ["Skills（至少一处）", `${summary.skills_enabled || 0} / ${summary.skills_total || 0}`, false],
      ["个人约束", `${summary.instructions_enabled || 0} / ${summary.instructions_total || 0}`, false],
      ["冲突", summary.conflicts || 0, (summary.conflicts || 0) > 0],
      ["扫描问题", summary.issues || 0, (summary.issues || 0) > 0],
    ].forEach(([label, value, needsAttention]) => {
      const item = node("div", null, "status-item");
      item.appendChild(node("span", label, "status-label"));
      if (needsAttention) {
        const valueButton = node(
          "button",
          value,
          "status-value status-value-attention status-value-button",
        );
        valueButton.setAttribute("type", "button");
        valueButton.setAttribute("aria-label", `${label} ${value} 项，查看需要处理列表`);
        valueButton.addEventListener("click", focusAttentionList);
        item.appendChild(valueButton);
      } else {
        item.appendChild(node("strong", value, "status-value"));
      }
      summaryNode.appendChild(item);
    });
    renderTopology(payload);
    renderAttention(payload);
  }

  function renderTopology(payload) {
    const board = document.getElementById("topology-board");
    clearNode(board);
    const source = node("div", null, "source-node");
    source.appendChild(node("strong", "lucas-skills"));
    appendPath(source, payload.repo_root || "仓库路径不可用", "route-path");
    board.appendChild(source);

    const list = node("ul", null, "route-list");
    buildTopology(payload).forEach((route) => {
      const routeNode = node(
        "li",
        null,
        routeNodeClass(route),
      );
      const toolNode = node("div", null, "route-tool");
      toolNode.appendChild(node("h3", route.label));
      toolNode.appendChild(node(
        "span",
        route.surfaces.map((surface) => `${surface.label} ${surface.installed ? "已安装" : "未安装"}`).join(" · "),
        "route-surfaces",
      ));
      routeNode.appendChild(toolNode);
      [
        ["Skills", route.skills, "skills"],
        ["个人约束", route.instructions, "instructions"],
      ].forEach(([kind, channel, view]) => {
        const channelNode = node(
          "section",
          null,
          `route-channel line-${channel.lineStyle} status-${channel.status}`,
        );
        const statusText = channel.countLabel
          ? `${channel.statusLabel} · ${channel.countLabel}`
          : channel.statusLabel;
        channelNode.setAttribute("aria-label", `${route.label} ${kind}：${statusText}`);
        channelNode.appendChild(node("span", kind, "route-kind"));
        channelNode.appendChild(node("strong", statusText, "route-status"));
        if (channel.status !== "healthy") {
          const notes = channel.messages
            .map((message) => messageLabel(message))
            .filter((message, index, all) => message && all.indexOf(message) === index);
          if (notes.length) {
            const note = node("span", notes.join("；"), "route-note");
            note.title = channel.messages.join("\n");
            channelNode.appendChild(note);
          }
        }
        if (channel.status === "attention") {
          const go = node("button", "处理", "compact-action attention-action");
          go.setAttribute("type", "button");
          go.setAttribute("aria-label", `处理 ${route.label} ${kind} 异常`);
          go.addEventListener("click", () => jumpToAttentionTarget({ view, key: channel.attentionKey }));
          channelNode.appendChild(go);
        }
        routeNode.appendChild(channelNode);
      });
      list.appendChild(routeNode);
    });
    board.appendChild(list);
  }

  function collectAttention(payload) {
    const records = [];
    if (state.operationError) {
      records.push({
        label: state.operationError.code || "操作失败",
        message: formatProblem(state.operationError),
      });
    }
    asArray(payload.skills && payload.skills.issues).forEach((issue) => {
      records.push({
        label: `Skill 扫描 · ${issue.code || "问题"}`,
        message: exactMessage(issue),
        path: issue.path,
        group: "Skill 扫描",
      });
    });
    asArray(payload.skills && payload.skills.targets)
      .filter((target) => ATTENTION_STATES.has(target.state))
      .forEach((target) => {
        const family = TOOL_FAMILIES.find((item) => item.key === target.tool);
        const familyLabel = family ? family.label : target.tool;
        records.push({
          label: `Skill · ${target.slug} · ${familyLabel}`,
          message: exactMessage(target),
          view: "skills",
          slug: target.slug,
          group: `Skill · ${familyLabel}`,
        });
      });
    asArray(payload.instructions && payload.instructions.issues).forEach((issue) => {
      records.push({
        label: `个人约束扫描 · ${issue.code || "问题"}`,
        message: exactMessage(issue),
        path: issue.path,
        group: "个人约束扫描",
      });
    });
    asArray(payload.instructions && payload.instructions.targets)
      .filter((target) => ATTENTION_STATES.has(target.state))
      .forEach((target) => {
        records.push({
          label: `个人约束 · ${target.key}`,
          message: exactMessage(target),
          view: "instructions",
          key: target.key,
          group: "个人约束",
        });
      });
    if (payload.ok === false && payload.message) {
      const topMessage = messageLabel(payload.message);
      if (!records.some((record) => record.message === topMessage)) {
        records.push({ label: payload.code || "状态异常", message: topMessage });
      }
    }
    return records;
  }

  function groupAttentionRecords(records) {
    const list = asArray(records);
    if (list.length <= 8) return { flat: list, groups: [] };
    const flat = [];
    const grouped = new Map();
    list.forEach((record) => {
      if (!record.group) {
        flat.push(record);
        return;
      }
      if (!grouped.has(record.group)) grouped.set(record.group, []);
      grouped.get(record.group).push(record);
    });
    return {
      flat,
      groups: [...grouped.entries()].map(([label, items]) => ({
        label,
        records: items,
      })),
    };
  }

  function highlightJumpTarget(element) {
    if (!element) return;
    const target = element.closest("tr, li") || element;
    target.classList.add("jump-highlight");
    target.scrollIntoView({ block: "center" });
    window.setTimeout(() => target.classList.remove("jump-highlight"), 1600);
  }

  function jumpToAttentionTarget(record) {
    switchView(record.view);
    if (record.view === "skills") {
      document.getElementById("skill-state-filter").value = "attention";
      document.getElementById("skill-query").value = record.slug || "";
      if (state.status) renderSkills(state.status);
      if (record.slug) {
        highlightJumpTarget(document.querySelector(`[id^="skill-${record.slug}-"]`));
      }
    } else if (record.view === "instructions" && record.key) {
      highlightJumpTarget(document.getElementById(`instruction-${record.key}-details`));
    }
  }

  function focusAttentionList() {
    const list = document.getElementById("attention-list");
    list.setAttribute("tabindex", "-1");
    list.focus({ preventScroll: true });
    list.scrollIntoView({ block: "start" });
  }

  function appendAttentionRow(list, record, nested) {
    const item = node("li", null, `attention-copy${nested ? " attention-nested" : ""}`);
    const copy = node("div", null, "attention-record");
    copy.appendChild(node("strong", record.label));
    copy.appendChild(node("span", record.message));
    if (record.path) {
      appendPath(copy, record.path, "path-text attention-path");
    }
    item.appendChild(copy);
    if (record.view) {
      const go = node("button", "查看", "compact-action attention-action");
      go.setAttribute("type", "button");
      go.setAttribute("aria-label", `查看 ${record.label}`);
      go.addEventListener("click", () => jumpToAttentionTarget(record));
      item.appendChild(go);
    }
    list.appendChild(item);
  }

  function focusAttentionGroupToggle(label) {
    const toggles = document.querySelectorAll("#attention-list .attention-group-toggle");
    for (const toggle of toggles) {
      if (toggle.getAttribute("data-attention-group") === label) {
        toggle.focus();
        return;
      }
    }
  }

  function renderAttention(payload) {
    const attention = collectAttention(payload);
    const list = document.getElementById("attention-list");
    clearNode(list);
    document.getElementById("attention-count").textContent = `${attention.length} 项`;
    if (!attention.length) {
      list.appendChild(node("li", "当前扫描未发现冲突或异常。", "healthy-copy"));
      return;
    }
    const { flat, groups } = groupAttentionRecords(attention);
    flat.forEach((record) => appendAttentionRow(list, record, false));
    groups.forEach((group) => {
      const open = state.openAttentionGroups.has(group.label);
      const item = node("li", null, "attention-group");
      const toggle = node("button", null, "attention-group-toggle");
      toggle.setAttribute("type", "button");
      toggle.setAttribute("aria-expanded", String(open));
      toggle.setAttribute("data-attention-group", group.label);
      toggle.appendChild(node("strong", group.label));
      toggle.appendChild(node("span", `${group.records.length} 项`, "count-label"));
      toggle.appendChild(node("span", open ? "收起" : "展开全部", "attention-group-cue"));
      toggle.addEventListener("click", () => {
        if (open) state.openAttentionGroups.delete(group.label);
        else state.openAttentionGroups.add(group.label);
        renderAttention(payload);
        focusAttentionGroupToggle(group.label);
      });
      item.appendChild(toggle);
      list.appendChild(item);
      if (open) {
        group.records.forEach((record) => appendAttentionRow(list, record, true));
      }
    });
  }

  function skillRows(payload) {
    const targets = asArray(payload.skills && payload.skills.targets);
    return asArray(payload.skills && payload.skills.records).map((record) => {
      const recordTargets = targets.filter((target) => target.slug === record.slug);
      return {
        ...record,
        targets: recordTargets,
        states: [
          ...recordTargets.map((target) => target.state),
          ...TOOL_FAMILIES.map((family) => aggregateSkillTarget(recordTargets, family.key).state),
        ],
      };
    });
  }

  function renderSkillsBulkControls(rows) {
    const controls = document.getElementById("skills-bulk-controls");
    const selected = [...state.selectedSkills].filter((slug) => (
      rows.some((row) => row.slug === slug)
    ));
    state.selectedSkills = new Set(selected);
    controls.hidden = selected.length === 0;
    document.getElementById("skills-selection-count").textContent = `已选择 ${selected.length} 项`;
    const selectAll = document.getElementById("skills-select-all");
    selectAll.checked = rows.length > 0 && selected.length === rows.length;
    selectAll.indeterminate = selected.length > 0 && selected.length < rows.length;
  }

  function appendOperationButton(parent, label, handler, className) {
    const button = node("button", label, className);
    button.setAttribute("type", "button");
    button.addEventListener("click", handler);
    parent.appendChild(button);
    return button;
  }

  function showSkillDetails(record, family, aggregate, label) {
    openDrawer({
      title: `${record.name || record.slug} · ${family.label}`,
      render(body) {
        if (record.description) {
          const description = node("p", record.description, "plan-copy");
          description.title = record.description;
          body.appendChild(description);
        }
        appendDetail(body, "状态", label);
        aggregate.records.forEach((target) => {
          const suffix = target.adapter_key || family.key;
          appendDetail(body, `加载位置 · ${suffix}`, target.path);
          if (target.raw_target) {
            appendDetail(body, `链接指向 · ${suffix}`, target.raw_target);
          }
          if (target.resolved_target && target.resolved_target !== target.raw_target) {
            appendDetail(body, `实际解析 · ${suffix}`, target.resolved_target);
          }
        });
        const note = node(
          "p",
          aggregate.messages.map((message) => messageLabel(message)).join("；")
            || "服务端未返回补充说明。",
          "plan-copy",
        );
        note.title = aggregate.message;
        body.appendChild(note);
        const planned = skillChannelActions(aggregate.state);
        if (planned.note) body.appendChild(node("p", planned.note, "plan-copy"));
        const actions = node("div", null, "operation-actions");
        const handlers = {
          enable: () => previewSkillSelection({
            kind: "set", skill: record.slug, tool: family.key, on: true,
          }),
          disable: () => previewSkillSelection({
            kind: "set", skill: record.slug, tool: family.key, on: false,
          }),
          adopt: () => previewSkillSelection({ kind: "adopt" }),
        };
        planned.actions.forEach((action) => {
          appendOperationButton(actions, action.label, handlers[action.kind]);
        });
        if (actions.childNodes.length) body.appendChild(actions);
      },
    });
  }

  function renderSkills(payload) {
    const rows = skillRows(payload);
    const reviewedRequest = state.reviewedPreview && state.reviewedPreview.request;
    renderSkillsBulkControls(rows);
    const query = document.getElementById("skill-query").value;
    const stateFilter = document.getElementById("skill-state-filter").value;
    const filtered = filterSkillRows(rows, query, stateFilter);
    const body = document.getElementById("skills-body");
    clearNode(body);
    if (!filtered.length) {
      const row = node("tr");
      const cell = node("td", rows.length ? "没有符合筛选条件的 Skill。" : "仓库中没有可展示的 Skill。", "empty-cell");
      cell.setAttribute("colspan", "5");
      row.appendChild(cell);
      body.appendChild(row);
      syncWriteBusy();
      return;
    }
    filtered.forEach((record) => {
      const row = node("tr");
      const heading = node("th", null, "skill-heading-cell");
      heading.setAttribute("scope", "row");
      const identity = node("div", null, "skill-identity");
      const selection = node("input");
      selection.setAttribute("type", "checkbox");
      selection.setAttribute("aria-label", `选择 ${record.name || record.slug}`);
      selection.checked = state.selectedSkills.has(record.slug);
      selection.addEventListener("change", () => {
        if (selection.checked) state.selectedSkills.add(record.slug);
        else state.selectedSkills.delete(record.slug);
        renderSkillsBulkControls(rows);
      });
      identity.appendChild(selection);
      const copy = node("div", null, "skill-identity-copy");
      copy.appendChild(node("strong", record.name || record.slug));
      if (record.name && record.name !== record.slug) {
        copy.appendChild(node("span", record.slug, "skill-description path-text"));
      }
      if (record.description) {
        const description = node(
          "span", record.description, "skill-description skill-description-clamped",
        );
        description.title = record.description;
        copy.appendChild(description);
      }
      identity.appendChild(copy);
      heading.appendChild(identity);
      row.appendChild(heading);
      TOOL_FAMILIES.forEach((family) => {
        const cell = node("td");
        const aggregate = aggregateSkillTarget(record.targets, family.key);
        const [label, stateClass] = statePresentation(aggregate.state);
        const button = node("button", null, "cell-button route-status-button");
        button.id = `skill-${record.slug}-${family.key}-details`;
        button.setAttribute("type", "button");
        button.setAttribute(
          "aria-label",
          `${record.name || record.slug} · ${family.label}：${label}，查看详情`,
        );
        button.title = `查看 ${record.name || record.slug} · ${family.label} 详情`;
        button.appendChild(node("span", label, `state-text ${stateClass}`));
        button.addEventListener("click", () => showSkillDetails(
          record, family, aggregate, label,
        ));
        cell.appendChild(button);
        if (
          state.operationError
          && (
            aggregate.records.some((target) => target.path === state.operationError.path)
            || (
              reviewedRequest
              && reviewedRequest.path === "/api/skills/set"
              && reviewedRequest.body.skill === record.slug
              && [family.key, "all"].includes(reviewedRequest.body.tool)
            )
          )
        ) {
          cell.appendChild(node("span", formatProblem(state.operationError), "operation-error row-error"));
        }
        row.appendChild(cell);
      });
      body.appendChild(row);
    });
    syncWriteBusy();
  }

  function renderInstructions(payload) {
    const list = document.getElementById("instructions-list");
    clearNode(list);
    const instructions = payload.instructions || {};
    const records = asArray(instructions.targets);
    const reviewedRequest = state.reviewedPreview && state.reviewedPreview.request;
    if (!records.length) {
      list.appendChild(node("li", "没有可展示的个人约束目标。", "instruction-row"));
    }
    records.forEach((record) => {
      const row = node("li", null, "instruction-row");
      const button = node("button", record.key || "未知目标", "instruction-target-button");
      button.id = `instruction-${record.key}-details`;
      button.setAttribute("type", "button");
      const path = record.path || "需要在工具设置中手动配置";
      const pathNode = appendPath(row, path, "instruction-path");
      pathNode.setAttribute("data-label", "加载位置");
      const coverage = node(
        "span",
        surfaceCoverageLabel(record.surfaces, true) || record.key || "—",
      );
      coverage.setAttribute("data-label", "覆盖工具");
      row.appendChild(coverage);
      const [label, stateClass] = statePresentation(record.state);
      const status = node("span", label, `state-text ${stateClass}`);
      status.setAttribute("data-label", "状态");
      row.appendChild(status);
      const actions = node("div", null, "instruction-actions");
      actions.setAttribute("data-label", "操作");
      const sourceReady = instructions.source_text !== null;
      const plannedActions = instructionRowActions(record.state, record.message);
      const controls = plannedActions.actions.map((action) => {
        const handlers = {
          enable: () => previewInstruction(record.key, { kind: "set", on: true }),
          disable: () => previewInstruction(record.key, { kind: "set", on: false }),
          adopt: () => previewInstruction(record.key, { kind: "adopt", replaceExisting: false }),
          resolve: () => previewInstruction(
            record.key, { kind: "adopt", replaceExisting: false }, true,
          ),
        };
        const control = appendOperationButton(
          actions,
          action.label,
          handlers[action.kind],
          action.kind === "resolve" ? "compact-action danger-action" : "compact-action",
        );
        control.id = `instruction-${record.key}-${action.id}`;
        return control;
      });
      if (plannedActions.note) {
        actions.appendChild(node("span", plannedActions.note, "route-note"));
      }
      controls.forEach((control) => {
        control.disabled = !sourceReady;
        if (!sourceReady) control.title = "仓库说明来源不可用";
      });
      row.appendChild(actions);
      if (
        state.operationError
        && (
          state.operationError.path === record.path
          || (
            reviewedRequest
            && reviewedRequest.path === "/api/instructions/set"
            && [record.key, "all"].includes(reviewedRequest.body.target)
          )
          || (reviewedRequest && reviewedRequest.path === "/api/instructions/adopt")
        )
      ) {
        row.appendChild(node("p", formatProblem(state.operationError), "operation-error row-error"));
      }
      button.addEventListener("click", () => {
        showDetails(
          `个人约束 · ${record.key || "未知目标"}`,
          [
            ["状态", label],
            ["原始类型", instructionOriginalType(record)],
            ["目标路径", record.path, true],
            ["来源", record.source, true],
            ...(record.target_sha256 ? [["目标 SHA-256", record.target_sha256]] : []),
            ...(record.raw_target ? [["链接指向", record.raw_target, true]] : []),
            ...(record.resolved_target && record.resolved_target !== record.raw_target
              ? [["实际解析", record.resolved_target, true]]
              : []),
          ],
          exactMessage(record),
          record.message,
        );
      });
      row.insertBefore(button, row.firstChild);
      list.appendChild(row);
    });
    asArray(instructions.manual_surfaces).forEach((record) => {
      const row = node("li", null, "instruction-row manual-instruction-row");
      row.appendChild(node("strong", "Copilot Desktop"));
      const path = node("span", "无托管路径，仅支持手工设置", "instruction-path");
      path.setAttribute("data-label", "加载位置");
      row.appendChild(path);
      const coverage = node("span", "Copilot Desktop", "instruction-coverage");
      coverage.setAttribute("data-label", "覆盖工具");
      row.appendChild(coverage);
      const status = node("span", "手动配置", "state-text state-muted");
      status.setAttribute("data-label", "状态");
      row.appendChild(status);
      const guidance = node("div", null, "instruction-actions manual-guidance");
      guidance.setAttribute("data-label", "操作");
      const copy = node("button", "复制仓库个人约束", "compact-action");
      copy.setAttribute("type", "button");
      copy.disabled = instructions.source_text === null;
      copy.addEventListener("click", async () => {
        const copied = await copyText(
          instructions.source_text,
          navigator.clipboard,
          fallbackCopyText,
          showManualCopy,
        );
        if (copied) showToast("已复制仓库个人约束；请按步骤粘贴到 Copilot Desktop。");
      });
      guidance.appendChild(copy);
      if (instructions.source_text === null) {
        const issue = asArray(instructions.issues)[0];
        guidance.appendChild(node(
          "p",
          `来源不可用：${issue ? formatProblem(issue) : "source_text 为空"}`,
          "operation-error",
        ));
      }
      const setup = node("details", null, "manual-setup");
      setup.appendChild(node("summary", "设置步骤"));
      const steps = node("ol", null, "manual-steps");
      [
        "打开 GitHub Copilot Desktop Settings。",
        "打开 custom instructions。",
        "替换现有全局文本。",
        "保存设置。",
        "开始一个新会话。",
      ].forEach((step) => steps.appendChild(node("li", step)));
      setup.appendChild(steps);
      guidance.appendChild(setup);
      row.appendChild(guidance);
      list.appendChild(row);
    });
    syncWriteBusy();
  }

  function instructionOriginalType(record) {
    if (record.message === "target is a directory") return "directory";
    if (record.raw_target) return record.state === "broken" ? "broken symlink" : "symlink";
    if (record.target_sha256) return "regular file";
    if (record.state === "missing") return "missing";
    return "unreadable or special";
  }

  async function loadInventory(force) {
    if (state.inventoryLoading) return { ok: true, skipped: true };
    if (state.inventoryLoaded && !force) return { ok: true, skipped: true };
    state.inventoryLoading = true;
    const button = document.getElementById("inventory-refresh-button");
    button.disabled = true;
    try {
      const payload = await fetch("/api/inventory", { method: "GET", credentials: "same-origin" })
        .then(async (response) => {
          const body = await response.json();
          if (!response.ok) {
            const error = new Error(body.message || `请求失败：HTTP ${response.status}`);
            error.payload = body;
            throw error;
          }
          return body;
        });
      state.inventoryLoaded = true;
      state.lastInventoryProblem = null;
      state.inventoryRecords = asArray(payload.inventory);
      renderInventory();
      return payload;
    } catch (error) {
      state.lastInventoryProblem = error.payload || {
        ok: false,
        code: "inventory-refresh-failed",
        message: error.message,
      };
      if (inventoryFailureMode(state.inventoryLoaded) === "stale") {
        renderInventory();
        return null;
      }
      const body = document.getElementById("inventory-body");
      clearNode(body);
      const row = node("tr");
      const message = error.payload && error.payload.message ? error.payload.message : error.message;
      const cell = node("td", `库存加载失败：${message} 请检查路径权限后重试。`, "empty-cell");
      cell.setAttribute("colspan", "6");
      row.appendChild(cell);
      body.appendChild(row);
      document.getElementById("inventory-result-count").textContent = "加载失败";
      const summaryContainer = document.getElementById("inventory-summary");
      clearNode(summaryContainer);
      summaryContainer.appendChild(node(
        "p",
        "库存摘要不可用：最近一次刷新失败，以下操作前请先重试刷新。",
        "attention-copy",
      ));
      return null;
    } finally {
      state.inventoryLoading = false;
      releaseWriteBusyControl(button);
      syncWriteBusy();
    }
  }

  function inventoryFiltersFromControls() {
    return {
      scope: state.inventoryScope,
      query: document.getElementById("inventory-query").value,
      tool: document.getElementById("inventory-tool-filter").value,
      source: document.getElementById("inventory-source-filter").value,
      status: document.getElementById("inventory-status-filter").value,
    };
  }

  function resetInventoryFilters() {
    state.inventoryScope = "managed-or-flagged";
    document.getElementById("inventory-query").value = "";
    document.getElementById("inventory-tool-filter").value = "all";
    document.getElementById("inventory-source-filter").value = "all";
    document.getElementById("inventory-status-filter").value = "all";
    renderInventory();
  }

  function renderInventorySummary(summary) {
    const container = document.getElementById("inventory-summary");
    clearNode(container);
    const flaggedLabel = summary.duplicateGroups > 0
      ? `需要处理 · ${summary.duplicateGroups} 组重名`
      : "需要处理";
    [
      ["仓库受管", summary.managed, "summary-managed"],
      [flaggedLabel, summary.flagged, "summary-flagged"],
      ["当前结果", summary.visible, "summary-visible"],
      ["全部库存", summary.total, "summary-total"],
    ].forEach(([label, value, className]) => {
      const item = node("span", null, `inventory-summary-item ${className}`);
      item.appendChild(node("strong", value));
      item.appendChild(node("small", label));
      container.appendChild(item);
    });
  }

  function inventoryToolLabel(tool) {
    const family = TOOL_FAMILIES.find((item) => item.key === tool);
    return family ? family.label : tool;
  }

  function inventoryStatusLabels(record) {
    const flags = asArray(record.flags).map(inventoryFlagPresentation);
    if (!flags.length && record.source_type === "broken") {
      return [{ label: "路径无效", raw: "broken" }];
    }
    return flags;
  }

  function showInventoryDetails(record) {
    const source = inventorySourcePresentation(record.source_type);
    const statuses = inventoryStatusLabels(record);
    showDetails(
      `库存 · ${record.name || record.slug}`,
      [
        ["Slug", record.slug],
        ["来源", `${source.label}（${record.source_type || "空值"}）`],
        ["工具", asArray(record.tools).map(inventoryToolLabel).join(", ")],
        ["路径", record.path, true],
        ["原始目标", record.raw_target, true],
        ["解析目标", record.resolved_target, true],
        ["界面", asArray(record.surfaces).join(", ")],
        ["原始标记", statuses.map((item) => item.raw).join(", ") || "无"],
      ],
      statuses.length
        ? `需要处理：${statuses.map((item) => item.label).join("、")}`
        : source.description,
    );
  }

  function renderInventory() {
    document.querySelectorAll("[data-inventory-scope]").forEach((button) => {
      button.setAttribute(
        "aria-pressed",
        String(button.getAttribute("data-inventory-scope") === state.inventoryScope),
      );
    });
    const staleNotice = state.lastInventoryProblem
      ? "以下为上次成功扫描的结果；最近一次刷新失败，请重试刷新。"
      : null;
    const filtered = filterInventoryRecords(
      state.inventoryRecords,
      inventoryFiltersFromControls(),
    );
    const records = sortInventoryRecords(filtered);
    const summary = inventorySummary(state.inventoryRecords, records);
    renderInventorySummary(summary);
    if (staleNotice) {
      document.getElementById("inventory-summary").appendChild(
        node("p", staleNotice, "attention-copy"),
      );
    }
    document.getElementById("inventory-result-count").textContent = staleNotice
      ? `显示 ${summary.visible} / ${summary.total} 项（数据可能过期）`
      : `显示 ${summary.visible} / ${summary.total} 项`;
    const body = document.getElementById("inventory-body");
    clearNode(body);
    if (!records.length) {
      const row = node("tr");
      const cell = node(
        "td",
        state.inventoryRecords.length
          ? "当前筛选下没有库存记录。"
          : "全局库存为空。请确认各工具已安装，并在扫描后重试。",
        "empty-cell",
      );
      cell.setAttribute("colspan", "6");
      row.appendChild(cell);
      body.appendChild(row);
      return;
    }
    let previousDuplicateName = null;
    records.forEach((record) => {
      const flagged = inventoryRecordIsFlagged(record);
      const rowClasses = ["inventory-row"];
      if (record.source_type === "managed") rowClasses.push("inventory-row-managed");
      if (flagged) rowClasses.push("inventory-row-flagged");
      const row = node("tr", null, rowClasses.join(" "));
      const heading = node("th");
      heading.setAttribute("scope", "row");
      const identity = node("div", null, "inventory-identity");
      const duplicateName = asArray(record.flags).includes("duplicate-name")
        ? record.name || record.slug
        : null;
      const groupedContinuation = duplicateName !== null
        && duplicateName === previousDuplicateName;
      previousDuplicateName = duplicateName;
      const nameNode = node(
        "strong",
        "",
        groupedContinuation ? "inventory-name-repeat" : "",
      );
      if (groupedContinuation) {
        nameNode.appendChild(node("span", "同名 · ", "inventory-name-repeat-prefix"));
      }
      nameNode.appendChild(document.createTextNode(record.name || record.slug));
      identity.appendChild(nameNode);
      if (record.slug && record.slug !== record.name) {
        identity.appendChild(node("span", record.slug, "path-text"));
      }
      heading.appendChild(identity);
      row.appendChild(heading);

      const source = inventorySourcePresentation(record.source_type);
      const sourceCell = node("td");
      const sourceBadge = node("span", source.label, `source-badge source-${record.source_type || "unknown"}`);
      sourceBadge.title = source.description;
      sourceCell.appendChild(sourceBadge);
      row.appendChild(sourceCell);

      row.appendChild(node(
        "td",
        asArray(record.tools).map(inventoryToolLabel).join(", ") || "—",
        "inventory-tools",
      ));

      const statusCell = node("td", null, "inventory-statuses");
      const statuses = inventoryStatusLabels(record);
      if (!statuses.length) {
        statusCell.appendChild(node("span", "正常", "status-badge status-badge-healthy"));
      } else {
        statuses.forEach((status) => {
          const badge = node("span", status.label, "status-badge status-badge-attention");
          badge.title = status.raw;
          statusCell.appendChild(badge);
        });
      }
      row.appendChild(statusCell);

      const pathCell = node("td", null, "inventory-path-cell");
      appendPath(pathCell, record.path, "path-text");
      row.appendChild(pathCell);

      const actionCell = node("td", null, "inventory-action-cell");
      const detailButton = node("button", "查看详情", "inventory-detail-button table-action");
      detailButton.setAttribute("type", "button");
      detailButton.addEventListener("click", () => showInventoryDetails(record));
      actionCell.appendChild(detailButton);
      row.appendChild(actionCell);
      body.appendChild(row);
    });
  }

  function renderLoadError(error) {
    const message = error.payload && error.payload.message ? error.payload.message : error.message;
    document.getElementById("scanned-at").textContent = "最近扫描：失败";
    const summary = document.getElementById("status-summary");
    clearNode(summary);
    summary.appendChild(node("p", `状态加载失败：${message} 请确认本地服务仍在运行后重新扫描。`, "attention-copy"));
    const topology = document.getElementById("topology-board");
    clearNode(topology);
    topology.appendChild(node("p", "无法构建路由拓扑。请先恢复状态接口。", "attention-copy"));
    const list = document.getElementById("attention-list");
    clearNode(list);
    list.appendChild(node("li", message, "attention-copy"));
    document.getElementById("attention-count").textContent = "1 项";
  }

  function switchView(view) {
    closeDrawer();
    state.activeView = view;
    document.querySelectorAll("[data-view-panel]").forEach((panel) => {
      panel.hidden = panel.getAttribute("data-view-panel") !== view;
    });
    document.querySelectorAll("[data-view]").forEach((button) => {
      if (button.getAttribute("data-view") === view) button.setAttribute("aria-current", "page");
      else button.removeAttribute("aria-current");
    });
    if (view === "inventory") loadInventory(false);
    document.getElementById("main-content").focus();
  }

  function navIcon(view) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("width", "16");
    svg.setAttribute("height", "16");
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("stroke-width", "2");
    svg.setAttribute("stroke-linecap", "round");
    svg.setAttribute("stroke-linejoin", "round");
    svg.setAttribute("aria-hidden", "true");
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", NAV_ICONS[view] || "");
    svg.appendChild(path);
    return svg;
  }

  function bootstrap() {
    const tokenMeta = document.querySelector('meta[name="agent-manager-token"]');
    state.token = tokenMeta ? tokenMeta.getAttribute("content") || "" : "";
    if (tokenMeta) tokenMeta.remove();
    document.querySelectorAll("[data-view]").forEach((button) => {
      button.insertBefore(navIcon(button.getAttribute("data-view")), button.firstChild);
      button.addEventListener("click", () => switchView(button.getAttribute("data-view")));
    });
    document.getElementById("refresh-button").addEventListener("click", loadStatus);
    document.getElementById("inventory-refresh-button").addEventListener("click", () => loadInventory(true));
    document.querySelectorAll("[data-inventory-scope]").forEach((button) => {
      button.addEventListener("click", () => {
        state.inventoryScope = button.getAttribute("data-inventory-scope");
        renderInventory();
      });
    });
    document.getElementById("inventory-query").addEventListener("input", renderInventory);
    ["inventory-tool-filter", "inventory-source-filter", "inventory-status-filter"]
      .forEach((id) => document.getElementById(id).addEventListener("change", renderInventory));
    document.getElementById("inventory-clear-filters").addEventListener(
      "click", resetInventoryFilters,
    );
    document.getElementById("shutdown-button").addEventListener("click", shutdownService);
    document.getElementById("skills-enable-button").addEventListener("click", () => previewSkillSelection({
      kind: "set",
      tool: document.getElementById("skills-bulk-tool").value,
      on: true,
    }));
    document.getElementById("skills-disable-button").addEventListener("click", () => previewSkillSelection({
      kind: "set",
      tool: document.getElementById("skills-bulk-tool").value,
      on: false,
    }));
    document.getElementById("skills-adopt-button").addEventListener("click", () => previewSkillSelection({
      kind: "adopt",
    }));
    document.getElementById("skills-select-all").addEventListener("change", (event) => {
      const rows = skillRows(state.status || {});
      state.selectedSkills = event.target.checked
        ? new Set(rows.map((row) => row.slug))
        : new Set();
      if (state.status) renderSkills(state.status);
    });
    document.getElementById("skill-query").addEventListener("input", () => {
      if (state.status) renderSkills(state.status);
    });
    document.getElementById("skill-state-filter").addEventListener("change", () => {
      if (state.status) renderSkills(state.status);
    });
    const drawer = document.getElementById("details-drawer");
    drawer.addEventListener("keydown", (event) => trapModalFocus(event, drawer, closeDrawer));
    document.getElementById("drawer-close-button").addEventListener("click", closeDrawer);
    const dialog = document.getElementById("confirmation-dialog");
    dialog.addEventListener("keydown", (event) => trapModalFocus(event, dialog, closeDangerDialog));
    dialog.addEventListener("cancel", (event) => {
      event.preventDefault();
      closeDangerDialog();
    });
    document.querySelector("[data-dialog-close]").addEventListener("click", closeDangerDialog);
    document.getElementById("danger-apply-button").addEventListener("click", applyPreview);
    loadStatus();
  }

  bootstrap();
})();
