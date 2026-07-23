"use strict";

(() => {
  const CLIENT_VERSION = "1";
  const SCHEMA_VERSION = 1;
  const app = document.getElementById("app");
  let bridge = null;
  let latestRevision = -1;
  let targetAddresses = new Set();

  const allowedLayouts = new Set(["split", "unified"]);
  const allowedModes = new Set(["simple", "standard", "detailed"]);
  const allowedSections = new Set(["code", "literal", "data", "bss", "global", "heap", "stack"]);
  const sectionLabels = {
    code: ["代码区", "只读"],
    literal: ["常量区", "只读"],
    data: ["数据段", "已初始化"],
    bss: ["BSS 段", "静态存储"],
    global: ["全局区", "静态存储"],
    heap: ["堆", "↑ 向高地址增长"],
    stack: ["栈", "↓ 向低地址增长"],
  };
  const layoutLabels = { split: "Split", unified: "Unified" };
  const modeLabels = { simple: "Simple", standard: "Standard", detailed: "Detailed" };

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function reportError(phase, error) {
    const message = error instanceof Error ? `${error.message}\n${error.stack || ""}` : String(error);
    if (bridge) bridge.reportError(phase, message.slice(0, 1000));
    const page = element("div", "frontend-error");
    const panel = element("section", "error-panel");
    panel.append(element("div", "error-title", "内存可视化无法显示"));
    panel.append(element("div", "error-copy", `${phase}: ${message}`));
    page.append(panel);
    app.replaceChildren(page);
  }

  function addressText(address) {
    return address && typeof address.text === "string" ? address.text : "-";
  }

  function displayNormalized(value) {
    if (value === null || value === undefined) return "null";
    if (typeof value !== "object") return String(value);
    if (value.type === "list" || value.type === "set") return (value.items || []).map(displayNormalized).join(", ");
    if (value.type === "map") return (value.entries || []).map((entry) => `${displayNormalized(entry.key)}: ${displayNormalized(entry.value)}`).join(", ");
    return String(value.value ?? value.type ?? "");
  }

  function renderByteCells(item) {
    const grid = element("div", "byte-grid");
    const size = Math.max(0, Number(item.size) || 0);
    const stride = Math.max(1, Number(item.stride) || 1);
    if (!size) return grid;
    grid.title = `地址: ${addressText(item.address)} ~ 0x${(item.address.value + size - 1).toString(16).toUpperCase().padStart(8, "0")}\n大小: ${size} 字节  步长: ${stride}B`;
    for (let index = 0; index < size; index += 1) {
      grid.append(element("span", `byte-cell${index > 0 && index % stride === 0 ? " boundary" : ""}`));
    }
    return grid;
  }

  function activatePointerTarget(card, active) {
    const target = card.dataset.pointerTarget;
    if (!target) return;
    document.querySelectorAll("[data-address]").forEach((candidate) => {
      if (candidate.dataset.address === target) candidate.classList.toggle("pointer-target-active", active);
    });
  }

  function renderPointerRelation(card, item) {
    if (!item.isPointer) return;
    const hasAddress = Boolean(item.pointerTargetAddress);
    const alive = Boolean(hasAddress && item.pointerTargetAlive);
    const relation = element("div", `pointer-meta${!hasAddress ? " is-null" : alive ? "" : " is-invalid"}`);
    relation.append(element("span", "pointer-state"));
    const target = hasAddress ? addressText(item.pointerTargetAddress) : "nullptr";
    const label = !hasAddress ? `空指针 · ${target}` : alive ? `指向 ${target}` : `目标已失效 · ${target}`;
    relation.append(element("span", "", label));
    card.append(relation);
    if (hasAddress) {
      card.dataset.pointerTarget = target;
      card.tabIndex = 0;
      card.setAttribute("aria-label", `${item.name}，${label}`);
      card.addEventListener("mouseenter", () => activatePointerTarget(card, true));
      card.addEventListener("mouseleave", () => activatePointerTarget(card, false));
      card.addEventListener("focus", () => activatePointerTarget(card, true));
      card.addEventListener("blur", () => activatePointerTarget(card, false));
    }
  }

  function appendMetaPair(parent, label, value) {
    const item = element("span", "");
    item.append(element("span", "", `${label} `), element("strong", "", value));
    parent.append(item);
  }

  function renderVariable(item) {
    const classes = [item.kind === "container" ? "container-card" : "variable-card"];
    if (item.highlighted) classes.push("highlighted");
    if (targetAddresses.has(addressText(item.address))) classes.push("pointer-target");
    const card = element("article", classes.join(" "));
    card.dataset.address = addressText(item.address);
    card.dataset.kind = item.kind;
    card.dataset.name = item.qualifiedName || item.name;

    const primary = element("div", "card-primary");
    primary.append(element("span", "var-name", item.name));
    if (item.kind !== "container") primary.append(element("span", "equals", "="), element("span", "var-value", item.displayValue));
    card.append(primary);

    if (item.kind === "container") renderContainerContent(card, item);
    const meta = element("div", "card-meta");
    meta.append(element("span", "type-badge", item.type));
    meta.append(element("span", "address", addressText(item.address)));
    if (item.size > 0) meta.append(element("span", "meta", `${item.size}B${item.stride > 0 ? ` · stride ${item.stride}B` : ""}`));
    if (item.kind !== "container") meta.append(renderByteCells(item));
    card.append(meta);
    if (item.size > item.stride && item.stride > 0) card.append(element("div", "array-meta", `${Math.floor(item.size / item.stride)} 个元素 × ${item.stride}B`));
    renderPointerRelation(card, item);
    return card;
  }

  function renderContainerContent(card, item) {
    const meta = element("div", "container-meta");
    const content = item.content || {};
    const values = element("div", "container-values");
    if (item.containerKind === "vector") {
      const items = content.items || [];
      appendMetaPair(meta, "size", String(items.length));
      appendMetaPair(meta, "capacity", String(item.capacity));
      if (item.heapDataAddress) appendMetaPair(meta, "heap", addressText(item.heapDataAddress));
      items.forEach((value, index) => values.append(element("span", "container-value", `${index}: ${displayNormalized(value)}`)));
    } else if (item.containerKind === "unordered_map") {
      const entries = content.entries || [];
      appendMetaPair(meta, "size", String(entries.length));
      entries.slice(0, 8).forEach((entry) => {
        const row = element("div", "map-entry");
        row.append(element("span", "map-key", `[${displayNormalized(entry.key)}]`), element("span", "map-arrow", "→"), element("span", "map-value", displayNormalized(entry.value)));
        values.append(row);
      });
      if (entries.length > 8) values.append(element("span", "meta", `共 ${entries.length} 个键值对`));
    } else if (item.containerKind === "string") {
      const text = String(content.value || "");
      appendMetaPair(meta, "length", String(text.length));
      values.append(element("span", "container-value", `"${text.slice(0, 40)}${text.length > 40 ? "…" : ""}"`));
    } else if (item.containerKind === "unordered_set") {
      const items = content.items || [];
      appendMetaPair(meta, "size", String(items.length));
      items.slice(0, 12).forEach((value) => values.append(element("span", "container-value", displayNormalized(value))));
      if (items.length > 12) values.append(element("span", "meta", `共 ${items.length} 个元素`));
    }
    card.append(meta);
    if (values.childNodes.length) card.append(values);
  }

  function renderObject(item) {
    const classes = ["object-card"];
    if (item.highlighted) classes.push("highlighted");
    if (targetAddresses.has(addressText(item.baseAddress))) classes.push("pointer-target");
    const card = element("article", classes.join(" "));
    card.dataset.kind = "object";
    card.dataset.name = item.name;
    card.dataset.address = addressText(item.baseAddress);

    const head = element("div", "object-head");
    const identity = element("div", "object-identity");
    identity.append(element("span", "var-name", item.name), element("span", "type-badge", item.className));
    head.append(identity, element("div", "object-meta", `${item.totalSize}B · ${addressText(item.baseAddress)}`));
    card.append(head);

    const layout = element("div", "struct-layout");
    const grid = element("div", "struct-grid");
    const legend = element("div", "struct-legend");
    const limit = Math.min(Number(item.totalSize) || 0, 32);
    const byteInfo = Array.from({ length: limit }, (_, offset) => ({ offset, color: null, label: "padding" }));
    (item.segments || []).forEach((segment) => {
      for (let byte = 0; byte < segment.size && segment.offset + byte < limit; byte += 1) byteInfo[segment.offset + byte] = { offset: segment.offset + byte, color: segment.color, label: segment.label };
    });
    byteInfo.forEach((info) => {
      const segmentIndex = (item.segments || []).findIndex((segment) => segment.color === info.color);
      const colorClass = segmentIndex >= 0 ? ` member-color-${segmentIndex % 8}` : " padding";
      const cell = element("span", `struct-cell${colorClass}`);
      const absolute = item.baseAddress.value + info.offset;
      cell.title = `+${info.offset}  ${info.label}  0x${absolute.toString(16).toUpperCase().padStart(8, "0")}`;
      grid.append(cell);
    });
    (item.members || []).forEach((member, index) => {
      const legendItem = element("span", "legend-item");
      legendItem.append(element("span", `legend-swatch member-color-${index % 8}`), element("span", "", `${member.name} +${member.address.value - item.baseAddress.value}`));
      legend.append(legendItem);
    });
    if ((item.padding || []).length) {
      const paddingItem = element("span", "legend-item padding-legend");
      const totalPadding = item.padding.reduce((sum, padding) => sum + padding.size, 0);
      paddingItem.append(element("span", "legend-swatch padding"), element("span", "", `padding ${totalPadding}B`));
      legend.append(paddingItem);
    }
    layout.append(grid, legend);
    card.append(layout);
    if (item.totalSize > 32) card.append(element("div", "object-truncated", `显示前 32B，总大小 ${item.totalSize}B`));

    const members = element("div", "member-list");
    (item.members || []).forEach((member, index) => {
      const row = element("div", "member-row");
      row.dataset.address = addressText(member.address);
      row.dataset.name = member.qualifiedName || member.name;
      row.append(element("span", `member-dot member-color-${index % 8}`), element("span", "type-badge", member.type), element("span", "var-name", member.name), element("span", "equals", "="), element("span", "var-value", member.displayValue), element("span", "member-address", addressText(member.address)));
      members.append(row);
    });
    card.append(members);
    return card;
  }

  function renderFrame(frame, isCurrent) {
    const box = element("section", `stack-frame${isCurrent ? " is-current" : ""}`);
    box.dataset.frameId = frame.id;
    if (isCurrent) box.setAttribute("aria-current", "true");
    const title = element("div", "frame-title");
    title.append(element("span", "frame-function", `${frame.functionName}()`));
    if (frame.returnLine !== null && frame.returnLine !== undefined) title.append(element("span", "frame-return", `返回第 ${frame.returnLine + 1} 行`));
    if (isCurrent) title.append(element("span", "current-badge", "当前"));
    box.append(title);
    const body = element("div", "frame-body");
    if (!frame.items.length) body.append(element("div", "section-empty", "无局部变量"));
    frame.items.forEach((item) => body.append(item.kind === "object" ? renderObject(item) : renderVariable(item)));
    box.append(body);
    return box;
  }

  function renderSection(section) {
    const key = allowedSections.has(section.key) ? section.key : "global";
    const panel = element("section", `memory-section section-${key}`);
    panel.dataset.section = key;
    panel.setAttribute("aria-label", section.title);
    const title = element("h2", "section-title");
    const [name, description] = sectionLabels[key];
    const count = Array.isArray(section.items) ? section.items.length : 0;
    title.append(
      element("span", "section-marker"),
      element("span", "section-name", name),
      element("span", "section-count", String(count)),
      element("span", "section-description", description)
    );
    panel.append(title);
    const body = element("div", "section-body");
    if (!section.items || !section.items.length) {
      body.append(element("div", "section-empty", "暂无数据"));
    } else if (key === "stack") {
      section.items.forEach((frame, index) => body.append(renderFrame(frame, index === section.items.length - 1)));
    } else {
      section.items.forEach((item) => body.append(renderVariable(item)));
    }
    panel.append(body);
    return panel;
  }

  function renderWorkspaceHeader(state, layout, mode) {
    const header = element("header", "workspace-header");
    const identity = element("div", "workspace-identity");
    identity.append(element("h1", "workspace-title", "Memory"));
    const labels = element("div", "workspace-labels");
    labels.append(
      element("span", "workspace-label layout-label", layoutLabels[layout]),
      element("span", "workspace-label mode-label", modeLabels[mode])
    );
    const status = element("div", "workspace-status");
    status.append(
      element("span", "workspace-step", state.step ? `Line ${state.step.lineIndex + 1}` : "Not started"),
      element("span", "workspace-revision", `rev ${state.revision}`)
    );
    identity.append(labels);
    header.append(identity, status);
    return header;
  }

  function renderEnvironment(environment) {
    const bar = element("div", "env-bar");
    const architecture = element("span", "env-group");
    architecture.append(element("span", "env-label", environment.architecture), element("span", "", "Little Endian"));
    const directions = element("span", "env-group");
    directions.append(element("span", "env-direction", "Stack ↓"), element("span", "env-direction", "Heap ↑"));
    const sizes = element("span", "env-group");
    sizes.append(element("span", "", "char 1B"), element("span", "", "int/float 4B"), element("span", "", "double/ptr 8B"), element("span", "", "自然对齐"));
    bar.append(architecture, directions, sizes);
    return bar;
  }

  function renderCrash(crash) {
    const panel = element("section", "crash-bar crash-panel");
    panel.setAttribute("role", "alert");
    panel.append(element("span", "crash-status", "执行已暂停"));
    const title = element("div", "crash-title", crash.title);
    if (crash.ptrName) title.append(element("span", "crash-pointer", `  ${crash.ptrName} = ${addressText(crash.ptrValue)}`));
    panel.append(title, element("div", "crash-cause", crash.cause));
    if (crash.detail) panel.append(element("div", "crash-detail", crash.detail));
    return panel;
  }

  function renderAddressAxis() {
    const axis = element("aside", "address-axis");
    axis.setAttribute("aria-label", "虚拟地址空间示意");
    axis.append(element("div", "axis-high", "高地址\n0xFFFFFFFF"), element("div", "axis-line"), element("div", "axis-low", "0x00000000\n低地址"));
    axis.append(element("div", "axis-note", "示意地址空间"));
    return axis;
  }

  function unifiedSections(sections) {
    const order = ["stack", "heap", "global", "data", "bss", "literal", "code"];
    return [...sections].sort((left, right) => order.indexOf(left.key) - order.indexOf(right.key));
  }

  function renderState(state) {
    if (!state || state.schemaVersion !== SCHEMA_VERSION) throw new Error(`不支持的 schemaVersion: ${state && state.schemaVersion}`);
    if (!Number.isInteger(state.revision)) throw new Error("状态缺少有效 revision");
    if (state.revision < latestRevision) return;
    latestRevision = state.revision;
    const layout = allowedLayouts.has(state.render.layout) ? state.render.layout : "split";
    const mode = allowedModes.has(state.render.segMode) ? state.render.segMode : "standard";
    const root = element("div", "visualizer");
    root.dataset.revision = String(state.revision);
    root.dataset.layout = layout;
    root.dataset.segMode = mode;
    root.append(renderWorkspaceHeader(state, layout, mode), renderEnvironment(state.environment));
    if (state.step && state.step.crash) root.append(renderCrash(state.step.crash));
    const scroll = element("div", "memory-scroll");
    if (!state.step) {
      const empty = element("div", "empty-state");
      empty.setAttribute("role", "status");
      empty.append(element("div", "empty-title", "尚无内存快照"), element("div", "empty-copy", "运行代码并执行到具体步骤后，将在这里显示内存布局。"));
      scroll.append(empty);
    } else {
      targetAddresses = new Set();
      state.step.sections.forEach((section) => {
        if (section.key === "stack") section.items.forEach((frame) => frame.items.forEach(collectPointerTargets));
        else section.items.forEach(collectPointerTargets);
      });
      const grid = element("div", `memory-grid ${layout} ${mode}`);
      const sections = layout === "unified" ? unifiedSections(state.step.sections) : state.step.sections;
      if (layout === "unified") grid.append(renderAddressAxis());
      sections.forEach((section) => grid.append(renderSection(section)));
      scroll.append(grid);
    }
    root.append(scroll);
    app.replaceChildren(root);
  }

  function collectPointerTargets(item) {
    if (item.kind === "object") {
      item.members.forEach(collectPointerTargets);
      return;
    }
    if (item.pointerTargetAddress && item.pointerTargetAlive) targetAddresses.add(addressText(item.pointerTargetAddress));
  }

  function parseAndRender(payload) {
    try {
      renderState(JSON.parse(payload));
    } catch (error) {
      reportError("render", error);
    }
  }

  window.addEventListener("error", (event) => reportError("bootstrap", event.error || event.message));
  window.addEventListener("unhandledrejection", (event) => reportError("promise", event.reason));

  document.addEventListener("DOMContentLoaded", () => {
    try {
      if (typeof QWebChannel !== "function" || !window.qt || !qt.webChannelTransport) throw new Error("QWebChannel transport 不可用");
      new QWebChannel(qt.webChannelTransport, (channel) => {
        bridge = channel.objects.memoryBridge;
        bridge.stateChanged.connect(parseAndRender);
        bridge.ready(CLIENT_VERSION);
        bridge.getInitialState((payload) => parseAndRender(payload));
      });
    } catch (error) {
      reportError("bootstrap", error);
    }
  });
})();
