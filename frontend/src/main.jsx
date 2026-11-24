import { useEffect, useLayoutEffect, useRef, useState, useSyncExternalStore } from "react";
import { createRoot } from "react-dom/client";
import {
  BuildOutlined, CalendarOutlined, DashboardOutlined, DesktopOutlined, DownOutlined, FileTextOutlined, HistoryOutlined, HomeOutlined,
  MenuFoldOutlined, MenuUnfoldOutlined, PauseOutlined, PlayCircleOutlined, RobotOutlined, SettingOutlined,
  StopOutlined, TrophyOutlined,
} from "@ant-design/icons";
import { Alert, App as AntApp, Button, Card, ConfigProvider, Drawer, Grid, Layout, Menu, Segmented, Space, Tag, Typography, theme } from "antd";
import { duration, format, resourceNames, switchStoragePrompt, useDashboard } from "./dashboard";
import { PageDetails } from "./details";
import { Settings } from "./settings";

const navIcons = {
  dashboard: DashboardOutlined, home_village: HomeOutlined, builder_base: BuildOutlined, wars_and_raids: TrophyOutlined,
  when_to_play: CalendarOutlined, like_a_person: RobotOutlined, history: HistoryOutlined,
  advanced: SettingOutlined, farms: DesktopOutlined,
};
const { Text } = Typography;
const { Content, Sider } = Layout;
const modeLabels = { home: "Home village", builder: "Builder base", auto: "Auto switch" };
const logEntryPattern = /^(\d{2}:\d{2}:\d{2}) {2}(\w+) {2}([\s\S]*)$/;
const card = { headerHeightSM: 44, headerFontSizeSM: 15, headerPaddingSM: 16, bodyPaddingSM: 16 };
const themes = {
  light: {
    algorithm: theme.defaultAlgorithm,
    token: { colorBgLayout: "#f4f6fa", colorTextDescription: "#596474" },
    components: { Card: card },
  },
  dark: {
    algorithm: theme.darkAlgorithm,
    token: {
      colorBgLayout: "#11151c", colorBgContainer: "#1a202a", colorBorderSecondary: "#343d4c",
      colorTextSecondary: "#a7b2c2", colorTextDescription: "#a7b2c2", colorPrimaryText: "#91caff",
    },
    components: {
      Card: card,
      Menu: { itemSelectedColor: "#91caff" },
      Segmented: { itemSelectedBg: "#2c3d56", itemSelectedColor: "#e1efff" },
    },
  },
};
const prefersDark = window.matchMedia("(prefers-color-scheme: dark)");
const csp = { nonce: document.querySelector('script[src="/dashboard.js"]')?.nonce };

function subscribeToSystemTheme(onChange) {
  prefersDark.addEventListener("change", onChange);
  return () => prefersDark.removeEventListener("change", onChange);
}

function systemIsDark() {
  return prefersDark.matches;
}

function farmStatus(farm, error) {
  if (error || farm?.failed) return { label: "Error", color: "error" };
  if (!farm) return { label: "Connecting" };
  if (farm.stopping || farm.pause_requested) {
    return { label: farm.stopping ? "Stopping" : "Paused", color: "warning" };
  }
  if (farm.running) return { label: "Running", color: "success" };
  if (farm.seconds == null) return { label: "Ready" };
  return { label: farm.message === "Finished" ? "Finished" : "Stopped" };
}

function FarmActions({ dashboard }) {
  const { farm, busy, control, connectionError } = dashboard;
  if (!farm?.running) {
    return <Button type="primary" icon={<PlayCircleOutlined />}
      disabled={busy || !farm || Boolean(connectionError) || dashboard.switchStorageRequired}
      onClick={() => control("start")}>Start</Button>;
  }
  return <Space size={6} wrap>
    <Button icon={farm.pause_requested ? <PlayCircleOutlined /> : <PauseOutlined />}
      disabled={busy || farm.stopping} onClick={() => control(farm.pause_requested ? "resume" : "pause")}>
      {farm.pause_requested ? "Resume" : "Pause"}
    </Button>
    <Button danger type="primary" icon={<StopOutlined />} disabled={busy || farm.stopping}
      onClick={() => control("stop")}>Stop</Button>
  </Space>;
}

function DashboardShell({ pages, active, navigate, status, dashboard, saveMessage, children }) {
  const { token } = theme.useToken();
  const desktop = Grid.useBreakpoint().md;
  const [collapsed, setCollapsed] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const navigation = <Menu mode="inline" aria-label="Dashboard pages" selectedKeys={active ? [active] : []}
    items={pages.map((page) => {
      const Icon = navIcons[page.key];
      return { key: page.key, label: page.title, icon: Icon && <Icon /> };
    })}
    onClick={({ key }) => { navigate(key); setMenuOpen(false); }} />;
  const headerBorder = "1px solid " + token.colorBorderSecondary;
  return <Layout style={{ minHeight: "100dvh" }}>
    {desktop ? <Sider theme="light" width={192} collapsedWidth={52} collapsed={collapsed} trigger={null} collapsible
      className="top-0 h-dvh self-start overflow-y-auto" style={{ position: "sticky", borderInlineEnd: headerBorder }}>
      <div className="mb-2 flex h-14 items-center gap-2 px-4" style={{ borderBlockEnd: headerBorder }}>
        <img src="/cocfarm.png" width="20" height="20" alt="" />
        {!collapsed && <Text strong>COCFARM</Text>}
      </div>
      {navigation}
    </Sider> : <Drawer title="COCFARM" placement="left" size={240} open={menuOpen}
      onClose={() => setMenuOpen(false)} styles={{ body: { padding: 0 } }}>
      {navigation}
    </Drawer>}
    <Layout className="min-w-0">
      <header className="sticky top-0 z-10" style={{ background: token.colorBgContainer, borderBlockEnd: headerBorder }}>
        <div className="mx-auto flex min-h-14 max-w-4xl flex-wrap items-center gap-x-3 gap-y-2 px-3 py-2 sm:px-6">
          <div className="flex min-w-0 items-center gap-2" style={{ color: token.colorText }}>
            <Button type="text" icon={desktop && !collapsed ? <MenuFoldOutlined /> : <MenuUnfoldOutlined />} aria-label="Toggle navigation"
              aria-expanded={desktop ? !collapsed : menuOpen}
              onClick={() => desktop ? setCollapsed(!collapsed) : setMenuOpen(!menuOpen)} />
            <h1 className="text-lg leading-tight font-semibold sm:text-xl">{pages.find((page) => page.key === active)?.title || "COCFARM"}</h1>
          </div>
          {dashboard.settings && <Space size={8} wrap style={{ marginInlineStart: "auto" }}>
            {active !== "dashboard" && <Tag color={status.color} style={{ marginInlineEnd: 0 }}>{status.label}</Tag>}
            <FarmActions dashboard={dashboard} />
          </Space>}
          {saveMessage && <div className="basis-full text-right text-xs" role="status"><Text type="secondary">{saveMessage}</Text></div>}
        </div>
      </header>
      <Content className="min-w-0" style={{ color: token.colorText }}>
        <div className="mx-auto grid w-full min-w-0 max-w-4xl grid-cols-1 gap-4 px-3 py-4 sm:gap-5 sm:px-6 sm:py-6">{children}</div>
      </Content>
    </Layout>
  </Layout>;
}

function Metric({ label, value }) {
  return <div className="min-w-0">
    <dt><Text type="secondary">{label}</Text></dt>
    <dd className="text-base font-semibold tabular-nums wrap-anywhere">{value}</dd>
  </div>;
}

function HomeTotals({ farm }) {
  return <dl className="session-metrics grid grid-cols-2 gap-2 @xl/field-group:grid-cols-5">
    <Metric label="Bases seen" value={format.format(farm.bases)} />
    <Metric label="Attacks" value={format.format(farm.attacks)} />
    {Object.entries(resourceNames).map(([key, name]) =>
      <Metric key={key} label={name + " gained"} value={format.format(farm.gained[key])} />
    )}
  </dl>;
}

function BuilderTotals({ builder }) {
  return <dl className="session-metrics grid grid-cols-2 gap-2 @lg/field-group:grid-cols-4">
    <Metric label="Battles" value={format.format(builder?.battles ?? 0)} />
    <Metric label="Gold gained" value={format.format(builder?.gained.gold ?? 0)} />
    <Metric label="Elixir gained" value={format.format(builder?.gained.elixir ?? 0)} />
    <Metric label="Walls upgraded" value={format.format(builder?.walls ?? 0)} />
  </dl>;
}

function RunDetails({ farm, mode, showBuilder }) {
  const storage = farm.resources;
  const target = farm.scout?.loot ?? farm.last_attack?.offered;
  const builder = showBuilder ? farm.builder : undefined;
  const hasBuilderDetails = builder?.last || builder?.cart_in != null;
  if (!storage && !target && !hasBuilderDetails) return null;

  return <details className="session-readings">
    <summary>Run details</summary>
    <div className="grid gap-3 pt-2">
      {(storage || target) && <table>
        <thead><tr>
          <th scope="col">Resource</th>
          {storage && <th scope="col">Last storage reading</th>}
          {target && <th scope="col">{farm.scout ? "Latest scout offer" : "Last attack offer"}</th>}
        </tr></thead>
        <tbody>{Object.entries(resourceNames).map(([key, name]) => {
          if (key === "dark" && mode === "builder" && !target && !storage?.dark) return null;
          return <tr key={key}>
            <th scope="row">{name}</th>
            {storage && <td>{format.format(storage[key])}</td>}
            {target && <td>{format.format(target[key])}</td>}
          </tr>;
        })}</tbody>
      </table>}
      {((storage && mode === "auto") || farm.scout) && <div className="flex flex-wrap gap-x-4 gap-y-1">
        {storage && mode === "auto" && <Text type="secondary">Storage shows the latest reading from either village.</Text>}
        {farm.scout && <Text type="secondary">Latest scout: {farm.scout.accepted ? "selected for attack" : "skipped"}.</Text>}
      </div>}
      {hasBuilderDetails && <dl className="grid grid-cols-2 gap-2">
        {builder.last && <Metric label="Last Builder battle" value={builder.last.stages + " stages · " + duration(builder.last.seconds)} />}
        {builder.cart_in != null && <Metric label="Elixir cart" value={builder.cart_in > 0 ? "In " + builder.cart_in + " battles" : "Due"} />}
      </dl>}
    </div>
  </details>;
}

function RunTotals({ farm, mode, firstVillage }) {
  const [village, setVillage] = useState(null);
  const view = mode === "auto" ? village ?? firstVillage ?? "home" : mode;
  const showBuilder = view === "builder";
  return <div className="session-details">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h3 className="text-base font-semibold">Run totals</h3>
      {mode === "auto" && <Segmented aria-label="Village totals" value={view} onChange={setVillage}
        options={[{ value: "home", label: modeLabels.home }, { value: "builder", label: modeLabels.builder }]} />}
    </div>
    {showBuilder ? <BuilderTotals builder={farm.builder} /> : <HomeTotals farm={farm} />}
    <RunDetails farm={farm} mode={mode} showBuilder={showBuilder} />
  </div>;
}

function FarmOverview({ farm, status, mode, firstVillage, connectionError, children }) {
  const { token } = theme.useToken();
  const started = farm?.seconds != null;
  const tones = {
    success: [token.colorSuccessText, token.colorSuccessBg],
    warning: [token.colorWarningText, token.colorWarningBg],
    error: [token.colorErrorText, token.colorErrorBg],
  };
  const [accent, tint] = tones[status.color] || [token.colorPrimaryText, token.colorPrimaryBg];
  const message = connectionError ? "Trying to reconnect to the dashboard."
    : farm?.message !== status.label ? farm?.message : undefined;
  return <Card size="small" className="@container/field-group min-w-0" style={{
    "--session-accent": accent, "--session-tint": tint, "--session-surface": token.colorBgLayout,
    "--session-divider": token.colorBorderSecondary,
  }}>
    <div className="session-heading">
      <span className="session-icon"><DashboardOutlined aria-hidden="true" /></span>
      <div className="min-w-0">
        <h2 className="session-label">Farm status</h2>
        <div role="status">
          <div className="session-state">{status.label}</div>
          {message && <Text type="secondary" className="wrap-anywhere">{message}</Text>}
        </div>
      </div>
      {started && <dl className="session-meta">
        <Metric label="Runtime" value={duration(farm.seconds)} />
        <Metric label="Run mode" value={modeLabels[mode] || "—"} />
      </dl>}
    </div>
    {started && <RunTotals farm={farm} mode={mode} firstVillage={firstVillage} />}
    <div className="session-settings">{children}</div>
  </Card>;
}

function LogEntry({ line }) {
  const parts = logEntryPattern.exec(line);
  if (!parts) return <li className="activity-entry activity-entry-plain">{line}</li>;
  const [, time, level, message] = parts;
  return <li className="activity-entry">
    <time className="activity-time">{time}</time>
    <span className="activity-level" data-level={level}>{level}</span>
    <span className="activity-message">{message}</span>
  </li>;
}

function ActivityLog({ logs, clear }) {
  const { token } = theme.useToken();
  const [open, setOpen] = useState(true);
  const toggle = useRef(null);
  const view = useRef(null);
  const follow = useRef(true);
  const hasLogs = logs.length > 0;
  useEffect(() => {
    const viewport = view.current;
    if (viewport && follow.current) viewport.scrollTop = viewport.scrollHeight;
  }, [logs, open]);
  useEffect(() => {
    const viewport = view.current;
    const entries = viewport?.firstElementChild;
    if (!entries) return;
    const observer = new ResizeObserver(() => {
      if (follow.current) viewport.scrollTop = viewport.scrollHeight;
    });
    observer.observe(entries);
    return () => observer.disconnect();
  }, [hasLogs]);
  return <Card className="activity-log min-w-0" size="small" styles={{ body: { padding: 0 } }}
    style={{ "--log-hover": token.colorFillTertiary, "--log-focus": token.colorPrimary,
      "--log-surface": token.colorBgLayout, "--log-border": token.colorBorderSecondary,
      "--log-muted": token.colorTextDescription, "--log-info": token.colorPrimaryText,
      "--log-warning": token.colorWarningText, "--log-error": token.colorErrorText }}>
    <h2>
      <button type="button" ref={toggle} className="activity-log-toggle" id="farm-log-toggle" aria-expanded={open}
        aria-controls="farm-log" onClick={() => setOpen((expanded) => !expanded)}>
        Step-by-step log <DownOutlined aria-hidden="true" />
      </button>
    </h2>
    <div id="farm-log" role="region" aria-labelledby="farm-log-toggle" hidden={!open}
      style={{ borderBlockStart: "1px solid " + token.colorBorderSecondary }}>
      <div className="grid gap-3 p-4">
        {hasLogs ? <>
          <div ref={view} tabIndex={0} role="group" aria-label="Log entries" className="activity-viewport"
            onScroll={(event) => {
              const area = event.currentTarget;
              follow.current = area.scrollHeight - area.clientHeight - area.scrollTop < 32;
            }}>
            <ol className="activity-entries">
              {logs.map(([id, line]) => <LogEntry key={id} line={line} />)}
            </ol>
          </div>
          <div className="flex justify-end">
            <Button size="small" onClick={() => {
              follow.current = true;
              clear();
              toggle.current?.focus();
            }}>Clear log</Button>
          </div>
        </> : <div className="activity-empty">
          <FileTextOutlined aria-hidden="true" />
          <Text type="secondary">No activity yet</Text>
        </div>}
      </div>
    </div>
  </Card>;
}

function DashboardPage({ dashboard, tab, status }) {
  const { farm, settings, connectionError } = dashboard;
  return <div className="@container/dashboard grid grid-cols-1 gap-4 sm:gap-5">
    {connectionError && <Alert type="error" showIcon title={connectionError} />}
    <FarmOverview farm={farm} status={status} mode={farm?.mode || settings.values["bot.mode"]}
      firstVillage={settings.values["bot.auto_first"]} connectionError={connectionError}>
      <Settings tab={tab} dashboard={dashboard} embedded />
    </FarmOverview>
    <ActivityLog logs={dashboard.logs} clear={dashboard.clearLog} />
  </div>;
}

function routeFromHash() {
  const [page, tab] = location.hash.slice(1).split("/");
  return { page, tab };
}

function App() {
  const dashboard = useDashboard();
  const systemDark = useSyncExternalStore(subscribeToSystemTheme, systemIsDark);
  const appearance = dashboard.settings ? dashboard.value("bot.theme") : "auto";
  const dark = appearance === "dark" || (appearance === "auto" && systemDark);
  const [route, setRoute] = useState(routeFromHash);
  const lastTabs = useRef({});
  const pages = dashboard.catalog?.pages || [];
  const page = pages.find((item) => item.key === route.page) || pages[0];
  const tab = page?.tabs.find((item) => item.key === route.tab) || page?.tabs[0];
  const status = farmStatus(dashboard.farm, dashboard.connectionError);
  const save = dashboard.saveStatus;
  const saveError = save?.kind === "error";
  const switchStorageRequired = dashboard.switchStorageRequired;
  const saveMessage = save && !saveError && !switchStorageRequired && (save.kind === "saved"
    ? (dashboard.farm?.running ? "Saved for next run" : "Saved") : "Saving…");

  useLayoutEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
  }, [dark]);
  useEffect(() => {
    function hashChange() { setRoute(routeFromHash()); }
    window.addEventListener("hashchange", hashChange);
    return () => window.removeEventListener("hashchange", hashChange);
  }, []);
  useEffect(() => {
    if (page && tab?.label) lastTabs.current[page.key] = tab.key;
    document.title = page ? page.title + " · COCFARM" : "COCFARM";
    window.scrollTo(0, 0);
  }, [page?.key, tab?.key]);
  useEffect(() => {
    if (!page || !tab || tab.label || location.hash !== "#" + page.key + "/" + tab.key) return;
    window.history.replaceState(window.history.state, "", "#" + page.key);
    setRoute(routeFromHash());
  }, [page, tab, route]);

  function navigationHref(key, tabKey = lastTabs.current[key]) {
    return "#" + key + (tabKey ? "/" + tabKey : "");
  }

  function pageBody() {
    if (page.key === "dashboard") return <DashboardPage dashboard={dashboard} tab={tab} status={status} />;
    const content = <div className="grid min-w-0 gap-4">
      {tab?.groups.length > 0 && <Settings tab={tab} dashboard={dashboard} />}
      <PageDetails key={page.key + "/" + tab?.key} page={page.key} tab={tab?.key} dashboard={dashboard} />
    </div>;
    if (!tab?.label) return content;
    return <div className="grid min-w-0 gap-4">
      <nav className="flex flex-wrap gap-1" aria-label={page.title + " sections"}>
        {page.tabs.map(({ key, label }) => <Button key={key} href={navigationHref(page.key, key)}
          aria-current={key === tab.key ? "page" : undefined} color={key === tab.key ? "primary" : "default"}
          variant={key === tab.key ? "filled" : "text"}>{label}</Button>)}
      </nav>
      <section className="min-w-0" aria-label={tab.label}>{content}</section>
    </div>;
  }

  return <ConfigProvider theme={dark ? themes.dark : themes.light} csp={csp}>
    <AntApp>
      <DashboardShell pages={pages} active={page?.key} navigate={(key) => { location.hash = navigationHref(key); }}
        status={status} dashboard={dashboard} saveMessage={saveMessage}>
        {!page || !dashboard.settings ? <Text type="secondary" role={dashboard.connectionError ? "alert" : "status"}>
          {dashboard.connectionError || "Loading dashboard…"}
        </Text> : <>
          {switchStorageRequired && page.key !== "dashboard" && <Alert type="error" showIcon role="status"
            title={switchStoragePrompt}
            action={<Button type="link" size="small" href="#dashboard">Open Auto switch settings</Button>} />}
          {saveError && !switchStorageRequired && <Alert type="error" showIcon title="Settings couldn’t be saved"
            description={save.message} action={<Button size="small" disabled={dashboard.busy} onClick={dashboard.retrySave}>Retry</Button>} />}
          {dashboard.notice && dashboard.notice.text !== save?.message &&
            !(switchStorageRequired && dashboard.notice.text === switchStoragePrompt) && <Alert
              type={dashboard.notice.error ? "error" : "success"} showIcon
              role={dashboard.notice.error ? "alert" : "status"} title={dashboard.notice.text} />}
          {pageBody()}
        </>}
      </DashboardShell>
    </AntApp>
  </ConfigProvider>;
}

createRoot(document.getElementById("app")).render(<App />);
