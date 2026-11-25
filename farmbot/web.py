"""Terminal-launched dashboard for a single local farm."""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import deque
from contextlib import contextmanager
from dataclasses import asdict
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ipaddress import ip_address
from pathlib import Path
from secrets import token_urlsafe
from urllib.parse import parse_qs, urlsplit

from farmbot import bluestacks, catalog, display, gamecheck, history, instances
from farmbot.accounts import Profiles, load_active, save_active
from farmbot.config import Config, load_config
from farmbot.device import DeviceError
from farmbot.form import plan_summary, validate
from farmbot.game import Game, Stopped
from farmbot.history import AttackRecord
from farmbot.human import HABITS
from farmbot.runner import run_farm
from farmbot.tasks.search import Loot
from farmbot.timings import Timings, cost, duration
from farmbot.vision import TemplateLibrary, Vision
from farmbot.web_settings import apply, schema, values_for, village_controls

log = logging.getLogger(__name__)
ASSETS = Path(__file__).with_name("assets")
STATIC = {
    "/": ("dashboard.html", "text/html; charset=utf-8"),
    "/dashboard.css": ("dashboard.css", "text/css; charset=utf-8"),
    "/dashboard.js": ("dashboard.js", "text/javascript; charset=utf-8"),
    "/cocfarm.png": ("cocfarm.png", "image/png"),
}
EMPTY_LOOT = Loot(0, 0, 0)
DISPLAY_VALUES = {"device.manual_width", "device.manual_height", "device.manual_dpi"}
CONNECTION_VALUES = {"device.mode", "device.serial", "device.adb_path"}


class DashboardLogs(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.setFormatter(logging.Formatter("%(asctime)s  %(levelname)s  %(message)s", "%H:%M:%S"))
        self.lines: deque[tuple[int, str]] = deque(maxlen=300)
        self.sequence = 0

    def emit(self, record: logging.LogRecord) -> None:
        self.sequence += 1
        self.lines.append((self.sequence, self.format(record)))

    def since(self, sequence: int) -> list[tuple[int, str]]:
        with self.lock:
            return [(index, line) for index, line in self.lines if index > sequence]


class Dashboard:
    def __init__(self, path: Path, serial: str | None) -> None:
        self.path = path
        self.serial = serial
        self.profiles = Profiles.beside(path)
        self.logs = DashboardLogs()
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.pause = threading.Event()
        self.worker: threading.Thread | None = None
        self.closed = False
        self.checking = False
        self.message = "Ready"
        self.mode: str | None = None
        self.resources: Loot | None = None
        self.attacks = 0
        self.bases = 0
        self.scout: dict | None = None
        self.gained = EMPTY_LOOT
        self.last_attack: dict | None = None
        self.builder = {"battles": 0, "gained": EMPTY_LOOT, "last": None, "walls": 0, "cart_in": None}
        self.started: float | None = None
        self.finished: float | None = None
        self.failed = False

    def settings(self) -> dict:
        with self.lock:
            return self._settings(load_active(self.path))

    def _settings(self, config: Config) -> dict:
        values = values_for(config)
        plan = plan_summary(validate(values)[0]).removesuffix(" Press Start (F5).")
        profile = config.profiles.active
        return {"values": values, "plan": plan, "file": self.path.name, "serial": self.serial,
                "active": profile, "profiles": self.profiles.names(), **village_controls(self.path, self.profiles, profile)}

    def save_settings(self, values: dict, profile: str) -> dict:
        with self.lock:
            config = load_active(self.path)
            if config.profiles.active != profile:
                raise ValueError("The active profile changed. Reload the dashboard before saving.")
            apply(config, values, self.serial)
            save_active(config, self.path)
            return self._settings(config)

    def select_profile(self, name: str) -> dict:
        with self.lock:
            if name and name not in self.profiles.names():
                raise ValueError("That profile could not be found")
            main = load_config(self.path)
            config = self.profiles.load(name, main) if name else main
            config.profiles.active = name
            save_active(config, self.path)
            return self._settings(config)

    def state(self, since: int) -> dict:
        with self.lock:
            return {
                "running": self.worker is not None,
                "stopping": self.worker is not None and self.stop.is_set(),
                "pause_requested": self.pause.is_set(),
                "failed": self.failed,
                "message": self.message,
                "mode": self.mode,
                "attacks": self.attacks,
                "bases": self.bases,
                "scout": self.scout,
                "gained": asdict(self.gained),
                "last_attack": self.last_attack,
                "builder": {**self.builder, "gained": asdict(self.builder["gained"])},
                "seconds": int((self.finished or time.monotonic()) - self.started) if self.started is not None else None,
                "resources": asdict(self.resources) if self.resources is not None else None,
                "logs": self.logs.since(since),
            }

    def control(self, action: str) -> None:
        with self.lock:
            if self.closed:
                raise ValueError("The dashboard is shutting down")
            if action == "start":
                if self.checking:
                    raise ValueError("Wait for the device operation to finish")
                if self.worker is not None:
                    raise ValueError("The farm is already running")
                config = load_active(self.path)
                config.home = self.path.parent
                self.stop.clear()
                self.pause.clear()
                self.failed = False
                self.mode = config.bot.mode
                self.resources = None
                self.attacks = 0
                self.bases = 0
                self.scout = self.last_attack = None
                self.gained = EMPTY_LOOT
                self.builder = {"battles": 0, "gained": EMPTY_LOOT, "last": None, "walls": 0, "cart_in": None}
                self.started, self.finished = time.monotonic(), None
                self.message = "Connecting to the device…"
                self.worker = threading.Thread(target=self._run, args=(config,), name="dashboard-farm")
                self.worker.start()
            elif self.worker is None or self.stop.is_set():
                raise ValueError("There is no active farm to control")
            elif action == "pause":
                self.pause.set()
                self.message = "Pausing at the next safe point…"
            elif action == "resume":
                self.pause.clear()
                self.message = "Resuming…"
            elif action == "stop":
                self.stop.set()
                self.message = "Stopping…"

    def _run(self, config: Config) -> None:
        error = ""
        try:
            run_farm(config, self.stop, serial=self.serial, pause=self.pause, on_status=self._status,
                     on_resources=self._resources, on_attack=self._attack, on_base=self._scout,
                     on_builder=self._builder)
        except Stopped:
            pass
        except Exception as exc:
            error = str(exc) or type(exc).__name__
            log.error("Farm stopped: %s", error)
        finally:
            with self.lock:
                self.message = error or ("Stopped" if self.stop.is_set() else "Finished")
                self.failed = bool(error)
                self.worker = None
                self.finished = time.monotonic()
                self.pause.clear()

    def _status(self, message: str) -> None:
        with self.lock:
            if not self.stop.is_set():
                self.message = message

    def _resources(self, loot: Loot) -> None:
        with self.lock:
            self.resources = loot

    def _scout(self, loot: Loot, accepted: bool) -> None:
        with self.lock:
            self.bases += 1
            self.scout = {"loot": asdict(loot), "accepted": accepted}

    def _attack(self, record: AttackRecord) -> None:
        with self.lock:
            self.attacks += 1
            gained = record.gained
            if gained is not None:
                self.gained = history.add(self.gained, gained)
            self.last_attack = {"offered": asdict(record.target), "gained": asdict(gained) if gained else None}

    def _builder(self, battle: dict) -> None:
        with self.lock:
            self.builder["battles"] += 1
            self.builder["walls"] += battle.get("walls", 0)
            self.builder["cart_in"] = battle.get("cart_in")
            self.builder["last"] = {"stages": battle["stages"], "seconds": battle["seconds"]}
            if battle.get("gained") is not None:
                self.builder["gained"] = history.add(self.builder["gained"], battle["gained"])

    def attack_history(self) -> dict:
        config = load_active(self.path)
        config.home = self.path.parent
        rows = history.read_all(instances.resolve(config, config.bot.history)) if config.bot.history else []
        totals = history.daily_totals(rows)
        today = date.today()
        week = today - timedelta(days=6)
        summaries = []
        for title, start in (("Today", today), ("Last 7 days", week), ("All time", None)):
            count, gain = 0, EMPTY_LOOT
            for day, (attacks, loot) in totals.items():
                if start is None or day >= start:
                    count += attacks
                    gain = history.add(gain, loot)
            summaries.append({"title": title, "count": count, "loot": asdict(gain)})
        hourly = history.per_hour([row for row in rows if row.time.date() >= week])
        summaries.append({"title": "Per hour of play", "count": None, "loot": asdict(hourly) if hourly else None})
        days = [today - timedelta(days=offset) for offset in range(13, -1, -1)]
        return {"summaries": summaries,
                "days": [[day.isoformat(), asdict(totals.get(day, (0, EMPTY_LOOT))[1])] for day in days],
                "rows": [asdict(row) | {"time": row.time.isoformat()} for row in reversed(rows[-300:])]}

    def pictures(self) -> dict:
        library = TemplateLibrary(load_active(self.path).bot.templates)
        return {"pictures": [{"title": picture.title, "where": picture.where, "feature": picture.feature,
                               "present": catalog.present(library, picture)} for picture in catalog.PICTURES]}

    def farms(self) -> dict:
        root = self.path.parent
        device = load_active(self.path).device
        title = "Automatic ADB selection" if device.mode == "manual" and not device.serial else instances.describe(device)
        farms = [{"number": 1, "device": title, "current": True}]
        for number in instances.numbers(root)[1:]:
            farms.append({"number": number, "device": instances.describe(instances.device_of(number, root)),
                          "current": False})
        return {"farms": farms}

    @contextmanager
    def _device_operation(self):
        with self.lock:
            if self.worker is not None or self.checking:
                raise ValueError("Stop the farm and wait for any device operation to finish")
            config = load_active(self.path)
            self.checking = True
        try:
            yield config
        finally:
            with self.lock:
                self.checking = False

    def _select_serial(self, config: Config) -> None:
        if self.serial is not None:
            config.device.mode, config.device.serial = "manual", self.serial.strip()

    def check_device(self) -> dict:
        with self._device_operation() as config:
            self._select_serial(config)
            device = bluestacks.open_device(config.device)
            height, width = device.screenshot().shape[:2]
            installed = gamecheck.installed(device, config.device.package) if hasattr(device, "shell") else None
            game = Game(device, Vision(TemplateLibrary(config.bot.templates), config.bot.threshold),
                        ui_scale=config.device.ui_scale, window_scale=config.device.window_scale,
                        picture_scales=config.device.picture_scales)
            return {"screen": f"{width} × {height}", "installed": installed, "village": gamecheck.in_a_village(game)}

    def configure_display(self, action: str, changes: dict) -> dict:
        allowed = CONNECTION_VALUES | DISPLAY_VALUES if action == "apply" else CONNECTION_VALUES
        if changes.keys() - allowed:
            raise ValueError("A display operation accepts only the device and display settings")
        with self._device_operation() as config:
            apply(config, changes, self.serial)
            self._select_serial(config)
            return {"display": display.configure_manual(config.device, action)}

    def close(self) -> None:
        with self.lock:
            self.closed = True
            self.stop.set()
            worker = self.worker
        if worker is not None:
            worker.join()


def request_handler(dashboard: Dashboard) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def _valid_host(self) -> bool:
            # Accept this connection's destination, not arbitrary Host headers:
            # remote access must not remove the DNS-rebinding protection.
            address = self.connection.getsockname()[0]
            names = {address, self.server.server_name}
            if ip_address(address).is_loopback:
                names.add("localhost")
            hosts = self.headers.get_all("Host", [])
            return len(hosts) == 1 and hosts[0] in {
                f"{name}:{self.server.server_port}" for name in names
            }

        def log_message(self, *_args) -> None:
            pass

        def _send(self, body: bytes, content_type: str, status: int = 200) -> None:
            policy = "default-src 'self'; frame-ancestors 'none'"
            if content_type.startswith("text/html"):
                # Ant Design attaches this nonce to its generated theme styles.
                nonce = token_urlsafe(24)
                body = body.replace(b"__DASHBOARD_STYLE_NONCE__", nonce.encode("ascii"))
                policy += f"; style-src 'self' 'nonce-{nonce}'"
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", policy)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, value: dict, status: int = 200) -> None:
            self._send(json.dumps(value).encode(), "application/json", status)

        def do_GET(self) -> None:
            if not self._valid_host():
                self._json({"error": "Use the dashboard server's address and port"}, 403)
                return
            path = urlsplit(self.path)
            try:
                if path.path in STATIC:
                    name, content_type = STATIC[path.path]
                    self._send((ASSETS / name).read_bytes(), content_type)
                elif path.path == "/api/settings":
                    self._json(dashboard.settings())
                elif path.path == "/api/settings/schema":
                    self._json(schema())
                elif path.path == "/api/history":
                    self._json(dashboard.attack_history())
                elif path.path == "/api/pictures":
                    self._json(dashboard.pictures())
                elif path.path == "/api/farms":
                    self._json(dashboard.farms())
                elif path.path == "/api/status":
                    since = int(parse_qs(path.query).get("since", ["0"])[0])
                    self._json(dashboard.state(since))
                else:
                    self._json({"error": "Page not found"}, 404)
            except (ValueError, OSError) as exc:
                self._json({"error": str(exc)}, 400)

        def do_POST(self) -> None:
            if (not self._valid_host()
                    or self.headers.get_all("Origin", []) != [f"http://{self.headers.get('Host')}"]):
                self._json({"error": "Use the dashboard's same-origin page to make changes"}, 403)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if self.headers.get_content_type() != "application/json" or not 0 < length <= 16384:
                    raise ValueError("Expected a JSON request")
                value = json.loads(self.rfile.read(length))
                if not isinstance(value, dict):
                    raise ValueError("Expected a JSON object")
                if self.path == "/api/settings":
                    changes, profile = value.get("changes"), value.get("profile")
                    if not isinstance(changes, dict) or not isinstance(profile, str):
                        raise ValueError("Expected settings changes and a profile")
                    self._json(dashboard.save_settings(changes, profile))
                elif self.path == "/api/profile":
                    name = value.get("name")
                    if not isinstance(name, str):
                        raise ValueError("Expected a profile name")
                    self._json(dashboard.select_profile(name))
                elif self.path == "/api/check-device":
                    self._json(dashboard.check_device())
                elif self.path == "/api/display":
                    action, changes = value.get("action"), value.get("changes", {})
                    if not isinstance(action, str) or not isinstance(changes, dict):
                        raise ValueError("Expected a display action and device settings")
                    self._json(dashboard.configure_display(action, changes))
                elif self.path == "/api/timings":
                    enabled = value.get("habits")
                    if not isinstance(enabled, list):
                        raise ValueError("Expected a list of habits")
                    habits = {habit.key for habit in HABITS if habit.key in enabled}
                    timings = Timings()
                    self._json({village: [[name, duration(plain), cost(added) if added >= .005 else "—", duration(total)]
                                          for name, plain, added, total in timings.summary(village, habits)]
                                for village in ("home", "builder")})
                elif self.path in ("/api/start", "/api/stop", "/api/pause", "/api/resume"):
                    since = value.get("since", 0)
                    if type(since) is not int or since < 0:
                        raise ValueError("Invalid log cursor")
                    dashboard.control(self.path.removeprefix("/api/"))
                    self._json(dashboard.state(since))
                else:
                    self._json({"error": "Page not found"}, 404)
            except (DeviceError, ValueError, OSError) as exc:
                self._json({"error": str(exc)}, 400)

    return Handler


def serve(path: Path, serial: str | None, port: int, host: str = "127.0.0.1") -> int:
    if not 0 <= port <= 65535:
        raise ValueError("Port must be between 0 and 65535")
    dashboard = Dashboard(path, serial)
    dashboard.settings()
    root_logger = logging.getLogger()
    with ThreadingHTTPServer((host, port), request_handler(dashboard)) as server:
        root_logger.addHandler(dashboard.logs)
        url = f"http://{'127.0.0.1' if host == '0.0.0.0' else host}:{server.server_port}"
        print(f"COCFARM dashboard at {url} (Ctrl+C to close)", flush=True)
        if host == "0.0.0.0":
            print(f"Network access enabled: http://<this computer's LAN or Tailscale IP>:{server.server_port}",
                  flush=True)
        if not ip_address(server.server_address[0]).is_loopback:
            print("Warning: this dashboard has no login. Use only on trusted networks; do not expose it publicly.",
                  flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            dashboard.close()
            root_logger.removeHandler(dashboard.logs)
    return 0
