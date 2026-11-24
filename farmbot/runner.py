"""Run a farm from a terminal or a local dashboard."""

from __future__ import annotations

import logging
from pathlib import Path
from threading import Event
from typing import Callable

from farmbot import bluestacks, catalog
from farmbot.bot import Bot
from farmbot.config import EMULATORS, Config
from farmbot.deploytrace import DeployTrace
from farmbot.game import Game
from farmbot.history import AttackRecord
from farmbot.tasks.search import Loot
from farmbot.vision import TemplateLibrary, Vision

log = logging.getLogger(__name__)


def run_farm(config: Config, stop: Event, *, serial: str | None = None, pause: Event | None = None,
             deploy_trace: Path | None = None,
             on_status: Callable[[str], None] | None = None, on_resources: Callable[[Loot], None] | None = None,
             on_attack: Callable[[AttackRecord], None] | None = None,
             on_base: Callable[[Loot, bool], None] | None = None,
             on_builder: Callable[[dict], None] | None = None) -> None:
    library = TemplateLibrary(config.bot.templates)
    if not config.search.maintain_only:
        missing = catalog.missing(library, required_only=True)
        if missing:
            raise ValueError("pictures missing: " + ", ".join(p.name for p in missing) + " (see 'farmbot pictures')")
        if catalog.slow_exit(library):
            log.info("Without buttons/return_home and buttons/okay the bot closes the game to leave each battle")

    if serial is not None:
        config.device.mode, config.device.serial = "manual", serial.strip()
    device = bluestacks.open_device_retrying(config.device)
    if stop.is_set():
        return
    bluestacks.prepare_gestures(config.device, device)
    if stop.is_set():
        return
    game = Game(device, Vision(library, config.bot.threshold), stop_event=stop, ui_scale=config.device.ui_scale,
                window_scale=config.device.window_scale, picture_scales=config.device.picture_scales)
    if deploy_trace is not None:
        game.deploy_trace = DeployTrace(deploy_trace)
    reopen = (lambda: bluestacks.restart_emulator(config.device)) if config.device.mode in EMULATORS else None
    Bot(game, config, pause_event=pause, reopen_device=reopen,
        on_status=on_status, on_resources=on_resources, on_attack=on_attack, on_base=on_base,
        on_builder=on_builder).run()
