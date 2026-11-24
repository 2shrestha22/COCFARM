"""Command line: run the bot, open the GUI, and calibrate from screenshots."""

from __future__ import annotations

import argparse
import logging
import shutil
import signal
import sys
import threading
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

import cv2
import numpy as np

from farmbot import bluestacks, catalog, imagefile, text
from farmbot.accounts import load_active
from farmbot.config import Config, DeviceConfig, ensure_config
from farmbot.device import AdbDevice, DeviceError, list_adb_devices
from farmbot.game import T, normalize_screen
from farmbot.geometry import Rect
from farmbot.runner import run_farm
from farmbot.vision import TemplateLibrary, Vision


def _config(args: argparse.Namespace) -> Config:
    # Like the GUI, use farmbot.toml when no file is named, creating it from
    # the starting profile on first run.
    if args.config is None:
        ensure_config("farmbot.toml")
        return load_active("farmbot.toml")
    return load_active(args.config)


def _device(args: argparse.Namespace, cfg: Config) -> AdbDevice:
    if args.serial is not None:  # an explicit override, including blank for discovery
        cfg.device.mode, cfg.device.serial = "manual", args.serial.strip()
    return bluestacks.open_device(cfg.device)


def _screen(args: argparse.Namespace, cfg: Config) -> np.ndarray:
    if getattr(args, "image", None):
        image = imagefile.read(args.image, cv2.IMREAD_COLOR)
        if image is None:
            raise FileNotFoundError(f"cannot read {args.image}")
    else:
        image = _device(args, cfg).screenshot()
    return normalize_screen(image, _vision(cfg), cfg.device.ui_scale)


def _vision(cfg: Config) -> Vision:
    return Vision(TemplateLibrary(cfg.bot.templates), cfg.bot.threshold)


class StillDevice:
    """A device that always shows the same screenshot (for ``inspect``)."""

    def __init__(self, screen: np.ndarray):
        self._screen = screen

    def screenshot(self) -> np.ndarray:
        return self._screen


def cmd_screenshot(args: argparse.Namespace) -> int:
    cfg = _config(args)
    image = _screen(args, cfg)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    imagefile.write(str(out), image)
    print(f"saved {out} ({image.shape[1]}x{image.shape[0]}, scaled to the bot's coordinates)")
    return 0


def cmd_crop(args: argparse.Namespace) -> int:
    cfg = _config(args)
    image = _screen(args, cfg)
    r = Rect(args.x, args.y, args.w, args.h)
    crop = image[r.y:r.y + r.h, r.x:r.x + r.w]
    if crop.size == 0:
        print("crop rectangle is outside the image", file=sys.stderr)
        return 1
    out = Path(cfg.bot.templates) / f"{args.name}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    imagefile.write(str(out), crop)
    print(f"saved template {out}")
    return 0


def cmd_locate(args: argparse.Namespace) -> int:
    cfg = _config(args)
    matches = _vision(cfg).find_all(_screen(args, cfg), args.name, args.threshold)
    for m in matches:
        print(f"{m.name}\t({m.x}, {m.y})\tscore {m.score:.3f}")
    if not matches:
        print("no match")
    return 0 if matches else 2


def cmd_learn_digits(args: argparse.Namespace) -> int:
    cfg = _config(args)
    region = Rect(args.x, args.y, args.w, args.h)
    saved = text.learn(_screen(args, cfg), region, args.text, Path(cfg.bot.templates) / T.LOOT_FONT, replace=args.replace)
    print(f"saved {len(saved)} glyph(s): {', '.join(p.name for p in saved) or 'none new'}")
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    """Show what the bot sees on a scouting screen."""
    from farmbot.inspect import describe

    cfg = _config(args)
    lines, overlay = describe(_screen(args, cfg), cfg, _vision(cfg))
    print("\n".join(lines))
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    imagefile.write(str(out), overlay)
    print(f"overlay: {out}")
    return 0


def _device_selection(device: DeviceConfig, states: dict[str, str]) -> str:
    if device.mode == "manual":
        serial = device.serial.strip()
        label = serial
        if not serial:
            if not states:
                return "automatic selection (not connected)"
            if len(states) > 1:
                return "automatic selection (multiple devices found, select a serial)"
            serial, = states
            label = f"automatic selection: {serial}"
    else:
        from farmbot import instances

        label = instances.describe(device)
        key = instances.key_of(device).casefold()
        choices = instances.choices(device)
        if device.mode == "bluestacks" and not key:
            choice = next(iter(choices), None)
        else:
            choice = next((item for item in choices if key in (item.key.casefold(), item.label.casefold())), None)
        if choice is None or not choice.port:
            return f"{label} (ADB address unavailable)"
        serial = f"127.0.0.1:{choice.port}"
        label = f"{label} [{serial}]"
    state = states.get(serial)
    status = "connected" if state == "device" else f"not connected: {state}" if state else "not connected"
    return f"{label} ({status})"


def cmd_devices(args: argparse.Namespace) -> int:
    path = Path(args.config or "farmbot.toml")
    device = load_active(path).device if args.config is not None or path.is_file() else DeviceConfig()
    if args.serial is not None:
        device.mode, device.serial = "manual", args.serial.strip()
    install = bluestacks.find_install() if device.adb_path in ("", "adb") and not shutil.which("adb") else None
    devices = list_adb_devices(bluestacks.adb_program(device, install))
    print(f"Configured device: {_device_selection(device, dict(devices))}")
    if not devices:
        print("No ADB devices found.")
        return 2
    print("ADB devices:")
    for serial, state in devices:
        print(f"  {serial}\t{state}")
    if any(state == "device" for _, state in devices):
        return 0
    print("No ADB devices are ready.")
    return 2


def cmd_pictures(args: argparse.Namespace) -> int:
    library = TemplateLibrary(_config(args).bot.templates)
    feature = None
    for p in catalog.PICTURES:
        if p.feature != feature:
            feature = p.feature
            print(f"\n{feature}{' (required)' if p.required else ''}")
        count = len(library.paths(p.name))
        mark = "ok " if count else "MISSING" if p.required else "ADD" if p.feature == catalog.QUICK_EXIT else "-  "
        extra = f" x{count}" if p.folder and count else ""
        print(f"  {mark:7} {p.name}{extra}: {p.where}")
    missing = catalog.missing(library, required_only=True)
    if missing:
        print(f"\n{len(missing)} required picture(s) missing. Add them under Advanced → Pictures in the window, or with 'farmbot crop'.")
    return 2 if missing else 0


def cmd_run(args: argparse.Namespace) -> int:
    from farmbot import instances

    if args.farm > 1:  # another farm's settings (the Farms page adds them)
        instances.mend_sizes()
        path = instances.config_path(args.farm)
        if not path.is_file():
            print(f"error: there's no farm {args.farm} (add it on the Farms page)", file=sys.stderr)
            return 1
        cfg = load_active(path)
        cfg.home = path.parent
        instances.mark(args.farm)
    else:
        cfg = _config(args)
        # The farm's folder, as the window has it: the village data is kept there and read once a
        # day, not again every run (18 Nov: each run from the command line went to Data Export).
        cfg.home = Path(args.config or "farmbot.toml").resolve().parent
    if args.max_attacks is not None:
        cfg.bot.max_attacks = args.max_attacks
    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    trace_dir = cfg.home / "screens" / "deploy-trace" if args.trace_deploy else None
    run_farm(cfg, stop, serial=args.serial, deploy_trace=trace_dir)
    return 0


def cmd_web(args: argparse.Namespace) -> int:
    from farmbot.web import serve

    path = Path(args.config or "farmbot.toml").resolve()
    if args.config is None:
        ensure_config(path)
    try:
        return serve(path, args.serial, args.port)
    except OSError as exc:
        raise ValueError(f"Could not start the dashboard: {exc}") from exc


def cmd_display(args: argparse.Namespace) -> int:
    from farmbot.display import configure_manual

    cfg = _config(args)
    if args.serial is not None:
        cfg.device.mode, cfg.device.serial = "manual", args.serial.strip()
    if args.action == "apply":
        for suffix in ("width", "height", "dpi"):
            value = getattr(args, suffix)
            if value is not None:
                setattr(cfg.device, f"manual_{suffix}", value)
        cfg.validate()
    print(configure_manual(cfg.device, args.action))
    return 0


def cmd_gui(args: argparse.Namespace) -> int:
    if args.start:
        from farmbot.gui_wake import hand_over_start

        if hand_over_start():  # a COCFARM is open: it starts instead
            return 0
    from farmbot import splash  # Qt is only needed here

    splash.show()  # while the rest loads
    from farmbot import installed
    from farmbot.gui import run_gui

    if installed.built():
        from farmbot import carry

        # Before this folder takes over Installed apps: where your farms were until now.
        carry.look(Path(args.config or "farmbot.toml").resolve().parent)
    installed.ensure()  # in the Start menu and Installed apps

    return run_gui(args.config or "farmbot.toml", args.serial, start=args.start)


def cmd_uninstall(args: argparse.Namespace) -> int:
    from farmbot import installed

    return installed.uninstall()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="farmbot", description=__doc__)
    parser.add_argument("-c", "--config", default=None, help="TOML settings file")
    parser.add_argument("-s", "--serial", default=None,
                        help="ADB serial, overrides the config (empty selects the sole connected device)")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("gui", help="open the control window")
    p.add_argument("--start", action="store_true",
                   help="start farm 1 straight away (Windows opens COCFARM so: Close COCFARM between upgrades)")
    p.set_defaults(func=cmd_gui)

    p = sub.add_parser("uninstall", help="remove COCFARM (the built exe's folder), after asking")
    p.set_defaults(func=cmd_uninstall)

    p = sub.add_parser("run", help="start farming without the GUI (Ctrl+C to stop)")
    p.add_argument("--max-attacks", type=int, default=None)
    p.add_argument("--farm", type=int, default=1, help="which farm's settings (the GUI's Farms page adds them)")
    p.add_argument("--trace-deploy", action="store_true",
                   help="save live deployment frames, candidates and troop inputs to screens/deploy-trace")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("web", help="start the local web dashboard")
    p.add_argument("--port", type=int, default=8765, help="loopback port (0 picks a free port)")
    p.add_argument("--no-browser", action="store_true", help=argparse.SUPPRESS)  # accepted by older launch scripts
    p.set_defaults(func=cmd_web)

    p = sub.add_parser("display", help="read, apply, or reset a custom ADB device's display")
    actions = p.add_subparsers(dest="action", required=True)
    apply = actions.add_parser("apply", help="set the width, height, and density")
    apply.add_argument("--width", type=int, help="width in pixels (defaults to the config)")
    apply.add_argument("--height", type=int, help="height in pixels (defaults to the config)")
    apply.add_argument("--dpi", type=int, help="density (defaults to the config)")
    actions.add_parser("reset", help="restore the device's native size and density")
    actions.add_parser("show", help="read the current size and density")
    p.set_defaults(func=cmd_display)

    p = sub.add_parser("devices", help="show the configured device and devices visible to ADB")
    p.set_defaults(func=cmd_devices)

    p = sub.add_parser("pictures", help="list the button pictures the bot uses and which are missing")
    p.set_defaults(func=cmd_pictures)

    p = sub.add_parser("screenshot", help="save the device screen (scaled to bot coordinates)")
    p.add_argument("output", nargs="?", default="screens/screen.png")
    p.set_defaults(func=cmd_screenshot)

    p = sub.add_parser("inspect", help="show loot, troop cards and deploy points the bot sees")
    p.add_argument("--image", help="screenshot file instead of the live screen")
    p.add_argument("--output", default="screens/inspect.png")
    p.set_defaults(func=cmd_inspect)

    p = sub.add_parser("crop", help="cut a template out of a screenshot")
    p.add_argument("image")
    for name in ("x", "y", "w", "h"):
        p.add_argument(name, type=int)
    p.add_argument("name", help="template name, e.g. buttons/return_home")
    p.set_defaults(func=cmd_crop)

    p = sub.add_parser("locate", help="test a template against a screenshot or the live screen")
    p.add_argument("name")
    p.add_argument("--image", help="screenshot file instead of the live screen")
    p.add_argument("--threshold", type=float, default=None)
    p.set_defaults(func=cmd_locate)

    p = sub.add_parser("learn-digits", help="learn loot digit shapes from a number on screen")
    p.add_argument("image")
    for name in ("x", "y", "w", "h"):
        p.add_argument(name, type=int)
    p.add_argument("text", help='the number shown, e.g. "1 582 869"')
    p.add_argument("--replace", action="store_true", help="overwrite digits already learned")
    p.set_defaults(func=cmd_learn_digits)
    return parser


LOG_FILE = "logs/farmbot.log"
LOG_DAYS = 14


def log_to_file(path: str) -> None:
    """Keep the activity log on disk too: a new file each midnight, the last
    ``LOG_DAYS`` days kept, so a problem can be looked at after the fact."""

    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        handler = _DailyLog(path, when="midnight", backupCount=LOG_DAYS, encoding="utf-8")
    except OSError as exc:
        logging.getLogger(__name__).warning("Not logging to %s: %s", path, exc)
        return
    handler.addFilter(_farm_tag)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(farm_tag)s%(name)s: %(message)s"))
    logging.getLogger().addHandler(handler)


class _DailyLog(TimedRotatingFileHandler):
    """A new file each midnight, unless another program (a second COCFARM
    window) has the log open: Windows won't rename it then. It carries on
    in the same file until the next midnight, rather than lose every line
    (the standard handler tries again, and fails, for each one)."""

    def rotate(self, source: str, dest: str) -> None:
        try:
            super().rotate(source, dest)
        except OSError:
            pass


def _farm_tag(record: logging.LogRecord) -> bool:
    """Marks the lines of farm 2 and up with their farm (see farmbot/instances.py)."""
    if not hasattr(record, "farm_tag"):
        farm = getattr(record, "farm", 0)
        record.farm_tag = f"[farm {farm}] " if farm > 1 else ""
    return True


def gui_main() -> int:
    """``cocfarm``: open the GUI (a windowed program, so no console opens)."""
    return main(["gui", *sys.argv[1:]])


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # Windows consoles default to a code page without characters like "→".
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )
    if args.func in (cmd_run, cmd_gui, cmd_web):
        log_to_file(LOG_FILE)
        from farmbot import diag

        diag.install(Path(LOG_FILE).parent)  # (a windowed program has no console for what nothing caught)
        logging.getLogger(__name__).info(diag.startup())  # first thing a bug report's log shows
    try:
        return args.func(args)
    except (DeviceError, FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
