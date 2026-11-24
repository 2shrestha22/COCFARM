import { useId, useState } from "react";
import { ArrowDownOutlined, ArrowUpOutlined, MinusOutlined } from "@ant-design/icons";
import { AutoComplete, Button, Card, Collapse, Flex, Grid, Input, Modal, Segmented, Select, Slider, Space, Switch, Table, Tag, Tree, Typography } from "antd";
import { format, resourceNames, suggestedMinimums, switchStoragePrompt } from "./dashboard";

const { Text } = Typography;
const inverseSwitches = new Set([suggestedMinimums, "search.maintain_only"]);
const orderedKinds = new Set(["units", "order", "buildings", "research", "equipment"]);
const toggleLists = new Set(["sides", "resources", "hours"]);
const numericKinds = new Set(["amount", "int", "instance", "percent", "float"]);

export function DataTable({ headers, rows }) {
  const columns = headers.map((title, index) => ({ title, key: index, dataIndex: ["values", index] }));
  return <Table size="small" pagination={false} columns={columns} scroll={{ x: "max-content" }}
    dataSource={rows.map((values, key) => ({ key, values }))} />;
}

export function SettingRow({ label, help, error, children, wide = false }) {
  return <div className={"flex flex-col gap-2 py-2.5 " +
    (wide ? "" : "@lg/field-group:flex-row @lg/field-group:items-center @lg/field-group:justify-between @lg/field-group:gap-5")}>
    <div className="grid min-w-0 gap-1">
      <Text strong>{label}</Text>
      {help && <div><Text type="secondary">{help}</Text></div>}
      {error && <div role="alert"><Text type="danger">{error}</Text></div>}
    </div>
    {children && <div className="min-w-0 @lg/field-group:shrink-0">{children}</div>}
  </div>;
}

export function SettingsSection({ title, description, children, embedded = false }) {
  const content = <>
    {description && <div className="mb-1"><Text type="secondary">{description}</Text></div>}
    {children}
  </>;
  if (embedded) return <section className="min-w-0">
    {title && <h3 className="text-base font-semibold">{title}</h3>}
    {content}
  </section>;
  return <Card size="small" className="@container/field-group min-w-0" title={title && <h2>{title}</h2>}>
    {content}
  </Card>;
}

function isLocked(path, dashboard) {
  if (dashboard.busy) return true;
  if (dashboard.settings.serial !== null && ["device.mode", "device.serial"].includes(path)) return true;
  return (dashboard.catalog.dependencies?.[path] || []).some(([controller, allowed]) => {
    const value = dashboard.value(controller);
    return !allowed.some((expected) => Array.isArray(expected)
      ? JSON.stringify(value) === JSON.stringify(expected) : value === expected);
  });
}

function MinimumsDialog({ minimums, disabled }) {
  const [open, setOpen] = useState(false);
  const keys = Object.keys(resourceNames);
  return <>
    <Button disabled={disabled} onClick={() => setOpen(true)}>See all</Button>
    <Modal title="Suggested loot amounts" open={open} onCancel={() => setOpen(false)} footer={null}>
      <div className="max-h-[55vh] overflow-y-auto">
        <DataTable headers={["Town Hall", ...Object.values(resourceNames)]}
          rows={minimums.map((entry, index) => [index + 1, ...keys.map((key) => format.format(entry[key]))])} />
      </div>
    </Modal>
  </>;
}

function SingleChoice({ label, options, value, disabled, change, id, fill }) {
  const compact = Grid.useBreakpoint().xs;
  const styles = fill ? {
    root: { overflowX: "auto" },
    item: { flex: "1 0 auto" },
    label: { whiteSpace: "nowrap", paddingInline: compact ? 4 : 10 },
  } : compact ? {
    label: { display: "flex", alignItems: "center", justifyContent: "center", height: "100%",
      lineHeight: 1.25, whiteSpace: "normal", overflowWrap: "anywhere", padding: "6px" },
  } : undefined;
  return <Segmented id={id} aria-label={label} size={compact ? "large" : "middle"} block={compact || fill}
    orientation={compact && options.length > 3 ? "vertical" : "horizontal"} disabled={disabled} value={value}
    styles={styles}
    options={options.map(([key, text]) => ({ value: key, label: text }))} onChange={change} />;
}

function ToggleOptions({ field, value, change, disabled }) {
  const hours = field.kind === "hours";
  const positions = field.kind === "sides";
  function toggle(key, checked) {
    change(checked ? field.options.filter(([item]) => item === key || value.includes(item)).map(([item]) => item)
      : value.filter((item) => item !== key));
  }
  return <div role="group" aria-label={field.label} className="grid gap-2">
    <div className={hours ? "grid grid-cols-6 gap-2 sm:grid-cols-12" : positions ? "grid grid-cols-2 gap-2" : "flex flex-wrap gap-2"}>
      {field.options.map(([key, label]) => <Button key={key} size="small" aria-label={label} aria-pressed={value.includes(key)}
        type={value.includes(key) ? "primary" : "default"} disabled={disabled}
        onClick={() => toggle(key, !value.includes(key))}>{hours ? label.slice(0, 2) : label}</Button>)}
    </div>
    {hours && <Space wrap size={6}>
      {[["All day", 0], ["Nights off (00–07)", 8], ["Evenings (17–23)", 17], ["None", 24]].map(([label, first]) =>
        <Button key={first} size="small" disabled={disabled}
          onClick={() => change(field.options.map(([hour]) => hour).filter((hour) => hour >= first))}>{label}</Button>
      )}
    </Space>}
  </div>;
}

function SliderEditor({ field, dashboard, value, disabled, change }) {
  const { path, control } = field;
  const share = dashboard.catalog.shares?.[path];
  const count = dashboard.settings.builders?.[path];
  let number = Number(value);
  let label = number;
  if (share) {
    const [storage, resource] = share;
    const match = /^([0-9]+(?:\.[0-9]+)?)([kmb])?$/i.exec(String(dashboard.value(storage)).replaceAll(",", "").trim());
    const size = match && Number(match[1]) * ({ k: 1e3, m: 1e6, b: 1e9 }[match[2]?.toLowerCase()] || 1);
    label = number + "% · " + (size ? format.format(Math.round(number / 100 * size)) + " " + resource : "size not known yet");
  } else if (control === "builders") {
    number = number < 0 ? 0 : number === 0 ? Math.max(count - 1, 1) : Math.min(number, count);
    label = number + " of " + count;
  } else if (control === "stars") {
    label = number + (number === 1 ? " star" : " stars");
  }
  return <Flex align="center" wrap gap={8} className="@md/field-group:w-72">
    {control === "speed" && <Text type="secondary">Slow</Text>}
    <Slider className="min-w-14 flex-1" ariaLabelForHandle={field.label} value={number}
      min={count ? 0 : field.low} max={count || field.high} disabled={disabled}
      onChange={(next) => change(count ? (next === Math.max(count - 1, 1) ? 0 : next || -1) : next)} />
    {control === "speed" && <Text type="secondary">Fast</Text>}
    <Text className="tabular-nums">{label}</Text>
  </Flex>;
}

function FieldEditor({ field, dashboard, id, placeholder: hint }) {
  const value = dashboard.value(field.path);
  const disabled = isLocked(field.path, dashboard);
  const change = (next) => {
    dashboard.edit(field.path, next);
    if (field.kind === "amount" && field.path.startsWith("storage.")) {
      dashboard.edit(field.path.startsWith("storage.builder_") ? "storage.builder_read" : "storage.read", false);
    }
  };
  if (field.kind === "bool") {
    const inverse = inverseSwitches.has(field.path);
    return <Space size={8}>
      <Switch id={id} aria-label={field.label} checked={Boolean(inverse ? !value : value)}
        disabled={disabled} onChange={(next) => change(inverse ? !next : next)} />
      {field.path === suggestedMinimums && <MinimumsDialog minimums={dashboard.catalog.minimums} disabled={disabled} />}
    </Space>;
  }

  if (["speed", "stars", "builders"].includes(field.control) || dashboard.catalog.shares?.[field.path]) {
    return <SliderEditor field={field} dashboard={dashboard} value={value} disabled={disabled} change={change} />;
  }

  if (toggleLists.has(field.kind)) return <ToggleOptions field={field} value={value} change={change} disabled={disabled} />;
  if (field.options.length) {
    const options = field.options.some(([key]) => key === value) ? field.options : [...field.options, [value, value || "Unset"]];
    if (field.control === "segments") {
      return <SingleChoice id={id} label={field.label} options={options} value={value} disabled={disabled} change={change}
        fill={field.path === "bot.mode"} />;
    }
    return <Select id={id} aria-label={field.label} disabled={disabled} value={value} className="w-full @md/field-group:w-56"
      onChange={change} options={options.map(([key, label]) => ({ value: key, label }))} />;
  }

  const secret = field.path === "notify.discord_webhook";
  const numeric = numericKinds.has(field.kind);
  if (field.control === "editable_choice") {
    return <AutoComplete id={id} aria-label={field.label} disabled={disabled} value={value}
      className="w-full @md/field-group:w-60" onChange={change}
      placeholder={field.path === "device.ldplayer" ? "Newest installed" : "Main instance"} />;
  }
  const placeholder = hint || (field.path.startsWith("storage.") ? "not known yet"
    : field.kind === "amount" ? "e.g. 1.5m" : field.low != null && field.high != null
    ? field.low + "–" + field.high
    : undefined);
  const suffix = field.unit || (field.kind === "percent" ? "%" : undefined);
  const wideNumber = field.kind === "amount" || field.high >= 1_000_000;
  return <Input id={id} aria-label={field.label} disabled={disabled} type={secret ? "password" : "text"}
    autoComplete={secret ? "off" : undefined} placeholder={placeholder} value={value ?? ""}
    suffix={suffix} className={numeric ? undefined : "w-full @md/field-group:w-60"}
    style={numeric ? { width: wideNumber ? "10rem" : "6.5rem", maxWidth: "100%" } : undefined}
    inputMode={numeric ? (["int", "instance"].includes(field.kind) ? "numeric" : "decimal") : undefined}
    onChange={(event) => change(event.target.value)} />;
}

function ReorderList({ values, names, describe, change, disabled }) {
  function move(index, offset) {
    const next = [...values];
    [next[index], next[index + offset]] = [next[index + offset], next[index]];
    change(next);
  }

  function drop({ dragNode, node, dropPosition, dropToGap }) {
    const from = values.indexOf(dragNode.key);
    if (disabled || !dropToGap || from < 0) return;
    const next = values.filter((key) => key !== dragNode.key);
    const target = next.indexOf(node.key);
    if (target < 0) return;
    const after = dropPosition > Number(node.pos.split("-").at(-1));
    const to = target + Number(after);
    if (to === from) return;
    next.splice(to, 0, dragNode.key);
    change(next);
  }

  if (!values.length) return null;
  return <Tree blockNode selectable={false} draggable={!disabled && values.length > 1}
    allowDrop={({ dropPosition }) => dropPosition !== 0} onDrop={drop}
    treeData={values.map((key, index) => ({
      key,
      title: <Flex align="center" justify="space-between" wrap="wrap" gap={8}>
        {describe(key, index)}
        <Space.Compact size="small">
          <Button icon={<ArrowUpOutlined />} aria-label={"Move " + (names.get(key) || key) + " up"}
            disabled={disabled || index === 0} onClick={() => move(index, -1)} />
          <Button icon={<ArrowDownOutlined />} aria-label={"Move " + (names.get(key) || key) + " down"}
            disabled={disabled || index === values.length - 1} onClick={() => move(index, 1)} />
        </Space.Compact>
      </Flex>,
    }))} />;
}

function PriorityEditor({ field, dashboard }) {
  const order = dashboard.value(field.path);
  const priorities = dashboard.catalog.priorities?.[field.path] || {};
  const names = new Map(Object.entries(priorities).map(([key, [, title]]) => [key, title]));
  const disabled = isLocked(field.path, dashboard);
  return <section className="grid gap-2 py-3">
    <h3 className="font-semibold">{field.label}</h3>
    <Text type="secondary">{field.help}</Text>
    <ReorderList values={order} names={names} disabled={disabled} change={(next) => dashboard.edit(field.path, next)}
      describe={(key, index) => {
        const [path, label, resources] = priorities[key] || [];
        return <Flex gap={8} align="center" wrap="wrap">
          <Text strong>{index + 1}</Text>
          <Text strong>{label || key}</Text>
          {resources?.split(", ").map((resource) => <Tag key={resource}>{resource}</Tag>)}
          {path && <Switch aria-label={label} checked={dashboard.value(path)}
            disabled={disabled || isLocked(path, dashboard)} onChange={(next) => dashboard.edit(path, next)} />}
        </Flex>;
      }} />
  </section>;
}

function OrderedEditor({ field, dashboard }) {
  const selected = dashboard.value(field.path);
  const disabled = isLocked(field.path, dashboard);
  const pickGroups = dashboard.catalog.pick_groups?.[field.path];
  const state = dashboard.settings.pick_state?.[field.path] || {};
  const done = new Set(state.done || []);
  const unlocked = state.available && new Set(state.available);
  const groups = Object.entries(pickGroups || {}).map(([title, keys]) =>
    [title, unlocked ? keys.filter((key) => unlocked.has(key)) : keys]).filter(([, keys]) => keys.length);
  const [current, setCurrent] = useState(groups[0]?.[0]);
  const group = groups.find(([label]) => label === current) || groups[0];
  const labels = new Map(field.options);
  const available = pickGroups ? (group?.[1] || []) : field.options.map(([key]) => key).filter((key) => !selected.includes(key));
  const selectable = available.filter((key) => !done.has(key));
  const change = (next) => dashboard.edit(field.path, next);
  function toggle(key) {
    change(selected.includes(key) ? selected.filter((entry) => entry !== key) : [...selected, key]);
  }
  const order = <ReorderList values={selected} names={labels} change={change} disabled={disabled}
    describe={(key) => <Space size={4} wrap>
      <Text>{labels.get(key) || key}</Text>
      <Button size="small" type="text" icon={<MinusOutlined />} aria-label={"Remove " + (labels.get(key) || key)}
        disabled={disabled} onClick={() => toggle(key)} />
    </Space>} />;
  if (!pickGroups) {
    return <div className="max-h-60 overflow-y-auto">
      {order}
      <Flex vertical align="start">
        {available.map((key) => <Button key={key} type="text" size="small" disabled={disabled}
          aria-pressed={false} onClick={() => toggle(key)}>{labels.get(key) || key}</Button>)}
      </Flex>
    </div>;
  }

  return <div className="grid gap-3">
    {group && <Flex align="center" justify="space-between" wrap="wrap" gap={8}>
      <div className="max-w-full overflow-x-auto">
        <Segmented aria-label={field.label + " groups"} size="small" value={group[0]} onChange={setCurrent}
          options={groups.map(([name, choices]) => {
            const count = choices.filter((key) => selected.includes(key)).length;
            return { value: name, label: count ? name + " (" + count + ")" : name };
          })} />
      </div>
      <Space.Compact>
        <Button disabled={disabled || selectable.every((key) => selected.includes(key))}
          onClick={() => change([...selected, ...selectable.filter((key) => !selected.includes(key))])}>All</Button>
        <Button disabled={disabled || !available.some((key) => selected.includes(key))}
          onClick={() => change(selected.filter((key) => !available.includes(key)))}>None</Button>
      </Space.Compact>
    </Flex>}
    <div className="grid grid-cols-1 items-start gap-3 md:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
      <Flex wrap="wrap" gap={6}>
        {available.map((key) => <Button key={key} size="small" disabled={disabled || done.has(key)} aria-pressed={selected.includes(key)}
          type={selected.includes(key) ? "primary" : "default"} onClick={() => toggle(key)}>
          {labels.get(key) || key}{state.levels?.[key] != null && <Tag color={done.has(key) ? "success" : undefined}>
            {state.levels[key]}{state.max?.[key] && "/" + state.max[key]}
          </Tag>}
        </Button>)}
      </Flex>
      <Card size="small" className="min-w-0" title="Order">
        <Text type="secondary">Drag to reorder.</Text>
        {order}
      </Card>
    </div>
  </div>;
}

function PresetEditor({ field, dashboard }) {
  const value = dashboard.value(field.path);
  const castles = dashboard.catalog.castles || [];
  const levels = new Map(castles.map((castle) => [castle.level, castle]));
  Object.keys(value).forEach((level) => { if (!levels.has(level)) levels.set(level, null); });
  return <div className="grid gap-2">
    {[...levels].map(([level, castle]) => <label key={level} className="grid gap-1 sm:grid-cols-[minmax(0,auto)_minmax(0,1fr)] sm:items-center sm:gap-3">
      <span>
        <Text strong>Level {level}</Text>
        {castle && <div><Text type="secondary">{castle.troops} troops · {castle.spells} spells · {castle.siege} siege · lab cap {castle.lab_cap}</Text></div>}
      </span>
      <Input value={value[level] || ""} disabled={dashboard.busy}
        onChange={(event) => dashboard.edit(field.path, { ...value, [level]: event.target.value })} />
    </label>)}
  </div>;
}

function Disclosure({ label, help, children, disabled = false }) {
  return <Collapse size="small" bordered={false} items={[{
    key: "settings",
    label: <><Text strong>{label}</Text>{help && <div><Text type="secondary">{help}</Text></div>}</>,
    children,
    collapsible: disabled ? "disabled" : undefined,
  }]} />;
}

function SettingField({ field, dashboard }) {
  const id = useId();
  const error = field.path === "bot.stop_when_full" && dashboard.switchStorageRequired ? switchStoragePrompt : undefined;
  if (field.kind === "order") return <PriorityEditor field={field} dashboard={dashboard} />;
  if (orderedKinds.has(field.kind) || field.kind === "presets") {
    return <Disclosure label={field.label} help={field.help} disabled={isLocked(field.path, dashboard)}>
      {field.kind === "presets" ? <PresetEditor field={field} dashboard={dashboard} />
        : <OrderedEditor field={field} dashboard={dashboard} />}
    </Disclosure>;
  }
  return <SettingRow label={<label htmlFor={id}>{field.label}</label>} help={field.help} error={error} wide={field.kind === "hours"}>
    <FieldEditor id={id} field={field} dashboard={dashboard} />
  </SettingRow>;
}

function PairedRow({ paths, fields, dashboard }) {
  const [label, help, unit] = dashboard.catalog.pairs[paths[0]];
  if (paths[0] === "upgrade.start_gold") {
    return <SettingRow label={label} help={help} wide>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        {paths.map((path, index) => <label key={path} className="grid min-w-0 gap-1 [&_input]:w-full">
          <Text>{Object.values(resourceNames)[index]}</Text>
          <FieldEditor field={fields[path]} dashboard={dashboard} placeholder="when full" />
        </label>)}
      </div>
    </SettingRow>;
  }

  const allSwitches = paths.every((path) => fields[path].kind === "bool");
  return <SettingRow label={label} help={help}>
    <Flex wrap="wrap" align="center" gap={8}>
      {paths.map((path, index) => allSwitches
        ? <Button key={path} type={dashboard.value(path) ? "primary" : "default"} aria-pressed={dashboard.value(path)}
            disabled={isLocked(path, dashboard)} onClick={() => dashboard.edit(path, !dashboard.value(path))}>{fields[path].label}</Button>
        : <Space key={path} size={8}>
            {index > 0 && <Text type="secondary">to</Text>}
            <div className="w-20 [&_.ant-input-affix-wrapper]:w-full [&_input]:w-full">
              <FieldEditor field={fields[path]} dashboard={dashboard} />
            </div>
          </Space>)}
      {unit && <Text type="secondary">{unit}</Text>}
    </Flex>
  </SettingRow>;
}

function DisplayActions({ dashboard }) {
  const [status, setStatus] = useState("");
  const disabled = dashboard.busy || dashboard.farm?.running;
  function run(action) {
    setStatus("Working…");
    dashboard.display(action, setStatus);
  }
  return <SettingRow label="Android display">
    <Space wrap size={6}>
      {[["show", "Read display"], ["apply", "Apply display"], ["reset", "Reset display"]].map(([action, label]) =>
        <Button key={action} type={action === "apply" ? "primary" : "default"}
          disabled={disabled} onClick={() => run(action)}>{label}</Button>
      )}
    </Space>
    <Text type="secondary" role="status">{status}</Text>
  </SettingRow>;
}

function ReadStorages({ paths, dashboard }) {
  const [read, ...amounts] = paths;
  function clear() {
    amounts.forEach((path) => dashboard.edit(path, ""));
    dashboard.edit(read, true);
  }
  return <div className="flex flex-wrap items-center gap-2 py-2.5">
    <Button disabled={dashboard.busy} onClick={clear}>Clear saved capacities</Button>
    <Text type="secondary">Re-enables automatic readings.</Text>
  </div>;
}

function Connection({ dashboard }) {
  const [status, setStatus] = useState("");
  const [checked, setChecked] = useState(null);
  function check() {
    setStatus("Checking…");
    setChecked(null);
    dashboard.checkDevice((data) => {
      setChecked(data);
      setStatus("Connected · " + data.screen);
    }, setStatus);
  }
  return <>
    <SettingRow label="Emulator connection" help="The check may start the emulator.">
      <Space wrap>
        <Text type="secondary" role="status">{status}</Text>
        <Button onClick={check} disabled={dashboard.busy || dashboard.farm?.running}>Check connection</Button>
      </Space>
    </SettingRow>
    {checked && <>
      <SettingRow label="Clash of Clans">
        <Text type="secondary">{checked.installed === null ? "Unavailable" : checked.installed ? "Installed" : "Missing"}</Text>
      </SettingRow>
      <SettingRow label="Game sign-in">
        <Text type="secondary">{checked.village ? "Village visible" : "Open your village"}</Text>
      </SettingRow>
    </>}
  </>;
}

export function Settings({ tab, dashboard, embedded }) {
  const { catalog, value } = dashboard;
  const fields = catalog.fieldsByPath;

  function row(entry) {
    if (Array.isArray(entry)) return <PairedRow key={entry[0]} paths={entry} fields={fields} dashboard={dashboard} />;
    if (typeof entry === "string") {
      const rule = catalog.visibility[entry];
      if (rule && !rule[1].includes(value(rule[0]))) return null;
      const field = fields[entry];
      if (field.control === "builders" && !(dashboard.settings.builders?.[entry] > 1)) return null;
      return <SettingField key={entry} field={field} dashboard={dashboard} />;
    }
    if (entry.fold) {
      const rows = entry.fields.map(row).filter(Boolean);
      return rows.length ? <Disclosure key={entry.fold} label={entry.fold} help={entry.help}>{rows}</Disclosure> : null;
    }
    if (entry.action === "connection") return <Connection key={entry.action} dashboard={dashboard} />;
    if (entry.action === "display") return <DisplayActions key={entry.action} dashboard={dashboard} />;
    if (entry.action === "read_storages") return <ReadStorages key={entry.action} paths={entry.fields} dashboard={dashboard} />;
    return null;
  }

  return <Flex vertical gap={12}>
    {tab.groups.map((group, index) => {
      if (group.when && !group.when[1].includes(value(group.when[0]))) return null;
      const rows = group.fields.map(row).filter(Boolean);
      return rows.length ? <SettingsSection key={index} title={group.title} description={group.help} embedded={embedded}>
        {rows}
      </SettingsSection> : null;
    })}
  </Flex>;
}
