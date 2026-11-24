"use strict";

const get = (id) => document.getElementById(id);
const fields = get("settings-fields");
const status = get("status");
const logs = get("logs");
const buttons = {start: get("start"), pause: get("pause"), stop: get("stop"), save: get("save")};
const format = new Intl.NumberFormat();
let sequence = 0;
let logLines = [];
let farm = null;
let loaded = false;
let busy = false;
let serialOverride = null;
let controlVersion = 0;
let catalog;
let baseline = {};
let edits = {};
let activeProfile = "";
const minimumFields = new Set(["search.min_gold", "search.min_elixir", "search.min_dark"]);
const useMinimums = "search.minimums_by_hand";
const inverseSwitches = new Set([useMinimums, "search.maintain_only"]);
const resourceNames = {gold: "Gold", elixir: "Elixir", dark: "Dark elixir"};
const pageIcons = {dashboard: "◴", home_village: "⌂", builder_base: "⚒", wars_and_raids: "⚔",
  when_to_play: "▦", like_a_person: "◎", history: "◷", advanced: "⚙", farms: "◉"};
const compactLayout = window.matchMedia("(max-width: 46rem)");
const refreshControls = new Set(["device.mode", "bot.mode", "bot.auto_first", "schedule.enabled", "schedule.breaks",
  "search.maintain_only"]);
const openGroups = new Set();
const lastTab = new Map();
let pageKey = "dashboard";
let tabKey = "dashboard";
let fieldsByPath;
let profiles = [];
let readyDetail = "";
let displayFeedback = "Not checked yet";

async function request(path, values) {
  const options = values === undefined ? {} : {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(values),
  };
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Dashboard request failed");
  return data;
}

function syncButtons() {
  const running = Boolean(farm?.running);
  const canStart = loaded && farm && !running;
  buttons.start.hidden = running;
  buttons.start.disabled = busy || !canStart;
  buttons.stop.hidden = !running;
  buttons.stop.disabled = busy || !running || farm.stopping;
  buttons.pause.disabled = busy || !running || farm.stopping;
  buttons.pause.textContent = farm?.pause_requested ? "Resume" : "Pause";
  get("card-action").textContent = running ? "Stop" : "Start";
  get("card-action").disabled = running ? buttons.stop.disabled : buttons.start.disabled;
  get("card-pause").hidden = !running;
  get("card-pause").textContent = buttons.pause.textContent;
  get("card-pause").disabled = buttons.pause.disabled;
  buttons.save.hidden = !Object.keys(edits).length;
  buttons.save.disabled = busy || !loaded;
  const profile = get("settings-profile");
  if (profile) profile.disabled = busy || !loaded;
  for (const button of document.querySelectorAll(".display-action")) button.disabled = busy || running;
  fields.disabled = busy || !loaded;
}

function valueOf(path) {
  return Object.hasOwn(edits, path) ? edits[path] : baseline[path];
}

function edit(path, value) {
  if (JSON.stringify(value) === JSON.stringify(baseline[path])) {
    delete edits[path];
  } else {
    edits[path] = value;
    if (minimumFields.has(path) && !valueOf(useMinimums)) {
      if (baseline[useMinimums]) delete edits[useMinimums];
      else edits[useMinimums] = true;
      const checkbox = get("field-" + useMinimums);
      if (checkbox) {
        checkbox.checked = false;
        checkbox.nextElementSibling.textContent = "Off";
      }
    }
  }
  settingsMessage("");
  syncButtons();
  if (path === "human.enabled" && pageKey === "like_a_person" && tabKey === "person") renderPageDetails();
}

function choicesFor(control, options) {
  control.replaceChildren(...options.map(([value, label]) => new Option(label, value)));
}

function node(tag, text = "", className = "") {
  const element = document.createElement(tag);
  element.textContent = text;
  if (className) element.className = className;
  return element;
}

function optionChecks(field, value) {
  const group = node("div", "", "chip-list");
  const controls = new Map();
  for (const [key, label] of field.options) {
    const option = node("label", "", "chip");
    const checkbox = node("input");
    checkbox.type = "checkbox";
    checkbox.checked = value.includes(key);
    controls.set(key, checkbox);
    checkbox.addEventListener("change", () => {
      edit(field.path, [...controls].filter(([, input]) => input.checked).map(([choice]) => choice));
    });
    option.append(checkbox, node("span", field.kind === "hours" ? label.slice(0, 2) : label));
    if (field.kind === "hours") checkbox.setAttribute("aria-label", label);
    group.append(option);
  }
  if (field.kind === "sides") group.classList.add("sides");
  if (field.kind !== "hours") return group;
  group.classList.add("hours");
  const container = node("div", "", "hours-control");
  const bar = node("div", "", "controls hour-presets");
  for (const [label, first] of [["All day", 0], ["Nights off (00–07)", 8], ["Evenings (17–23)", 17], ["None", 24]]) {
    const button = node("button", label);
    button.addEventListener("click", () => {
      for (const [hour, input] of controls) input.checked = hour >= first;
      edit(field.path, [...controls.keys()].filter((hour) => hour >= first));
    });
    bar.append(button);
  }
  container.append(group, bar);
  return container;
}

function listButton(text, item, callback, disabled = false) {
  const button = node("button", text, "list-button");
  button.type = "button";
  button.disabled = disabled;
  button.setAttribute("aria-label", text + " " + item);
  button.addEventListener("click", callback);
  return button;
}

function orderedList(field) {
  const group = node("div", "", "ordered-setting");
  const names = new Map(field.options);
  const fixed = field.kind === "order";
  const list = node("ol", "", "setting-order");
  const pick = node("select");
  pick.setAttribute("aria-label", "Add to " + field.label);

  function redraw() {
    const value = valueOf(field.path);
    list.replaceChildren();
    for (const [index, item] of value.entries()) {
      const label = names.get(item) || item;
      const row = node("li");
      const actions = node("span", "", "list-actions");
      function move(offset) {
        const copy = [...value];
        const destination = index + offset;
        [copy[index], copy[destination]] = [copy[destination], copy[index]];
        edit(field.path, copy);
        redraw();
        list.children[destination].querySelector("button:not(:disabled)")?.focus();
      }
      actions.append(listButton("Up", label, () => move(-1), index === 0),
        listButton("Down", label, () => move(1), index === value.length - 1));
      if (!fixed) actions.append(listButton("Remove", label, () => {
        edit(field.path, value.filter((_, position) => position !== index));
        redraw();
        pick.focus();
      }));
      row.append(node("span", label), actions);
      list.append(row);
    }
    if (!fixed) choicesFor(pick, [["", "Add an item"], ...field.options.filter(([key]) => !value.includes(key))]);
  }

  group.append(list);
  if (!fixed) {
    pick.addEventListener("change", () => {
      if (!pick.value) return;
      edit(field.path, [...valueOf(field.path), pick.value]);
      redraw();
    });
    group.append(pick);
  }
  redraw();
  return group;
}

function presets(field, value) {
  const group = node("div", "", "preset-grid");
  for (const level of new Set([...catalog.castle_levels, ...Object.keys(value)])) {
    const row = node("label", "Level " + level);
    const input = node("input");
    input.value = value[level] || "";
    input.addEventListener("input", () => edit(field.path, {...valueOf(field.path), [level]: input.value}));
    row.append(input);
    group.append(row);
  }
  return group;
}

function displayValue(path) {
  if (serialOverride !== null && path === "device.mode") return "manual";
  if (serialOverride !== null && path === "device.serial") return serialOverride;
  return valueOf(path);
}

function lockedField(path) {
  if (serialOverride !== null && ["device.mode", "device.serial"].includes(path)) return true;
  if (path === "schedule.active_hours") return !valueOf("schedule.enabled");
  if (path.startsWith("schedule.break_")) return !valueOf("schedule.breaks");
  if (path.startsWith("search.") && path !== "search.maintain_only") return valueOf("search.maintain_only");
  return false;
}

function controlFor(field) {
  const value = displayValue(field.path);
  const key = "field-" + field.path;
  const disabled = lockedField(field.path);
  if (field.kind === "bool") {
    const control = node("input");
    const toggle = node("label", "", "switch");
    const inverse = inverseSwitches.has(field.path);
    control.type = "checkbox";
    control.id = key;
    control.checked = inverse ? !value : value;
    control.disabled = disabled;
    control.setAttribute("aria-label", field.label);
    const text = node("span", control.checked ? "On" : "Off");
    control.addEventListener("change", () => {
      text.textContent = control.checked ? "On" : "Off";
      edit(field.path, inverse ? !control.checked : control.checked);
      refreshAfterEdit(field.path, key);
    });
    toggle.append(control, text);
    return toggle;
  }
  if (field.options.length) {
    const group = node("fieldset", "", "segments");
    group.id = key;
    group.disabled = disabled;
    group.setAttribute("aria-label", field.label);
    const options = field.options.some(([item]) => item === value) ? field.options : [...field.options, [value, value || "Unset"]];
    for (const [option, label] of options) {
      const chip = node("label", "", "chip");
      const radio = node("input");
      radio.type = "radio";
      radio.name = key;
      radio.value = option;
      radio.checked = option === value;
      radio.addEventListener("change", () => {
        if (!radio.checked) return;
        edit(field.path, option);
        refreshAfterEdit(field.path, key);
      });
      chip.append(radio, node("span", label));
      group.append(chip);
    }
    return group;
  }
  const control = node("input");
  control.id = key;
  control.disabled = disabled;
  control.value = value;
  control.setAttribute("aria-label", field.label);
  if (field.path === "notify.discord_webhook") {
    control.type = "password";
    control.autocomplete = "off";
  } else if (["amount", "int", "instance", "percent", "float"].includes(field.kind)) {
    control.inputMode = ["instance", "int"].includes(field.kind) ? "numeric" : "decimal";
    control.classList.add("numeric");
  }
  if (field.path === "device.serial") control.placeholder = "Automatic for one device";
  if (field.path === "device.bluestacks_instance") control.placeholder = "Main instance";
  control.addEventListener("input", () => edit(field.path, control.value));
  return control;
}

function settingRow(label, help, symbol = "◇") {
  const row = node("div", "", "setting-row card");
  const icon = node("span", symbol, "row-icon");
  icon.setAttribute("aria-hidden", "true");
  const caption = node("div", "", "setting-copy");
  caption.append(node("div", label, "setting-label"));
  if (help) caption.append(node("p", help, "setting-help"));
  row.append(icon, caption);
  return row;
}

function expandedRow(row, body) {
  const details = node("details", "", "expand-row card");
  const summary = node("summary");
  row.classList.remove("card");
  summary.append(row);
  const key = pageKey + "/" + tabKey + "/" + row.querySelector(".setting-label").textContent;
  details.open = openGroups.has(key);
  details.addEventListener("toggle", () => {
    if (details.open) openGroups.add(key);
    else openGroups.delete(key);
  });
  details.append(summary, body);
  return details;
}

function settingField(field) {
  const value = displayValue(field.path);
  const ordered = ["units", "order", "buildings", "research", "equipment"].includes(field.kind);
  const checks = ["sides", "resources", "hours"].includes(field.kind);
  const help = field.help || (field.kind === "percent" ? "Percentage (" + field.low + "–" + field.high + ")" : "");
  const icon = {bool: "◈", amount: "◉", hours: "◷", sides: "⊞", resources: "◉", order: "≡"}[field.kind];
  const row = settingRow(field.label, help, icon);
  if (minimumFields.has(field.path)) {
    const resource = field.path.split("_").at(-1);
    const symbol = row.querySelector(".row-icon");
    symbol.textContent = "";
    symbol.classList.add("loot-symbol", resource);
  }
  if (ordered || field.kind === "presets") {
    return expandedRow(row, ordered ? orderedList(field) : presets(field, value));
  }
  if (checks) {
    const wrapper = node("fieldset", "", "setting-value");
    wrapper.setAttribute("aria-label", field.label);
    wrapper.disabled = lockedField(field.path);
    wrapper.append(optionChecks(field, value));
    row.append(wrapper);
    if (field.kind === "hours") row.classList.add("wide-control", "hours-row");
    return row;
  }
  const editor = node("div", "", "setting-value");
  editor.append(controlFor(field));
  if (field.path === useMinimums) {
    const button = node("button", "See all");
    button.addEventListener("click", showMinimumTable);
    editor.append(button);
  }
  if (field.kind === "percent") editor.append(node("span", "%", "hint"));
  row.append(editor);
  return row;
}

function pairedRow(paths) {
  const [title, help, unit] = catalog.pairs[paths[0]];
  const row = settingRow(title, help, "◷");
  const controls = node("div", "", "setting-value paired");
  const allSwitches = paths.every((path) => fieldsByPath.get(path).kind === "bool");
  paths.forEach((path, index) => {
    const field = fieldsByPath.get(path);
    if (allSwitches) {
      const chip = node("label", "", "chip");
      const input = node("input");
      input.type = "checkbox";
      input.checked = valueOf(path);
      input.addEventListener("change", () => edit(path, input.checked));
      chip.append(input, node("span", field.label));
      controls.append(chip);
      return;
    }
    if (index) controls.append(node("span", "to", "hint"));
    controls.append(controlFor(field));
  });
  if (unit) controls.append(node("span", unit, "hint"));
  row.append(controls);
  return row;
}

function groupRows(group) {
  const rows = [];
  for (const entry of group.fields) {
    if (Array.isArray(entry)) {
      rows.push(pairedRow(entry));
    } else {
      const condition = catalog.visibility[entry];
      if (!condition || condition[1].includes(displayValue(condition[0]))) {
        rows.push(settingField(fieldsByPath.get(entry)));
      }
    }
  }
  return rows;
}

function renderSettings(tab) {
  fields.replaceChildren();
  fields.hidden = !tab?.groups.length;
  for (const group of tab?.groups || []) {
    const rows = groupRows(group);
    if (!rows.length) continue;
    const section = node("section", "", group.folded || !group.title ? "setting-group continuation" : "setting-group");
    if (group.folded) {
      const body = node("div", "", "fold-content");
      body.append(...rows);
      section.append(expandedRow(settingRow(group.title, group.help, "≡"), body));
    } else {
      if (group.title) section.append(node("h2", group.title));
      section.append(...rows);
      if (pageKey === "advanced" && tabKey === "settings" && group.title === "Custom device") {
        section.append(displayActions());
      }
    }
    fields.append(section);
  }
}

function displayActions() {
  const row = settingRow("Android display", "Apply the values above, or restore the device’s native size and density.", "▣");
  const output = node("span", displayFeedback, "subtitle");
  output.setAttribute("role", "status");
  const controls = node("div", "", "setting-value display-controls");
  controls.append(output);
  for (const [action, title] of [["show", "Read display"], ["apply", "Apply display"], ["reset", "Reset display"]]) {
    const button = node("button", title, action === "apply" ? "display-action primary" : "display-action");
    button.disabled = busy || Boolean(farm?.running);
    button.addEventListener("click", async () => {
      busy = true;
      syncButtons();
      output.textContent = "Working…";
      try {
        const names = ["device.mode", "device.serial", "device.adb_path"];
        if (action === "apply") names.push("device.manual_width", "device.manual_height", "device.manual_dpi");
        const changes = Object.fromEntries(Object.entries(edits).filter(([path]) => names.includes(path)));
        const data = await request("/api/display", {action, changes});
        displayFeedback = data.display;
      } catch (error) {
        displayFeedback = error.message;
      } finally {
        busy = false;
        output.textContent = displayFeedback;
        syncButtons();
      }
    });
    controls.append(button);
  }
  row.classList.add("wide-control");
  row.append(controls);
  return row;
}

function refreshAfterEdit(path, key) {
  if (!refreshControls.has(path)) return;
  renderSettings(currentTab());
  const control = get(key);
  (control?.querySelector(":checked") || control)?.focus();
  updateDashboardMode();
}

function currentPage() {
  return catalog.pages.find((page) => page.key === pageKey);
}

function currentTab() {
  return currentPage().tabs.find((tab) => tab.key === tabKey);
}

function navigate(page, tab) {
  const route = page + (tab ? "/" + tab : "");
  if (location.hash === "#" + route) return;
  location.hash = route;
}

function makeNavigation() {
  const primary = get("main-navigation");
  const bottom = get("secondary-navigation");
  for (const page of catalog.pages) {
    const nav = ["advanced", "farms"].includes(page.key) ? bottom : primary;
    const button = node("button", "", "navigation-item");
    button.dataset.page = page.key;
    const icon = node("span", pageIcons[page.key], "nav-icon");
    icon.setAttribute("aria-hidden", "true");
    const label = node("span", page.title, "nav-label");
    if (page.key === "farms") label.id = "profile-navigation";
    button.append(icon, label);
    button.title = page.title;
    button.addEventListener("click", () => {
      navigate(page.key, lastTab.get(page.key));
      if (compactLayout.matches) collapseNavigation(true);
    });
    nav.append(button);
  }
}

function routePage() {
  if (!loaded) return;
  const [requestedPage, requestedTab] = location.hash.slice(1).split("/");
  const page = catalog.pages.find((option) => option.key === requestedPage) || catalog.pages[0];
  const tab = page.tabs.find((option) => option.key === requestedTab) || page.tabs[0];
  pageKey = page.key;
  tabKey = tab?.key;
  if (tab) lastTab.set(pageKey, tabKey);
  for (const button of document.querySelectorAll(".navigation-item")) {
    if (button.dataset.page === pageKey) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  }
  get("page-title").textContent = page.title;
  get("page-subtitle").textContent = page.subtitle;
  document.title = page.title + " · COCFARM";
  const tabs = get("tabs");
  tabs.replaceChildren();
  tabs.hidden = !tab?.label;
  for (const option of page.tabs) {
    if (!option.label) continue;
    const button = node("button", option.label);
    button.setAttribute("aria-pressed", String(option.key === tabKey));
    button.addEventListener("click", () => navigate(pageKey, option.key));
    tabs.append(button);
  }
  get("tab-intro").textContent = tab?.intro || "";
  get("tab-intro").hidden = !tab?.intro;
  const dashboard = pageKey === "dashboard";
  get("dashboard-status").hidden = !dashboard;
  get("dashboard-panels").hidden = !dashboard;
  window.scrollTo(0, 0);
  renderSettings(tab);
  renderPageDetails();
}

function updateDashboardMode() {
  const mode = valueOf("bot.mode");
  const builder = mode === "builder" || (mode === "auto" && valueOf("bot.auto_first") === "builder");
  get("builder-panel").hidden = !builder;
  get("home-panels").hidden = builder;
}

function showSettings(data) {
  const firstLoad = !loaded;
  baseline = data.values;
  serialOverride = data.serial;
  activeProfile = data.active;
  profiles = data.profiles;
  readyDetail = data.plan;
  edits = {};
  loaded = true;
  if (firstLoad) makeNavigation();
  get("profile-navigation").textContent = activeProfile || "Farms";
  if (firstLoad) routePage();
  else {
    renderSettings(currentTab());
    if (pageKey === "farms") renderPageDetails();
  }
  updateDashboardMode();
  syncButtons();
}

function duration(seconds) {
  if (seconds === null) return "—";
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor(seconds / 60) % 60;
  const clock = [minutes, seconds % 60].map((part) => String(part).padStart(2, "0")).join(":");
  return hours ? hours + ":" + clock : clock;
}

function lootText(loot) {
  if (!loot) return "—";
  return Object.keys(resourceNames).map((key) => resourceNames[key] + " " + format.format(loot[key])).join(" · ");
}

function showState(data) {
  farm = data;
  const label = data.failed ? "Error" : data.stopping ? "Stopping" : data.pause_requested ? "Paused"
    : data.running ? "Running" : data.seconds === null ? "Ready" : data.message;
  for (const id of ["state-pill", "title-state"]) {
    get(id).textContent = label;
    get(id).dataset.state = data.failed ? "error" : data.pause_requested || data.stopping ? "paused" : data.running ? "running" : "idle";
  }
  const headline = data.seconds === null ? "Ready to farm" : data.message;
  if (status.textContent !== headline) status.textContent = headline;
  get("title-message").textContent = headline;
  get("run-detail").textContent = data.seconds === null ? readyDetail : "";
  get("scout-verdict").textContent = data.scout ? (data.scout.accepted ? "Attacking" : "Skipping") : "Waiting for a base";
  get("scout-verdict").dataset.accepted = data.scout ? String(data.scout.accepted) : "";
  for (const key of Object.keys(resourceNames)) {
    get("scout-" + key).textContent = data.scout ? format.format(data.scout.loot[key]) : "—";
    get("gained-" + key).textContent = format.format(data.gained[key]);
  }
  get("village-resources").textContent = data.resources ? lootText(data.resources) : "";
  get("attacks").textContent = format.format(data.attacks);
  get("bases").textContent = format.format(data.bases);
  get("runtime").textContent = duration(data.seconds);
  get("last-attack").textContent = data.last_attack ? "Offered " + lootText(data.last_attack.offered) : "None yet";
  for (const key of ["gold", "elixir"]) get("builder-" + key).textContent = format.format(data.builder.gained[key]);
  get("builder-battles").textContent = format.format(data.builder.battles);
  get("builder-runtime").textContent = duration(data.seconds);
  get("builder-last").textContent = data.builder.last
    ? data.builder.last.stages + " stages · " + duration(data.builder.last.seconds) : "None yet";
  get("builder-walls").textContent = format.format(data.builder.walls);
  get("builder-cart").textContent = data.builder.cart_in === null ? "—" : "In " + data.builder.cart_in + " battles";
  get("builder-stage").textContent = data.running ? data.message : "Waiting";
  const fresh = data.logs.filter(([index]) => index > sequence);
  if (fresh.length) {
    const follow = !sequence || logs.scrollHeight - logs.scrollTop - logs.clientHeight < 32;
    sequence = fresh.at(-1)[0];
    logLines = logLines.concat(fresh.map(([, line]) => line)).slice(-300);
    logs.textContent = logLines.join("\n");
    if (follow) logs.scrollTop = logs.scrollHeight;
  }
  syncButtons();
}

function panel(title) {
  const box = node("section", "", "panel");
  const head = node("div", "", "panel-header");
  head.append(node("h2", title));
  box.append(head);
  return box;
}

function dataTable(headers, rows) {
  const table = node("table");
  const heading = table.createTHead().insertRow();
  for (const header of headers) {
    const cell = node("th", header);
    cell.scope = "col";
    heading.append(cell);
  }
  const body = table.createTBody();
  for (const values of rows) {
    const row = body.insertRow();
    row.append(...values.map((value) => node("td", value)));
  }
  return table;
}

function showMinimumTable() {
  const dialog = node("dialog", "", "minimum-dialog");
  const heading = node("h2", "Suggested amounts");
  heading.id = "minimum-dialog-title";
  dialog.setAttribute("aria-labelledby", heading.id);
  const rows = catalog.minimums.map((loot, index) => [index + 1, ...Object.keys(resourceNames).map((key) => format.format(loot[key]))]);
  const scroll = node("div", "", "minimum-table");
  scroll.append(dataTable(["Town Hall", ...Object.values(resourceNames)], rows));
  const close = node("button", "Close", "primary");
  close.addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", () => dialog.remove());
  dialog.append(heading, scroll, close);
  document.body.append(dialog);
  dialog.showModal();
}

function historyChart(days, selected) {
  const chart = node("canvas", "", "history-chart");
  chart.width = 920;
  chart.height = 250;
  chart.setAttribute("aria-label", "Loot gained per day");
  const context = chart.getContext("2d");
  const colors = {gold: "#ffc83e", elixir: "#d797ff", dark: "#aaaafa"};
  const keys = selected ? [selected] : Object.keys(resourceNames);
  const maximum = Math.max(1, ...days.flatMap(([, loot]) => keys.map((key) => loot[key])));
  const left = 70;
  const bottom = 215;
  context.font = "13px sans-serif";
  context.textAlign = "right";
  for (let tick = 0; tick <= 4; tick += 1) {
    const y = bottom - tick * 46;
    context.strokeStyle = "#4a4a4a";
    context.beginPath();
    context.moveTo(left, y);
    context.lineTo(905, y);
    context.stroke();
    context.fillStyle = "#b6bdc8";
    context.fillText(new Intl.NumberFormat(undefined, {notation: "compact"}).format(maximum * tick / 4), left - 8, y + 4);
  }
  const spacing = (905 - left) / days.length;
  context.textAlign = "center";
  for (const [index, [day, loot]] of days.entries()) {
    const x = left + index * spacing;
    for (const [position, key] of keys.entries()) {
      const height = Math.max(0, loot[key]) / maximum * 184;
      context.fillStyle = colors[key];
      context.fillRect(x + 11 + position * 13, bottom - height, 11, height);
    }
    context.fillStyle = "#b6bdc8";
    context.fillText(day.slice(5), x + spacing / 2, bottom + 20);
  }
  return chart;
}

async function showHistory(target) {
  const data = await request("/api/history");
  const toolbar = node("div", "", "controls page-tools");
  const refresh = node("button", "Refresh");
  refresh.addEventListener("click", renderPageDetails);
  toolbar.append(refresh);
  const metrics = node("div", "", "history-metrics");
  for (const summary of data.summaries) {
    const card = node("div", "", "panel summary-stat");
    card.append(node("span", summary.title, "subtitle"), node("strong", summary.count === null
      ? (summary.loot ? format.format(summary.loot.gold + summary.loot.elixir) : "—")
      : format.format(summary.count) + " attacks"), node("p", lootText(summary.loot), "hint"));
    metrics.append(card);
  }
  const chart = panel("Loot gained per day (last 14 days)");
  const filter = node("select");
  filter.setAttribute("aria-label", "Show");
  choicesFor(filter, [["", "All loot"], ...Object.entries(resourceNames).map(([key, name]) => [key, name + " only"])]);
  const select = node("label", "Show ", "chart-filter");
  select.append(filter);
  const chartFrame = node("div", "", "chart-frame");
  const draw = () => chartFrame.replaceChildren(historyChart(data.days, filter.value));
  draw();
  filter.addEventListener("change", draw);
  chart.append(select, chartFrame);
  const tableFrame = node("div", "", "panel history-table");
  if (data.rows.length) {
    const rows = data.rows.map((record) => [new Date(record.time).toLocaleString(),
      ...[record.target, record.gained].flatMap((loot) => Object.keys(resourceNames).map((key) => loot ? format.format(loot[key]) : "—"))]);
    tableFrame.append(dataTable(
      ["Time", "Offered gold", "Offered elixir", "Offered dark", "Gained gold", "Gained elixir", "Gained dark"], rows));
  } else {
    tableFrame.append(node("p", "No attacks recorded yet.", "empty"));
  }
  target.append(toolbar, metrics, chart, tableFrame);
}

async function showFarms(target) {
  const data = await request("/api/farms");
  const heading = node("h2", "Your farms");
  target.append(heading);
  for (const farmInfo of data.farms) {
    const row = settingRow("Farm " + farmInfo.number, farmInfo.device, "▣");
    if (farmInfo.current) row.append(node("span", "Current farm", "badge"));
    target.append(row);
  }
  target.append(node("h2", "Accounts and profiles"));
  const row = settingRow("Settings profile", "Pick the account profile this farm uses.", "◉");
  const select = node("select");
  select.id = "settings-profile";
  select.setAttribute("aria-label", "Settings profile");
  choicesFor(select, [["", "Default"], ...profiles.map((name) => [name, name])]);
  select.value = activeProfile;
  select.disabled = busy || !loaded;
  select.addEventListener("change", () => selectProfile(select));
  row.append(select);
  target.append(row);
}

async function showPictures(target) {
  const data = await request("/api/pictures");
  const query = node("input");
  query.type = "search";
  query.placeholder = "Find a picture";
  query.setAttribute("aria-label", "Find a picture");
  const entries = node("div", "", "setting-group");
  const paint = () => {
    const text = query.value.toLowerCase().trim();
    entries.replaceChildren(...data.pictures.filter((picture) => [picture.title, picture.feature].join(" ").toLowerCase().includes(text)).map((picture) => {
      const row = settingRow(picture.title, picture.where, "▧");
      row.append(node("span", picture.present ? "Available" : "Missing", "badge"));
      return row;
    }));
    if (!entries.children.length) entries.append(node("p", "No pictures match your search.", "subtitle"));
  };
  query.addEventListener("input", paint);
  paint();
  target.append(query, entries);
}

async function showTimings(target) {
  const habits = valueOf("human.enabled") ? catalog.fields
    .filter(({path}) => path.startsWith("human.") && path !== "human.enabled" && valueOf(path))
    .map(({path}) => path.slice(6)) : [];
  const data = await request("/api/timings", {habits});
  for (const [key, title] of [["home", "Home village: one round"], ["builder", "Builder base: one round"]]) {
    const box = node("section", "", "panel timing-panel");
    box.append(dataTable([title, "Without habits", "Added", "With these"], data[key]),
      node("p", "Typical times from test runs. Upgrades and village care vary with what there is to do.", "hint"));
    target.append(box);
  }
}

function showReport(target) {
  const box = panel("Step-by-step log");
  const report = node("pre", logLines.length ? logLines.slice(-60).join("\n") : "Nothing to report yet.");
  report.className = "report-log";
  box.append(report);
  target.append(box);
}

function showConnection(target) {
  const section = node("section", "", "setting-group");
  section.append(node("h2", "Check the connection"));
  const check = settingRow("Check the connection", "Checks that COCFARM can see the Android screen.", "▣");
  const result = node("span", "Not checked yet", "subtitle");
  const control = node("div", "", "setting-value");
  const button = node("button", "Check now", "primary");
  const installed = settingRow("Clash of Clans installed", "", "◇");
  const signedIn = settingRow("Signed in to your account", "", "◉");
  const installResult = node("span", "Not checked yet", "subtitle");
  const signInResult = node("span", "Not checked yet", "subtitle");
  installed.append(installResult);
  signedIn.append(signInResult);
  button.addEventListener("click", async () => {
    button.disabled = true;
    result.textContent = "Checking…";
    try {
      if (Object.keys(edits).length) await saveSettings();
      const data = await request("/api/check-device", {});
      result.textContent = "Connected · " + data.screen;
      installResult.textContent = data.installed === null ? "Unavailable" : data.installed ? "Installed" : "Missing";
      signInResult.textContent = data.village ? "Village visible" : "Open the game in your village";
    } catch (error) {
      result.textContent = error.message;
    } finally {
      button.disabled = false;
    }
  });
  control.append(result, button);
  check.append(control);
  section.append(check, installed, signedIn);
  target.append(section);
}

async function renderPageDetails() {
  const view = {history: showHistory, farms: showFarms}[pageKey] ||
    (pageKey === "advanced" ? {settings: showConnection, report: showReport, pictures: showPictures}[tabKey]
      : pageKey === "like_a_person" && tabKey === "person" ? showTimings : undefined);
  const details = get("page-content");
  details.replaceChildren();
  details.hidden = !view;
  if (!view) return;
  const content = node("div", "", "page-details");
  details.append(content);
  try {
    await view(content);
  } catch (error) {
    content.append(node("p", error.message, "notice error"));
  }
}

function settingsMessage(text, error = false) {
  const result = get("settings-result");
  result.textContent = text;
  result.hidden = !text;
  result.classList.toggle("error", error);
}

async function saveSettings() {
  showSettings(await request("/api/settings", {changes: edits, profile: activeProfile}));
  settingsMessage(farm?.running ? "Saved for the next run." : "Saved.");
}

async function act(action) {
  if (busy) return;
  const errorMessage = get("action-error");
  errorMessage.hidden = true;
  busy = true;
  controlVersion += 1;
  syncButtons();
  try {
    if (action === "start" && Object.keys(edits).length) await saveSettings();
    showState(await request(`/api/${action}`, {since: sequence}));
  } catch (error) {
    errorMessage.textContent = error.message;
    errorMessage.hidden = false;
  } finally {
    busy = false;
    syncButtons();
  }
}

async function selectProfile(select) {
  const name = select.value;
  busy = true;
  syncButtons();
  try {
    if (Object.keys(edits).length) await saveSettings();
    showSettings(await request("/api/profile", {name}));
    settingsMessage("");
  } catch (error) {
    select.value = activeProfile;
    settingsMessage(error.message, true);
  } finally {
    busy = false;
    syncButtons();
  }
}

buttons.save.addEventListener("click", async () => {
  if (busy) return;
  busy = true;
  syncButtons();
  try {
    await saveSettings();
  } catch (error) {
    settingsMessage(error.message, true);
  } finally {
    busy = false;
    syncButtons();
  }
});

function collapseNavigation(collapsed) {
  document.body.classList.toggle("collapsed", collapsed);
  get("menu").setAttribute("aria-expanded", String(!collapsed));
}

get("menu").addEventListener("click", () => collapseNavigation(!document.body.classList.contains("collapsed")));

get("card-action").addEventListener("click", () => act(farm?.running ? "stop" : "start"));
get("card-pause").addEventListener("click", () => act(farm?.pause_requested ? "resume" : "pause"));
get("show-log").addEventListener("click", (event) => {
  logs.hidden = !logs.hidden;
  get("clear-log").hidden = logs.hidden;
  event.currentTarget.textContent = logs.hidden ? "Show the step-by-step log" : "Hide the log";
  event.currentTarget.setAttribute("aria-expanded", String(!logs.hidden));
});
get("clear-log").addEventListener("click", () => {
  logLines = [];
  logs.textContent = "Nothing yet. Press Start and each step will appear here.";
});
window.addEventListener("hashchange", routePage);

collapseNavigation(compactLayout.matches);
compactLayout.addEventListener("change", (event) => collapseNavigation(event.matches));

buttons.start.addEventListener("click", () => act("start"));
buttons.pause.addEventListener("click", () => act(farm?.pause_requested ? "resume" : "pause"));
buttons.stop.addEventListener("click", () => act("stop"));

async function monitor() {
  const version = controlVersion;
  try {
    if (!loaded) {
      const [schema, data] = await Promise.all([request("/api/settings/schema"), request("/api/settings")]);
      catalog = schema;
      fieldsByPath = new Map(catalog.fields.map((field) => [field.path, field]));
      showSettings(data);
    }
    if (!busy) {
      const data = await request(`/api/status?since=${sequence}`);
      if (version === controlVersion) showState(data);
    }
  } catch (error) {
    if (version === controlVersion) {
      farm = null;
      status.textContent = error.message;
      status.dataset.state = "error";
      syncButtons();
    }
  } finally {
    setTimeout(monitor, 1000);
  }
}

monitor();
