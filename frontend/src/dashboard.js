import { useEffect, useRef, useState } from "react";

export const format = new Intl.NumberFormat();
export const resourceNames = { gold: "Gold", elixir: "Elixir", dark: "Dark elixir" };
const resourceKeys = Object.keys(resourceNames);
const minimumFields = new Set(resourceKeys.map((key) => "search.min_" + key));
export const suggestedMinimums = "search.minimums_by_hand";
export const switchStoragePrompt = "Choose at least one storage to save Auto switch.";
const saveDelay = 400;
const sameValue = (left, right) => JSON.stringify(left) === JSON.stringify(right);

function needsSwitchStorage({ settings, edits }) {
  const saved = settings?.values;
  return (edits["bot.mode"] ?? saved?.["bot.mode"]) === "auto" &&
    !(edits["bot.stop_when_full"] ?? saved["bot.stop_when_full"]).length;
}

export function duration(seconds) {
  if (seconds == null) return "—";
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor(seconds / 60) % 60;
  const clock = [minutes, seconds % 60].map((part) => String(part).padStart(2, "0")).join(":");
  return hours ? hours + ":" + clock : clock;
}

export function lootText(loot) {
  if (!loot) return "—";
  return resourceKeys.map((key) => resourceNames[key] + " " + format.format(loot[key])).join(" · ");
}

export async function request(path, values) {
  const response = await fetch(path, values === undefined ? {} : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(values),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Dashboard request failed");
  return data;
}

export function useDashboard() {
  const [catalog, setCatalog] = useState(null);
  const [draft, setDraft] = useState({ settings: null, edits: {} });
  const latestDraft = useRef(draft);
  const { settings, edits } = draft;
  const switchStorageRequired = needsSwitchStorage(draft);
  const [farm, setFarm] = useState(null);
  const [logs, setLogs] = useState([]);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState(null);
  const [saveStatus, setSaveStatus] = useState(null);
  const [connectionError, setConnectionError] = useState("");
  const sequence = useRef(0);
  const ongoing = useRef(false);
  const controlVersion = useRef(0);
  const revision = useRef(0);
  const inFlight = useRef(null);

  function updateDraft(next) {
    latestDraft.current = next;
    setDraft(next);
  }

  function showState(data) {
    setFarm(data);
    const fresh = data.logs.filter(([index]) => index > sequence.current);
    if (fresh.length) {
      sequence.current = fresh.at(-1)[0];
      setLogs((lines) => lines.concat(fresh).slice(-300));
    }
  }

  useEffect(() => {
    let alive = true;
    let timeout;
    let loaded = false;
    async function monitor() {
      const version = controlVersion.current;
      try {
        if (!loaded) {
          const [schema, data] = await Promise.all([request("/api/settings/schema"), request("/api/settings")]);
          if (!alive) return;
          setCatalog({ ...schema, fieldsByPath: Object.fromEntries(schema.fields.map((field) => [field.path, field])) });
          updateDraft({ settings: data, edits: {} });
          loaded = true;
        }
        if (ongoing.current) return;
        const data = await request("/api/status?since=" + sequence.current);
        if (alive && version === controlVersion.current) {
          setConnectionError("");
          showState(data);
        }
      } catch (error) {
        if (alive && version === controlVersion.current) setConnectionError(error.message);
      } finally {
        if (alive) timeout = setTimeout(monitor, 1_000);
      }
    }
    monitor();
    return () => {
      alive = false;
      clearTimeout(timeout);
    };
  }, []);

  function value(path) {
    if (settings.serial !== null) {
      if (path === "device.mode") return "manual";
      if (path === "device.serial") return settings.serial;
    }
    return Object.hasOwn(edits, path) ? edits[path] : settings.values[path];
  }

  function edit(path, next) {
    if (ongoing.current) return;
    setNotice(null);
    revision.current += 1;
    const current = latestDraft.current;
    const changes = { ...current.edits };
    const submitted = inFlight.current?.changes || {};
    function update(field, value) {
      // Retain a revert to the old saved value while an earlier write is changing that field.
      if (sameValue(value, current.settings.values[field]) && !Object.hasOwn(submitted, field)) delete changes[field];
      else changes[field] = value;
    }
    update(path, next);
    if (minimumFields.has(path) && Object.hasOwn(changes, path)) update(suggestedMinimums, true);
    updateDraft({ settings: current.settings, edits: changes });
    setSaveStatus(Object.keys(changes).length ? { kind: "pending" } : null);
  }

  function saveEdits() {
    if (inFlight.current) return inFlight.current.promise;
    const { settings: base, edits: changes } = latestDraft.current;
    if (needsSwitchStorage(latestDraft.current)) return Promise.reject(new Error(switchStoragePrompt));
    if (!Object.keys(changes).length) return Promise.resolve();

    const sentRevision = revision.current;
    setSaveStatus({ kind: "saving" });
    const promise = request("/api/settings", { changes, profile: base.active }).then((data) => {
      const pending = Object.fromEntries(Object.entries(latestDraft.current.edits).filter(([path, value]) =>
        !sameValue(value, changes[path]) && !sameValue(value, data.values[path])
      ));
      updateDraft({ settings: data, edits: pending });
      setSaveStatus({ kind: Object.keys(pending).length ? "pending" : "saved" });
    }).catch((error) => {
      if (sentRevision === revision.current) setSaveStatus({ kind: "error", message: error.message });
      throw error;
    }).finally(() => { inFlight.current = null; });
    inFlight.current = { changes, promise };
    return promise;
  }

  useEffect(() => {
    if (busy || switchStorageRequired || !Object.keys(edits).length) return;
    const expected = revision.current;
    const timer = setTimeout(async () => {
      // A newer edit can arrive while the previous request is still in flight.
      await inFlight.current?.promise.catch(() => {});
      if (!ongoing.current && revision.current === expected) await saveEdits().catch(() => {});
    }, saveDelay);
    return () => clearTimeout(timer);
  }, [edits, busy, switchStorageRequired]);

  useEffect(() => {
    if (saveStatus?.kind !== "saved") return;
    const timer = setTimeout(() => setSaveStatus((current) => current === saveStatus ? null : current), 4_000);
    return () => clearTimeout(timer);
  }, [saveStatus]);

  async function flushEdits() {
    await inFlight.current?.promise.catch(() => {});
    await saveEdits();
  }

  async function act(operation, onError) {
    if (ongoing.current) return;
    ongoing.current = true;
    controlVersion.current += 1;
    setBusy(true);
    setNotice(null);
    try {
      await operation();
    } catch (error) {
      if (onError) onError(error.message);
      else setNotice({ text: error.message, error: true });
    } finally {
      setBusy(false);
      ongoing.current = false;
    }
  }

  return {
    catalog, settings, farm, logs, busy, notice, saveStatus, connectionError, switchStorageRequired, value, edit,
    clearLog: () => setLogs([]),
    retrySave: () => { if (!ongoing.current) void saveEdits().catch(() => {}); },
    control: (action) => act(async () => {
      if (action === "start") await flushEdits();
      showState(await request("/api/" + action, { since: sequence.current }));
    }),
    selectProfile: (name) => act(async () => {
      await flushEdits();
      updateDraft({ settings: await request("/api/profile", { name }), edits: {} });
      setSaveStatus(null);
    }),
    checkDevice: (onResult, onError) => act(async () => {
      await flushEdits();
      onResult(await request("/api/check-device", {}));
    }, onError),
    display: (action, onMessage) => act(async () => {
      const connection = ["device.mode", "device.serial", "device.adb_path"];
      const size = ["device.manual_width", "device.manual_height", "device.manual_dpi"];
      const names = action === "apply" ? [...connection, ...size] : connection;
      const changes = Object.fromEntries(Object.entries(latestDraft.current.edits).filter(([path]) => names.includes(path)));
      const data = await request("/api/display", { action, changes });
      onMessage(data.display);
    }, onMessage),
  };
}
