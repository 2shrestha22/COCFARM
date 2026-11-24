"""Browser editors for the shared farm settings model."""

from __future__ import annotations

import re
from functools import cache
from typing import Any

from farmbot import config
from farmbot.castle import CASTLES
from farmbot.form import BY_PATH, apply_form, form_values, validate
from farmbot.human import HABITS
from farmbot.tasks.row_names import PICKS
from farmbot.units import SIEGE_MACHINES, SPELLS, TROOPS
from farmbot.web_layout import PAIR_LABELS, PAGES, VISIBILITY

MINIMUMS = "search.minimums_by_hand"

LABELS = {
    "device.mode": "Emulator",
    "device.bluestacks_instance": "BlueStacks window",
    "device.launch_emulator": "Open the emulator automatically",
    "device.enable_adb": "Turn on ADB",
    "device.mute": "Keep the emulator muted",
    "device.serial": "ADB serial or address",
    "device.adb_path": "ADB program",
    "device.manual_width": "Display width",
    "device.manual_height": "Display height",
    "device.manual_dpi": "Display density (DPI)",
    "device.rooted_adb": "Use rooted ADB for gestures",
    "device.ldplayer": "LDPlayer version",
    "device.ldplayer_index": "LDPlayer instance number",
    "device.mumu_index": "MuMu instance number",
    "bot.mode": "Village",
    "bot.auto_first": "Start with",
    "bot.collect_gold": "Gold",
    "bot.collect_elixir": "Elixir",
    "bot.collect_ice": "Ice",
    "bot.collect_dark": "Dark",
    "bot.read_village": "Read the village data once a day",
    "bot.stop_when_full": "When these storages are full",
    "bot.check_updates": "Look for updates by itself",
    "search.min_gold": "At least this much gold",
    "search.min_elixir": "At least this much elixir",
    "search.min_dark": "At least this much dark elixir",
    "search.minimums_by_hand": "Suggested amounts",
    "search.match_any": "Any one is enough",
    "search.maintain_only": "Attack bases",
    "search.min_own_gold_share": "Don’t search while my gold is below",
    "search.max_searches": "Give up after",
    "attack.placement": "Troops go",
    "attack.sides": "Deploy from",
    "attack.super_troops": "Activate super troops",
    "attack.speed_up": "Play battles at 4x",
    "attack.star_bonus": "Earn the daily Star Bonus",
    "attack.end_when_no_loot": "Leave when the loot stops",
    "attack.end_when_full": "End battle when storages are full",
    "upgrade.order": "What to upgrade first",
    "upgrade.only": "Only these buildings",
    "upgrade.research_only": "Only this research",
    "upgrade.equipment_only": "Only this equipment",
    "upgrade.wake_up": "Close COCFARM between upgrades",
    "builder.corner": "Go in from",
    "builder.use_hero": "Hero goes first",
    "builder.upgrade_order": "What to upgrade first",
    "builder.clock_tower": "Use the Clock Tower’s free boost",
    "clan.donate": "Donate to requests",
    "clan.donate_main": "Main troops",
    "clan.donate_siege": "Siege machines",
    "clan.donate_spells": "Main spells",
    "clan.donate_presets": "Armies by Clan Castle level",
    "redline.enabled": "Follow the red line",
    "zone.enabled": "Otherwise go around the buildings",
    "ranked.enabled": "Make the day’s ranked attacks",
    "war.enabled": "Make your war attacks",
    "war.target": "Which base",
    "walls.enabled": "Upgrade walls with spare loot",
    "upgrade.enabled": "Upgrade automatically",
    "clan_games.enabled": "Play the Clan Games",
    "schedule.enabled": "Only play at certain hours",
    "schedule.breaks": "Take breaks",
    "schedule.day_off_every": "A day off about every",
    "human.enabled": "Play like a person",
    **{f"human.{habit.key}": habit.title for habit in HABITS},
}

HELP = {
    "device.mode": "Choose Other for a USB-connected Android device or an emulator at an ADB address.",
    "device.bluestacks_instance": "Which BlueStacks instance plays the game. Empty uses the main one.",
    "device.launch_emulator": "When you press Start and it isn’t open yet.",
    "device.serial": "Leave blank to use the sole connected ADB device.",
    "device.adb_path": "Use adb on PATH or enter the full path to the Android Platform-Tools executable.",
    "device.manual_width": "Width in pixels for Apply display.",
    "device.manual_height": "Height in pixels for Apply display.",
    "device.manual_dpi": "Density for Apply display. Reset display restores the device’s native DPI.",
    "device.rooted_adb": "Requests root when a farm starts, if the device supports rooted debugging.",
    "bot.theme": "Sets the Windows application’s appearance.",
    "bot.check_updates": "Controls update checks in the desktop application.",
    "bot.mode": "Its settings are on the page of the same name. Auto switch farms each village until its storages are full.",
    "bot.auto_first": "The village Auto switch farms first.",
    "bot.stop_when_full": "It stops once every resource you picked is full. Auto switch moves on to the other village first.",
    "search.maintain_only": "Off: it only collects, donates and looks after the village.",
    **{f"search.min_{kind}": "Bases offering less are skipped. 0 ignores it." for kind in ("gold", "elixir", "dark")},
    "search.minimums_by_hand": "Suggested amounts follow your Town Hall. Typing your own turns this off.",
    "search.match_any": "On: one amount above is enough. Off: a base must have them all.",
    "search.min_own_gold_share": "A share of your gold storages: each Next costs gold. 0% always searches.",
    "search.max_searches": "Bases skipped before it goes back to the village and starts over.",
    "search.sound_on_match": "Beeps when it finds a base worth attacking.",
    "attack.sides": "Laid out like the map. Troops spread over the sides you turn on.",
    "attack.waves": "Split each troop type into this many waves.",
    "redline.enabled": "Along the thin boundary the game draws around a base.",
    "zone.enabled": "Where there’s no red line. Off: along fixed lines at the map’s edges.",
    "schedule.enabled": "Off: plays whenever it’s running. On: only in the hours lit up below, using this PC’s time.",
    "schedule.breaks": "Rests now and then, at random, to play more like a person.",
    "schedule.day_off_every": "About one day in this many, it doesn’t play at all. 0 = never.",
    "upgrade.wake_up": "Windows desktop scheduling setting.",
    "clan.donate_presets": "Use comma-separated unit names. A count such as 1 Super Yeti limits that unit.",
    **{f"human.{habit.key}": habit.text for habit in HABITS},
}

CHOICES = {
    "device.mode": {"bluestacks": "BlueStacks", "ldplayer": "LDPlayer", "mumu": "MuMu", "manual": "Other"},
    "bot.mode": {"home": "Home village", "builder": "Builder base", "auto": "Auto switch"},
    "bot.auto_first": {"home": "Home village", "builder": "Builder base"},
    "bot.theme": {"auto": "Follow Windows", "light": "Light", "dark": "Dark"},
    "attack.placement": {"spread": "Spread", "loot": "Toward the loot"},
    "attack.spell_placement": {"together": "One spot", "spread": "Spread"},
    "attack.spells": {"bat": "Bat Spells only", "earthquake": "Bats and quakes", "all": "All spells"},
    "attack.spell_spot": config.SPELL_SPOTS,
    "attack.quake_aim": {"path": "Way in", "spots": "Middle"},
    "attack.funnel": config.FUNNELS,
    "attack.hero_walk": config.HERO_WALKS,
    "attack.walk_fox": tuple(config.WALK_FOXES),
    "builder.corner": config.BUILDER_CORNERS,
    "builder.first_hero": {"any": "Keep", "machine": "Battle Machine", "copter": "Battle Copter"},
    "builder.walls_use": config.WALL_RESOURCES,
    "walls.use": config.WALL_RESOURCES,
    "builder.upgrade_first": config.UPGRADE_FIRST,
    "upgrade.first": config.UPGRADE_FIRST,
    "war.target": {"mirror": "Recommended", "bottom": "Bottom", "gain": "Most stars"},
    "capital.district_order": {"destroyed": "Most destroyed", "stars": "Most stars"},
    "clan_games.goal": {"4000": "4,000", "10000": "10,000"},
    "clan_games.stuck_after": {"0": "Never", "3": "3 battles", "5": "5 battles"},
    "attack.sides": {"nw": "Top left", "ne": "Top right", "sw": "Bottom left", "se": "Bottom right"},
    "attack.waves": {wave: str(wave) for wave in (1, 2, 3)},
    "bot.stop_when_full": {"gold": "Gold", "elixir": "Elixir", "dark": "Dark elixir"},
    "schedule.active_hours": {hour: f"{hour:02d}:00" for hour in range(24)},
    "upgrade.order": config.UPGRADE_ORDER,
    "builder.upgrade_order": config.BUILDER_UPGRADE_ORDER,
    "upgrade.only": PICKS["buildings"],
    "upgrade.research_only": PICKS["research"],
    "upgrade.equipment_only": PICKS["equipment"],
    "clan.donate_main": tuple(unit.name for unit in TROOPS),
    "clan.donate_siege": tuple(unit.name for unit in SIEGE_MACHINES),
    "clan.donate_spells": tuple(unit.name for unit in SPELLS),
}

LISTS = {"sides", "resources", "hours", "units", "order", "buildings", "research", "equipment"}


def _label(value: str) -> str:
    words = value.replace("_", " ")
    if not words:
        return words
    return words[0].upper() + words[1:]


@cache
def schema() -> dict:
    fields = []
    for path, field in BY_PATH.items():
        _, name = path.split(".")
        choices = CHOICES.get(path, ())
        options = list(choices.items()) if isinstance(choices, dict) else [(value, _label(value)) for value in choices]
        fields.append({"path": path, "label": LABELS.get(path, _label(name)), "kind": field.kind,
                       "help": HELP.get(path, ""), "options": options, "low": field.low, "high": field.high})
    fields.append({"path": MINIMUMS, "label": LABELS[MINIMUMS], "kind": "bool",
                   "help": HELP[MINIMUMS], "options": []})
    return {"pages": PAGES, "fields": fields, "visibility": VISIBILITY, "pairs": PAIR_LABELS,
            "minimums": [config.town_hall_minimums(level) for level in range(1, config.MAX_TOWN_HALL + 1)],
            "castle_levels": [str(c.level) for c in CASTLES]}


def values_for(settings: config.Config) -> dict:
    return {**form_values(settings), MINIMUMS: settings.search.minimums_by_hand}


def apply(settings: config.Config, changes: dict[str, Any], serial_override: str | None) -> None:
    """Validate just the submitted changes, with the current settings as context."""
    updates = dict(changes)
    minimums = updates.pop(MINIMUMS, settings.search.minimums_by_hand)
    if type(minimums) is not bool:
        raise ValueError("Use these minimums must be on or off")
    for path, value in updates.items():
        field = BY_PATH.get(path)
        if field is None:
            raise ValueError(f"Unknown setting {path}")
        if path in ("device.mode", "device.serial") and serial_override is not None:
            raise ValueError("Device selection is set by the terminal’s --serial option")
        if not _valid_value(field.kind, value):
            raise ValueError(f"Invalid value for {LABELS.get(path, _label(path.split('.')[1]))}")
        choices = CHOICES.get(path)
        if field.kind == "text" and choices and value not in choices:
            raise ValueError(f"Choose a listed value for {LABELS.get(path, _label(path.split('.')[1]))}")
    # Desktop validation expects both sides of related settings, even if the
    # browser submits only the fields edited on one page.
    _, errors = validate({**form_values(settings), **updates})
    if errors:
        path, error = next(iter(errors.items()))
        raise ValueError(f"{LABELS.get(path, _label(path.split('.')[1]))}: {error}")
    apply_form(settings, updates)
    settings.search.minimums_by_hand = minimums


def _valid_value(kind: str, value: Any) -> bool:
    if kind == "bool":
        return type(value) is bool
    if kind == "hours":
        return isinstance(value, list) and all(type(hour) is int for hour in value)
    if kind in LISTS:
        return isinstance(value, list) and all(isinstance(item, str) for item in value)
    if kind == "presets":
        return isinstance(value, dict) and all(isinstance(names, str) for names in value.values())
    if isinstance(value, str):
        return re.search(r"[\x00-\x1f]", value) is None
    return kind != "text" and type(value) in (int, float)
