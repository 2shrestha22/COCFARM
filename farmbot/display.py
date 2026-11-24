"""The display Android itself uses, checked against farmbot.standard.

The emulators' own settings are set to the standard when the bot connects
(farmbot.mumu, .bluestacks, .ldplayer), but what the game is drawn at is
what Android reports: an override (``wm size``, ``wm density``) left by an
app or by hand, or an emulator that didn't apply its own DPI setting, makes
the game draw its windows at another size than the pictures were taken at,
and buttons such as the upgrade window's Confirm go unseen. An emulator's
display is put back (overrides dropped, or the standard set). Manual
devices can apply or reset size and density on demand.
"""

from __future__ import annotations

import logging
import re

from farmbot import standard
from farmbot.config import DeviceConfig
from farmbot.device import DeviceError

log = logging.getLogger(__name__)


def _values(out: str) -> tuple[str, str]:
    """``(physical, override)`` from ``wm size`` / ``wm density`` output
    (override empty when there's none)."""
    physical = override = ""
    for line in out.splitlines():
        if ":" not in line:
            continue
        key, value = (part.strip() for part in line.split(":", 1))
        if key.lower().startswith("physical"):
            physical = value
        elif key.lower().startswith("override"):
            override = value
    return physical, override


def _size(value: str, *, ordered: bool = False) -> tuple[int, int] | None:
    m = re.fullmatch(r"(\d+)\s*x\s*(\d+)", value)
    if not m:
        return None
    width, height = int(m[1]), int(m[2])
    if not width or not height:
        return None
    return (width, height) if ordered or width <= height else (height, width)


def matches_physical_size(output: str) -> bool:
    """Does Android report the same effective and physical display dimensions?"""
    physical, override = _values(output)
    native = _size(physical, ordered=True)
    return native is not None and _size(override or physical, ordered=True) == native


def _density(value: str) -> int | None:
    return int(value) if value.isdigit() else None


WANTED_SIZE = tuple(sorted((standard.WIDTH, standard.HEIGHT)))


def configure_manual(cfg: DeviceConfig, action: str) -> str:
    """Read, apply, or reset the selected manual device's size and density."""
    from farmbot.bluestacks import open_device

    if cfg.mode != "manual":
        raise ValueError("Choose Other under Emulator to configure an ADB device's display")
    if action not in ("show", "apply", "reset"):
        raise ValueError(f"Unknown display action: {action}")
    device = open_device(cfg)
    before = _read_display(device)
    if action == "show":
        return _describe(before)

    reset = action == "reset"
    wanted = {"size": "reset" if reset else f"{cfg.manual_width}x{cfg.manual_height}",
              "density": "reset" if reset else str(cfg.manual_dpi)}
    attempted = []
    try:
        for name, command in wanted.items():
            original, override = before[name]
            if (reset and not override) or (not reset and (override or original) == command):
                continue
            attempted.append(name)
            device.shell("wm", name, command)
        after = _read_display(device) if attempted else before
        for name, command in wanted.items():
            original, override = after[name]
            if (reset and override) or (not reset and (override or original) != command):
                raise DeviceError(f"Android reported {name} {override or original} after wm {name} {command}")
    except DeviceError as exc:
        if not attempted:
            raise
        failures = []
        for name in reversed(attempted):
            try:
                device.shell("wm", name, before[name][1] or "reset")
            except DeviceError:
                failures.append(name)
        if not failures:
            try:
                restored = _read_display(device)
                failures = [name for name in attempted if restored[name] != before[name]]
            except DeviceError:
                failures = attempted
        status = f" Could not verify restoration of {' and '.join(failures)}." if failures else " Previous display settings restored."
        raise DeviceError(f"{exc}{status}") from exc
    return _describe(after)


def _read_display(device) -> dict[str, tuple[str, str]]:
    values = {name: _values(device.shell("wm", name)) for name in ("size", "density")}
    for name, parse in (("size", _size), ("density", _density)):
        original, override = values[name]
        if parse(original) is None or (override and parse(override) is None):
            raise DeviceError(f"Could not read Android's display {name}")
    return values


def _describe(values: dict[str, tuple[str, str]]) -> str:
    original_size, size = values["size"]
    original_dpi, dpi = values["density"]
    return f"{size or original_size} at {dpi or original_dpi} DPI (native {original_size} at {original_dpi} DPI)"


def check(device, fix: bool) -> list[str]:
    """Check the display Android uses; with ``fix``, put it back to the
    standard. What was wrong (put back or not), one line each; empty if
    it's right or the device can't say."""
    shell = getattr(device, "shell", None)
    if shell is None:
        return []
    found: list[str] = []
    try:
        size_out, density_out = str(shell("wm", "size")), str(shell("wm", "density"))
    except Exception:  # noqa: BLE001 - a device that can't say is left alone
        return []
    want_size = f"{standard.WIDTH}x{standard.HEIGHT}"

    physical, override = _values(size_out)
    physical_size = _size(physical)
    if physical_size is not None and _size(override or physical) != WANTED_SIZE:
        if override and _size(override) != physical_size:
            detail = f"display size overridden to {override} (its own {physical})"
        else:
            detail = f"display size {physical}"
        if fix and physical_size == WANTED_SIZE:
            shell("wm", "size", "reset")
            found.append(f"{detail}: reset to {physical}")
        elif fix:
            shell("wm", "size", want_size)
            found.append(f"{detail}: set to {want_size}")
        else:
            found.append(f"{detail}, expected {want_size}")

    physical, override = _values(density_out)
    if _density(physical) is not None:
        using = _density(override) or _density(physical)
        if using != standard.DPI:
            if fix and _density(physical) == standard.DPI:
                shell("wm", "density", "reset")
                found.append(f"density overridden to {using}: reset to {standard.DPI}")
            elif fix:
                shell("wm", "density", str(standard.DPI))
                found.append(f"density {using}: set to {standard.DPI}")
            else:
                found.append(f"density {using}, not {standard.DPI}")
    return found
