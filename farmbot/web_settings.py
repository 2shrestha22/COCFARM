"""Browser editors for the shared farm settings model."""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path
from typing import Any

from farmbot import config, gamedata, townhall, upgradable
from farmbot.accounts import Profiles
from farmbot.castle import CASTLES
from farmbot.form import BY_PATH, apply_form, form_values, validate
from farmbot.human import HABITS
from farmbot.tasks.row_names import HOME_BUILDINGS, HOME_EQUIPMENT, HOME_RESEARCH, PICKS
from farmbot.units import SIEGE_MACHINES, SPELLS, TROOPS
from farmbot.web_layout import DEPENDENCIES, PAIR_LABELS, PAGES, VISIBILITY

MINIMUMS = "search.minimums_by_hand"

LABELS = {
    "attack.ability_health": "Or when health drops to",
    "attack.ability_max_wait": "At the latest after",
    "attack.end_at_loot_share": "Leave at this loot share",
    "attack.end_when_full": "End battle at full storage",
    "attack.end_when_no_loot": "Leave when the loot stops",
    "attack.funnel": "Clear buildings beside the entry",
    "attack.hero_abilities": "Use hero abilities",
    "attack.hero_ability_delay": "Ability after",
    "attack.hero_walk": "Hero walk",
    "attack.league_bonus": "League bonus farming",
    "attack.league_bonus_damage": "Leave at this damage",
    "attack.no_loot_seconds": "No loot for",
    "attack.placement": "Troop placement",
    "attack.quake_aim": "Earthquake timing",
    "attack.quakes_per_spot": "Earthquakes per target",
    "attack.sides": "Deploy from",
    "attack.speed_up": "Play battles at 4x",
    "attack.spell_placement": "Placement for other spells",
    "attack.spell_spot": "Spell target",
    "attack.spells": "Spells to cast",
    "attack.star_bonus": "Earn the daily Star Bonus",
    "attack.super_troops": "Activate super troops",
    "attack.troop_speed": "Troop speed",
    "attack.use_siege": "Use siege machines",
    "attack.walk_fox": "Her Spirit Fox",
    "attack.walk_invisibility_health": "Invisibility from health",
    "attack.walk_spear_early": "Rocket Spear ability at once",
    "attack.walk_time": "The army follows at most after",
    "attack.wave_speed": "Wave speed",
    "attack.waves": "Waves",
    "bot.auto_first": "First village",
    "bot.check_updates": "Check for updates automatically",
    "bot.clear_gravestones": "Clear gravestones",
    "bot.collect_dark": "Dark",
    "bot.collect_elixir": "Elixir",
    "bot.collect_every": "Collection interval",
    "bot.collect_gold": "Gold",
    "bot.collect_ice": "Ice",
    "bot.collect_loot_cart": "Collect the loot cart",
    "bot.collect_resources": "Collect resources",
    "bot.collect_treasury": "Collect the Clan Castle treasury",
    "bot.mode": "Village",
    "bot.read_village": "Read the village data once a day",
    "bot.stop_when_full": "When these storages are full",
    "bot.theme": "Theme",
    "bot.use_snacks": "Use snacks and potions",
    "builder.ability_batch": "Cards per tap",
    "builder.ability_delay": "Between taps",
    "builder.clock_tower": "Use the Clock Tower's free boost",
    "builder.collect_cart": "Collect the elixir cart",
    "builder.collect_minutes": "Collection interval",
    "builder.collect_resources": "Collect resources on both bases",
    "builder.corner": "Go in from",
    "builder.first_hero": "First hero",
    "builder.hero_ability": "Hero ability",
    "builder.hero_ability_after": "Fallback ability delay",
    "builder.return_home_after": "Sail home when the bot stops",
    "builder.second_base": "Attack the second base too",
    "builder.speed_up": "Play at 4x speed",
    "builder.stage_delay": "Wait before the second base",
    "builder.switch_below": "Switch below",
    "builder.switch_hero": "Switch hero when hurt",
    "builder.troop_abilities": "Troop abilities",
    "builder.troop_delay": "Troops follow after",
    "builder.troop_speed": "Troop speed",
    "builder.upgrade": "Upgrade when storage is full",
    "builder.upgrade_first": "Buildings: this kind first",
    "builder.upgrade_order": "What to upgrade first",
    "builder.use_hero": "Hero goes first",
    "builder.walls": "Upgrade walls with spare loot",
    "builder.walls_keep_elixir": "Keep this much elixir",
    "builder.walls_keep_gold": "Keep this much gold",
    "builder.walls_use": "Pay with",
    "capital.district_order": "Which district first",
    "capital.fortress_heal_at": "Heal Flying Fortresses at",
    "capital.heal_lead": "Lead the fortresses' heal by",
    "capital.late_heal": "Late heal for Flying Fortresses",
    "capital.lightning_near_drop": "Lightning near the troops",
    "capital.miner_heal_at": "Heal Super Miners at",
    "capital.raid": "Play Raid Weekend",
    "capital.spells_near_drop": "Skeleton spell near the troops",
    "clan.donate": "Donate to requests",
    "clan.donate_fill": "Fill the rest",
    "clan.donate_main": "Main troops",
    "clan.donate_presets": "Armies by Clan Castle level",
    "clan.donate_siege": "Siege machines",
    "clan.donate_spells": "Main spells",
    "clan.empty_castle": "Empty the Clan Castle to request again",
    "clan.request_every_minutes": "Fallback request interval",
    "clan.request_troops": "Request Clan Castle troops",
    "clan_games.clear_out": "Clear out challenges it can't do",
    "clan_games.enabled": "Play the Clan Games",
    "clan_games.fight_on": "Fight on for the challenge",
    "clan_games.goal": "Play up to",
    "clan_games.rewards": "Pick the rewards",
    "clan_games.stuck_after": "Trash a stuck challenge after",
    "clan_games.trade_in": "Trade in a challenge it can't do",
    "device.adb_path": "ADB path",
    "device.bluestacks_instance": "BlueStacks instance",
    "device.enable_adb": "Turn on ADB",
    "device.launch_emulator": "Open the emulator automatically",
    "device.ldplayer": "LDPlayer version",
    "device.ldplayer_index": "LDPlayer instance number",
    "device.manual_dpi": "Display density",
    "device.manual_height": "Display height",
    "device.manual_width": "Display width",
    "device.mode": "Emulator",
    "device.mumu_index": "MuMu instance number",
    "device.mute": "Keep the emulator muted",
    "device.rooted_adb": "Use rooted ADB for gestures",
    "device.serial": "ADB serial or address",
    "human.enabled": "Play like a person",
    "notify.alert_cooldown_minutes": "Same alert at most every",
    "notify.daily_summary": "Daily summary",
    "notify.discord_webhook": "Discord webhook",
    "notify.on_critical_error": "When a round fails",
    "notify.on_deploy_failed": "When troops won't deploy",
    "notify.on_emulator_restart": "When the emulator is restarted",
    "notify.on_raids": "After Clan Capital raids",
    "notify.on_stopped": "When the bot stops",
    "notify.on_storage_full": "When storage is full",
    "notify.progress_every": "Progress update every",
    "ranked.enabled": "Make the day's ranked attacks",
    "redline.enabled": "Follow the red line",
    "schedule.breaks": "Take breaks",
    "schedule.day_off_every": "A day off about every",
    "schedule.enabled": "Only play at certain hours",
    "search.maintain_only": "Attack bases",
    "search.match_any": "Match any loot minimum",
    "search.max_searches": "Search limit",
    "search.min_dark": "Minimum dark elixir",
    "search.min_elixir": "Minimum elixir",
    "search.min_gold": "Minimum gold",
    "search.min_own_gold_share": "Don't search while my gold is below",
    "search.minimums_by_hand": "Suggested amounts",
    "search.sound_on_match": "Sound on match",
    "upgrade.apprentice": "Put the Builder's Apprentice to work",
    "upgrade.enabled": "Upgrade automatically",
    "upgrade.equipment_only": "Only this equipment",
    "upgrade.first": "Buildings: this kind first",
    "upgrade.lab_assistant": "Put the Lab Assistant to work",
    "upgrade.new_buildings": "Build new buildings",
    "upgrade.only": "Only these buildings",
    "upgrade.order": "What to upgrade first",
    "upgrade.pause_when_idle": "Pause when there's nothing left to upgrade",
    "upgrade.research_only": "Only this research",
    "upgrade.town_hall": "Upgrade the Town Hall",
    "upgrade.wait_for_town_hall": "Rest while the Town Hall upgrades",
    "upgrade.wake_up": "Close COCFARM between upgrades",
    "walls.enabled": "Upgrade walls with spare loot",
    "walls.keep_elixir": "Keep this much elixir",
    "walls.keep_gold": "Keep this much gold",
    "walls.only_when_full": "Only when storage is full",
    "walls.use": "Pay with",
    "war.enabled": "Make your war attacks",
    "war.max_stars": "Maximum stars already taken",
    "war.target": "Target priority",
    "zone.enabled": "Otherwise go around the buildings",
    **{f"human.{habit.key}": habit.title for habit in HABITS},
    "builder.upgrade_builders": "Builders to use",
    "upgrade.builders": "Builders to use",
    "storage.read": "Read capacities automatically",
    "storage.gold": "Gold capacity",
    "storage.elixir": "Elixir capacity",
    "storage.dark": "Dark elixir capacity",
    "storage.builder_read": "Read capacities automatically",
    "storage.builder_gold": "Gold capacity",
    "storage.builder_elixir": "Elixir capacity",
}

HELP = {
    "attack.ability_health": "0% uses the time delay instead.",
    "attack.ability_max_wait": "Fires the ability even if the health threshold hasn't been reached.",
    "attack.end_at_loot_share": "0% disables this threshold.",
    "attack.end_when_full": "Uses the selected resources, or all storages if none are selected.",
    "attack.funnel": "Sends troops or heroes ahead of the main army to clear the sides of the entry.",
    "attack.hero_walk": "The hero goes in first. Invisibility Spells protect her when hurt.",
    "attack.league_bonus": "Skips loot minimums and deploys the army at once. Star Bonus battles still prioritize stars.",
    "attack.league_bonus_damage": "70% damage earns the full league bonus.",
    "attack.placement": "Spread uses the sides selected above. Toward the loot aims at visible loot buildings. "
                        "Earthquakes set to Before troops can override either choice.",
    "attack.quake_aim": "With enough Earthquakes ready at the start, Before troops opens one entry in farming "
                        "battles and sends the army in behind it. After troops targets the base interior.",
    "attack.quakes_per_spot": "Four Earthquakes on a wall open it.",
    "attack.spell_placement": "Applies to spells such as Bats and Rage.",
    "attack.spell_spot": "Used for One spot and for the first Earthquake group cast after troops. "
                         "When farming, Random picks a new spot near the center each battle.",
    "attack.spells": "Hero walks handle Invisibility Spells separately.",
    "attack.star_bonus": "Battles prioritize stars until the daily bonus is earned.",
    "attack.super_troops": "Costs 25,000 dark elixir per boost.",
    "attack.use_siege": "Turning this off also holds back Clan Castle troops.",
    "attack.walk_time": "The army follows sooner if the hero falls.",
    "attack.waves": "Splits each troop type into this many groups.",
    "bot.check_updates": "Used by the desktop app.",
    "bot.collect_every": "Also collects on the first round.",
    "bot.collect_treasury": "May need your clan badge under Advanced → Pictures to find the castle.",
    "bot.mode": "Auto switch changes villages when the selected storages are full.",
    "bot.read_village": "Uses the game's Data Export. Village data is saved with the profile.",
    "bot.stop_when_full": "Stops when all selected resources are full in every farmed village. Leave empty to disable outside Auto switch.",
    "builder.collect_minutes": "0 collects before each battle. Also collects on the first round.",
    "builder.corner": "Auto picks the corner farthest from enemy buildings.",
    "builder.first_hero": "Keep uses the hero selected in the game.",
    "builder.hero_ability_after": "Counts from landing when the charge bars can't be read.",
    "builder.second_base": "Turning this off forfeits the second base's stars.",
    "builder.walls": "Starts with the cheapest walls and spends spare loot.",
    "capital.fortress_heal_at": "Triggers when one fortress drops below this health.",
    "capital.heal_lead": "0 aims at the fortresses' current position.",
    "capital.late_heal": "After 45 s, uses a spare heal on the first fortress below 85%.",
    "capital.lightning_near_drop": "Off targets the densest group of buildings in view.",
    "capital.miner_heal_at": "Triggers the first heal early when a miner drops below this health.",
    "capital.raid": "Friday to Monday, 07:00 UTC. Uses the army set in the game.",
    "capital.spells_near_drop": "Off targets the densest group of buildings in view.",
    "clan.donate": "Uses elixir or dark elixir.",
    "clan.donate_fill": "Fills leftover space with the largest units that fit.",
    "clan.donate_presets": "Enter comma-separated units. A count like 1 Super Yeti limits the quantity.",
    "clan.empty_castle": "Discards troops, spells, and siege machines once a free request is available.",
    "clan.request_every_minutes": "Used when the game timer can't be read.",
    "clan_games.clear_out": "Requires Trade in. Replacing a challenge triggers a 10-minute cooldown.",
    "clan_games.enabled": "Picks challenges the bot can complete in normal rounds.",
    "clan_games.fight_on": "Keeps attacking for the challenge after loot runs out or storage fills.",
    "clan_games.goal": "4,000 unlocks the bonus reward. 10,000 is the maximum.",
    "clan_games.rewards": "Picks magic items first, then gems.",
    "clan_games.stuck_after": "Requires Trade in. Replacing a challenge triggers a 10-minute cooldown.",
    "clan_games.trade_in": "Replaces an unsupported challenge. Triggers a 10-minute cooldown.",
    "device.adb_path": "Use the full path or adb on PATH. For USB, use Android Platform-Tools.",
    "device.bluestacks_instance": "Leave blank for the main instance.",
    "device.enable_adb": "Restarts the emulator if ADB needs to be enabled.",
    "device.ldplayer": "Requires LDPlayer 9 or later. Leave blank for the newest installed.",
    "device.ldplayer_index": "1 is the first instance.",
    "device.mode": "ADB device supports USB and TCP connections.",
    "device.mumu_index": "1 is the first instance.",
    "device.rooted_adb": "Requires a device that supports rooted debugging.",
    "device.serial": "Leave blank for one device. Otherwise enter a serial or host:port.",
    "human.enabled": "Off disables every habit.",
    "human.tap_hold": "Holds each tap for 40–140 ms.",
    "human.curved_swipes": "Uses a straight swipe if the device can't draw a curve.",
    "human.fatigue": "Waits grow up to 25% longer after an hour. Breaks reset the timing.",
    "human.odd_hours": "Starts 5–25 minutes late and stops 5–25 minutes early.",
    "human.offline_breaks": "Closes the game during breaks, outside playing hours, and at the daily attack limit.",
    "human.uneven_days": "Scales attack limits and break frequency by 0.6–1.2 each day.",
    "human.distracted": "Adds 10–60 seconds roughly once every 25 rounds.",
    "human.browse": "Looks around the game every 8–20 rounds.",
    "human.end_spread": "Varies the loot and no-loot thresholds.",
    "human.near_misses": "Sometimes accepts or skips bases within 5% of the loot minimums.",
    "human.few_sides": "Uses one or two sides in about a third of battles.",
    "human.hold_deploy": "Requires readable troop counts. Applies to cards with 8 or more units.",
    "notify.alert_cooldown_minutes": "Groups repeat alerts during this interval.",
    "notify.daily_summary": "Sends yesterday's totals after midnight.",
    "notify.discord_webhook": "Paste a URL from Discord Server Settings → Integrations → Webhooks.",
    "notify.on_deploy_failed": "Sends after all deployment retries fail.",
    "notify.progress_every": "0 turns off progress updates.",
    "ranked.enabled": "Join the tournament in the game. Battles prioritize stars.",
    "schedule.day_off_every": "0 disables days off.",
    "schedule.enabled": "Uses the dashboard server's local time.",
    "search.maintain_only": "Turn off to run village chores only.",
    "search.match_any": "Off requires every selected minimum.",
    "search.max_searches": "Returns to the village when this limit is reached.",
    "search.min_dark": "0 disables this minimum.",
    "search.min_elixir": "0 disables this minimum.",
    "search.min_gold": "0 disables this minimum.",
    "search.min_own_gold_share": "0% disables this limit.",
    "search.minimums_by_hand": "Uses Town Hall recommendations until you edit a minimum.",
    "upgrade.apprentice": "Assigns the longest remaining building upgrade.",
    "upgrade.lab_assistant": "Assigns the longest remaining research.",
    "upgrade.new_buildings": "Places them where the game suggests.",
    "upgrade.pause_when_idle": "Closes the game until an upgrade finishes. Requires village data.",
    "upgrade.town_hall": "Prioritizes the Town Hall when gold is full and prerequisites are met.",
    "upgrade.wait_for_town_hall": "Closes the game when storage is full and upgrades are exhausted. Checks every 2 hours.",
    "upgrade.wake_up": "Applies to the Windows desktop app.",
    "walls.enabled": "Starts with the cheapest walls and spends spare loot.",
    "walls.keep_gold": "Also reserves enough gold to keep searching.",
    "war.enabled": "Uses the army set in the game and prioritizes stars.",
    "war.max_stars": "3 allows any base.",
    "war.target": "Most stars estimates additional stars and ignores the star limit.",
    "zone.enabled": "Off uses fixed lines at the map edges when there is no red line.",
    "upgrade.enabled": "Spends loot at full storage or at the configured threshold.",
    "builder.upgrade": "Spends loot on the most expensive available upgrades.",
    "upgrade.order": "Walls come last by default. Drag or use the arrows to reorder.",
    "builder.upgrade_order": "Walls come last by default. Drag or use the arrows to reorder.",
    "upgrade.first": "Disabled when a custom building list is set.",
    "upgrade.only": "Pick and order buildings. Leave empty to allow any.",
    "upgrade.research_only": "Pick and order research. Leave empty to allow any.",
    "upgrade.equipment_only": "Upgrades up to 3 per round. Requires the Blacksmith and Windows text recognition.",
    "storage.read": "Measures capacity once a day.",
    "storage.builder_read": "Measures capacity once a day.",
    "upgrade.builders": "Defaults to all but one. A free builder can upgrade walls.",
    "builder.upgrade_builders": "Defaults to all but one. A free builder can upgrade walls.",
}

CONTROLS = {
    "attack.funnel": "segments",
    "attack.hero_walk": "segments",
    "attack.placement": "segments",
    "attack.quake_aim": "segments",
    "attack.spell_placement": "segments",
    "attack.spell_spot": "segments",
    "attack.spells": "segments",
    "attack.troop_speed": "speed",
    "attack.walk_fox": "segments",
    "attack.wave_speed": "speed",
    "attack.waves": "segments",
    "bot.auto_first": "segments",
    "bot.mode": "segments",
    "bot.theme": "segments",
    "builder.corner": "segments",
    "builder.first_hero": "segments",
    "builder.troop_speed": "speed",
    "builder.upgrade_first": "segments",
    "builder.walls_use": "segments",
    "capital.district_order": "segments",
    "clan_games.goal": "segments",
    "clan_games.stuck_after": "segments",
    "device.mode": "segments",
    "upgrade.first": "segments",
    "walls.use": "segments",
    "war.max_stars": "stars",
    "war.target": "segments",
    "device.bluestacks_instance": "editable_choice",
    "device.ldplayer": "editable_choice",
    "upgrade.builders": "builders",
    "builder.upgrade_builders": "builders",
}

SHARES = {
    "search.min_own_gold_share": ("storage.gold", "gold"),
    "walls.keep_gold": ("storage.gold", "gold"),
    "walls.keep_elixir": ("storage.elixir", "elixir"),
    "builder.walls_keep_gold": ("storage.builder_gold", "gold"),
    "builder.walls_keep_elixir": ("storage.builder_elixir", "elixir"),
}

PRIORITIES = {
    "upgrade.order": {
        "pets": ("upgrade.pets", "Pets", "Dark elixir"),
        "hero": ("upgrade.heroes", "Heroes", "Elixir, dark elixir"),
        "research": ("upgrade.lab", "Research", "Elixir, dark elixir"),
        "equipment": ("upgrade.equipment", "Hero equipment", "Ore"),
        "building": ("upgrade.buildings", "Buildings", "Gold, elixir, dark elixir"),
        "walls": ("walls.enabled", "Walls", "Gold, elixir"),
    },
    "builder.upgrade_order": {
        "research": ("builder.upgrade_lab", "Research", "Elixir"),
        "hero": ("builder.upgrade_heroes", "Heroes", "Elixir"),
        "building": ("builder.upgrade_buildings", "Buildings", "Gold, elixir"),
        "walls": ("builder.walls", "Walls", "Gold, elixir"),
    },
}

PICK_GROUPS = {
    "upgrade.only": HOME_BUILDINGS,
    "upgrade.research_only": HOME_RESEARCH,
    "upgrade.equipment_only": HOME_EQUIPMENT,
}

UNITS = {
    "attack.ability_health": "%",
    "attack.ability_max_wait": "s",
    "attack.end_at_loot_share": "%",
    "attack.hero_ability_delay": "s",
    "attack.league_bonus_damage": "%",
    "attack.no_loot_seconds": "s",
    "attack.walk_invisibility_health": "%",
    "attack.walk_time": "s",
    "bot.collect_every": "rounds",
    "builder.ability_delay": "s",
    "builder.collect_minutes": "min",
    "builder.hero_ability_after": "s",
    "builder.stage_delay": "s",
    "builder.switch_below": "%",
    "builder.troop_delay": "s",
    "capital.fortress_heal_at": "%",
    "capital.heal_lead": "s",
    "capital.miner_heal_at": "%",
    "clan.request_every_minutes": "min",
    "device.manual_dpi": "DPI",
    "device.manual_height": "px",
    "device.manual_width": "px",
    "schedule.day_off_every": "days",
    "search.max_searches": "bases",
}

CHOICES = {
    "device.mode": {"bluestacks": "BlueStacks", "ldplayer": "LDPlayer", "mumu": "MuMu", "manual": "ADB device"},
    "bot.mode": {"home": "Home village", "builder": "Builder base", "auto": "Auto switch"},
    "bot.auto_first": {"home": "Home village", "builder": "Builder base"},
    "bot.theme": {"auto": "System", "light": "Light", "dark": "Dark"},
    "attack.placement": {"spread": "Spread", "loot": "Toward the loot"},
    "attack.spell_placement": {"together": "One spot", "spread": "Across the base"},
    "attack.spells": {"bat": "Bats only", "earthquake": "Bats + Earthquakes", "all": "All spells"},
    "attack.spell_spot": {"middle": "Center", "random": "Random"},
    "attack.quake_aim": {"path": "Before troops", "spots": "After troops"},
    "attack.funnel": {"off": "Off", "troops": "Troops", "heroes": "Heroes"},
    "attack.hero_walk": config.HERO_WALKS,
    "attack.walk_fox": {"off": "None", "1-4": "1-4", "5-9": "5-9", "10": "10"},
    "builder.corner": config.BUILDER_CORNERS,
    "builder.first_hero": {"any": "Keep", "machine": "Battle Machine", "copter": "Battle Copter"},
    "builder.walls_use": {"gold": "Gold", "elixir": "Elixir", "both": "Either"},
    "walls.use": {"gold": "Gold", "elixir": "Elixir", "both": "Either"},
    "builder.upgrade_first": {"none": "Any", "defense": "Defenses", "resource": "Resources", "army": "Army"},
    "upgrade.first": {"none": "Any", "defense": "Defenses", "resource": "Resources", "army": "Army"},
    "war.target": {"mirror": "Recommended", "bottom": "Bottom", "gain": "Most stars"},
    "capital.district_order": {"destroyed": "Most destroyed", "stars": "Most stars"},
    "clan_games.goal": {"4000": "4,000", "10000": "10,000"},
    "clan_games.stuck_after": {"0": "Never", "3": "3 battles", "5": "5 battles"},
    "attack.sides": {"nw": "Top left", "ne": "Top right", "sw": "Bottom left", "se": "Bottom right"},
    "attack.waves": {wave: str(wave) for wave in (1, 2, 3)},
    "bot.stop_when_full": {"gold": "Gold", "elixir": "Elixir", "dark": "Dark"},
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
    dependencies: dict[str, list[tuple]] = {}
    for controller, allowed, names in DEPENDENCIES:
        for path in names.split():
            dependencies.setdefault(path, []).append((controller, allowed))
    fields = []
    for path, field in BY_PATH.items():
        _, name = path.split(".")
        choices = CHOICES.get(path, ())
        options = list(choices.items()) if isinstance(choices, dict) else [(value, _label(value)) for value in choices]
        fields.append({"path": path, "label": LABELS.get(path, _label(name)), "kind": field.kind,
                       "help": HELP.get(path, ""), "options": options, "low": field.low, "high": field.high,
                       "control": CONTROLS.get(path), "unit": UNITS.get(path)})
    fields.append({"path": MINIMUMS, "label": LABELS[MINIMUMS], "kind": "bool",
                   "help": HELP[MINIMUMS], "options": []})
    return {"pages": PAGES, "fields": fields, "visibility": VISIBILITY, "pairs": PAIR_LABELS,
            "dependencies": dependencies, "shares": SHARES, "priorities": PRIORITIES, "pick_groups": PICK_GROUPS,
            "minimums": [config.town_hall_minimums(level) for level in range(1, config.MAX_TOWN_HALL + 1)],
            "castles": [{"level": str(c.level), "troops": c.troops, "spells": c.spells,
                         "siege": c.siege, "lab_cap": c.lab_cap} for c in CASTLES]}


def values_for(settings: config.Config) -> dict:
    return {**form_values(settings), MINIMUMS: settings.search.minimums_by_hand}


def village_controls(path: Path, profiles: Profiles, active: str) -> dict:
    """The same exported village data the desktop's sliders and pickers use."""
    village_file = profiles.village_path(active) if active else path.parent / townhall.VILLAGE_FILE
    village = townhall.load(village_file)
    if village is None:
        return {"builders": {}, "pick_state": {}}
    kept = upgradable.path_for(village_file)
    research = upgradable.item_levels(village, "research", PICKS["research"])
    equipment = upgradable.item_levels(village, "equipment", PICKS["equipment"])
    return {
        "builders": {"upgrade.builders": village.builders, "builder.upgrade_builders": village.builder_base_builders},
        "pick_state": {
            "upgrade.only": {"done": sorted(upgradable.done(kept, village, "buildings", PICKS["buildings"]))},
            "upgrade.research_only": {"available": list(research), "levels": research,
                                      "done": sorted(upgradable.done(kept, village, "research", PICKS["research"]))},
            "upgrade.equipment_only": {"available": sorted(upgradable.owned_equipment(village, HOME_EQUIPMENT) or ()),
                                       "levels": equipment, "max": {name: gamedata.equipment_max(name) for name in equipment},
                                       "done": sorted(upgradable.maxed_equipment(equipment))},
        },
    }


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
