import { useEffect, useState } from "react";
import { Alert, Button, Input, Select, Tag, Typography, theme } from "antd";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { format, lootText, request, resourceNames } from "./dashboard";
import { Panel } from "./panel";
import { DataTable, SettingRow, SettingsSection } from "./settings";

const { Text } = Typography;
const compactNumber = new Intl.NumberFormat(undefined, { notation: "compact" });

function useRemote(path, body) {
  const [result, setResult] = useState(null);
  const [revision, setRevision] = useState(0);
  const bodyKey = JSON.stringify(body);
  useEffect(() => {
    let alive = true;
    request(path, bodyKey === undefined ? undefined : JSON.parse(bodyKey)).then(
      (data) => { if (alive) setResult({ data }); },
      (error) => { if (alive) setResult({ error: error.message }); },
    );
    return () => { alive = false; };
  }, [path, bodyKey, revision]);
  return { ...result, refresh: () => setRevision((current) => current + 1) };
}

function FetchState({ error }) {
  return error
    ? <Alert type="error" showIcon title={error} />
    : <Text type="secondary" role="status">Loading…</Text>;
}

function HistoryChart({ days, selected }) {
  const { token } = theme.useToken();
  const colors = { gold: token.colorWarning, elixir: token.colorPrimary, dark: token.colorTextSecondary };
  const keys = selected ? [selected] : Object.keys(resourceNames);
  return <ResponsiveContainer width="100%" height={224}>
    <BarChart accessibilityLayer data={days.map(([day, loot]) => ({ day, ...loot }))}>
      <CartesianGrid stroke={token.colorBorderSecondary} vertical={false} />
      <XAxis dataKey="day" tick={{ fill: token.colorTextSecondary, fontSize: 12 }}
        tickLine={false} axisLine={false} tickFormatter={(day) => day.slice(5)} />
      <YAxis tick={{ fill: token.colorTextSecondary, fontSize: 12 }} width={42}
        tickLine={false} axisLine={false} tickFormatter={compactNumber.format} />
      <Tooltip formatter={(value) => format.format(value)}
        contentStyle={{ background: token.colorBgElevated, borderColor: token.colorBorder, color: token.colorText }} />
      {!selected && <Legend />}
      {keys.map((key) => <Bar key={key} dataKey={key} name={resourceNames[key]} fill={colors[key]} radius={4} />)}
    </BarChart>
  </ResponsiveContainer>;
}

function History() {
  const { data, error, refresh } = useRemote("/api/history");
  const [selected, setSelected] = useState("");
  if (error || !data) return <FetchState error={error} />;
  const keys = Object.keys(resourceNames);
  return <div className="grid grid-cols-1 gap-4">
    <Panel title="Totals" actions={<Button size="small" onClick={refresh}>Refresh</Button>}>
      <dl className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        {data.summaries.map((summary) => <div key={summary.title}>
          <dt className="text-sm font-medium">{summary.title}</dt>
          <dd><Text type="secondary">{summary.count === null
            ? (summary.loot ? format.format(summary.loot.gold + summary.loot.elixir) : "—")
            : format.format(summary.count) + (summary.count === 1 ? " attack" : " attacks")}</Text></dd>
          {summary.loot && <dd><Text type="secondary">{lootText(summary.loot)}</Text></dd>}
        </div>)}
      </dl>
    </Panel>
    <Panel title="Loot gained per day" actions={<Select aria-label="Show loot"
      className="min-w-32" value={selected} onChange={setSelected}
      options={[{ value: "", label: "All loot" }, ...Object.entries(resourceNames).map(([value, name]) => ({ value, label: name + " only" }))]} />}>
      {data.days.length ? <HistoryChart days={data.days} selected={selected} />
        : <Text type="secondary">No loot recorded yet.</Text>}
    </Panel>
    <Panel title="Attacks">
      {data.rows.length ? <DataTable headers={["Time", "Offered gold", "Offered elixir", "Offered dark", "Gained gold", "Gained elixir", "Gained dark"]}
        rows={data.rows.map((record) => [new Date(record.time).toLocaleString(),
          ...[record.target, record.gained].flatMap((loot) => keys.map((key) => loot ? format.format(loot[key]) : "—"))])} />
        : <Text type="secondary">No attacks recorded yet.</Text>}
    </Panel>
  </div>;
}

function Farms({ dashboard }) {
  const { data, error } = useRemote("/api/farms");
  if (error || !data) return <FetchState error={error} />;
  return <div className="grid gap-4">
    <SettingsSection title="Your farms">
      {data.farms.map((farm) => <SettingRow key={farm.number} label={"Farm " + farm.number} help={farm.device}>
        {farm.current && <Tag color="processing">Current farm</Tag>}
      </SettingRow>)}
    </SettingsSection>
    <SettingsSection title="Accounts and profiles">
      <SettingRow label="Configuration file"><span className="text-sm">{dashboard.settings.file}</span></SettingRow>
      <SettingRow label="Settings profile">
        <Select aria-label="Settings profile" className="w-full @md/field-group:w-56"
          value={dashboard.settings.active} disabled={dashboard.busy} onChange={dashboard.selectProfile}
          options={[{ value: "", label: "Default" }, ...dashboard.settings.profiles.map((name) => ({ value: name, label: name }))]} />
      </SettingRow>
    </SettingsSection>
  </div>;
}

function Pictures() {
  const { data, error } = useRemote("/api/pictures");
  const [query, setQuery] = useState("");
  if (error || !data) return <FetchState error={error} />;
  const visible = data.pictures.filter((picture) => (picture.title + " " + picture.feature).toLowerCase().includes(query.toLowerCase().trim()));
  return <div className="grid gap-4">
    <Input type="search" aria-label="Find a picture" placeholder="Find a picture" value={query}
      className="max-w-xs" onChange={(event) => setQuery(event.target.value)} />
    {visible.length ? <SettingsSection>
      {visible.map((picture, index) => <SettingRow key={index} label={picture.title} help={picture.where}>
        <Tag color={picture.present ? "success" : undefined}>{picture.present ? "Available" : "Missing"}</Tag>
      </SettingRow>)}
    </SettingsSection> : <Text type="secondary">No pictures match your search.</Text>}
  </div>;
}

function Timings({ dashboard }) {
  const habits = dashboard.value("human.enabled") ? dashboard.catalog.fields
    .filter(({ path }) => path.startsWith("human.") && path !== "human.enabled" && dashboard.value(path))
    .map(({ path }) => path.slice(6)) : [];
  const { data, error } = useRemote("/api/timings", { habits });
  if (error || !data) return <FetchState error={error} />;
  return <div className="grid grid-cols-1 items-start gap-3 xl:grid-cols-2">
    {[["home", "Home village"], ["builder", "Builder base"]].map(([key, title]) =>
      <Panel title={title + " timing"} key={key}>
        <DataTable headers={["Step", "Without habits", "Added", "With habits"]} rows={data[key]} />
      </Panel>
    )}
  </div>;
}

function Report({ logs }) {
  return <Panel title="Step-by-step log">
    <pre tabIndex={0} className="h-80 overflow-auto whitespace-pre-wrap wrap-anywhere text-sm">
      {logs.slice(-60).map(([, line]) => line).join("\n") || "Nothing to report yet."}
    </pre>
  </Panel>;
}

export function PageDetails({ page, tab, dashboard }) {
  if (page === "history") return <History />;
  if (page === "farms") return <Farms dashboard={dashboard} />;
  if (page === "like_a_person" && tab === "person") return <Timings dashboard={dashboard} />;
  if (page === "advanced") {
    if (tab === "pictures") return <Pictures />;
    if (tab === "report") return <Report logs={dashboard.logs} />;
  }
  return null;
}
