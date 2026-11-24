"""The desktop window's navigation and card order for the browser."""

from __future__ import annotations

from farmbot.human import HABITS


def fields(section: str, names: str) -> tuple[str, ...]:
    return tuple(f"{section}.{name}" for name in names.split())


def group(title: str, *settings: str | tuple[str, ...] | dict, help_text: str = "",
          when: tuple[str, tuple[str, ...]] | None = None) -> dict:
    return {"title": title, "fields": settings, "help": help_text, "when": when}


def fold(title: str, *settings: str | dict, help_text: str = "") -> dict:
    return {"fold": title, "help": help_text, "fields": settings}


def action(name: str, *paths: str) -> dict:
    return {"action": name, "fields": paths}


def storages(prefix: str, resources: str) -> dict:
    read = f"storage.{prefix}read"
    amounts = tuple(f"storage.{prefix}{kind}" for kind in resources.split())
    return group("Storages", read, fold("Storage capacities", *amounts, action("read_storages", read, *amounts),
                                      help_text="Manual edits turn off automatic readings."))


def tab(key: str, label: str, *groups: dict) -> dict:
    return {"key": key, "label": label, "groups": groups, "intro": ""}


def page(key: str, title: str, *tabs: dict) -> dict:
    return {"key": key, "title": title, "subtitle": "", "tabs": tabs}


PAGES = (
    page("dashboard", "Dashboard",
         tab("dashboard", "", group("What to farm", *fields("bot", "mode auto_first")),
             group("When to stop", "bot.stop_when_full", when=("bot.mode", ("auto",))))),
    page("home_village", "Home village",
         tab("bases", "Bases to attack",
             group("Bases to attack", *fields("search", "maintain_only min_gold min_elixir min_dark minimums_by_hand match_any")),
             group("While searching", *fields("search", "min_own_gold_share max_searches sound_on_match"))),
         tab("attacking", "Attacking",
             group("Deploying", *fields("attack", "sides placement"),
                   fold("Deployment path", "redline.enabled", "zone.enabled"),
                   "attack.waves", fold("Deploy speeds", *fields("attack", "troop_speed wave_speed"))),
             group("Ending the battle", *fields("attack", "end_when_full speed_up league_bonus league_bonus_damage star_bonus end_when_no_loot"),
                   fold("Early exit thresholds", *fields("attack", "no_loot_seconds end_at_loot_share")))),
         tab("army", "Army",
             group("Troops, heroes and siege machines", *fields("attack", "super_troops use_siege hero_abilities"),
                   fold("Ability timing", *fields("attack", "hero_ability_delay ability_health ability_max_wait")),
                   "attack.hero_walk", fold("Walk timing",
                                           *fields("attack", "walk_time walk_invisibility_health walk_fox walk_spear_early"))),
             group("Spells", *fields("attack", "spells quakes_per_spot quake_aim funnel spell_placement spell_spot"))),
         tab("village", "Village",
             group("Collecting", *fields("bot", "collect_resources"),
                   fields("bot", "collect_gold collect_elixir collect_dark collect_ice"),
                   *fields("bot", "collect_every collect_loot_cart use_snacks clear_gravestones collect_treasury")),
             storages("", "gold elixir dark"),
             group("Village data", "bot.read_village")),
         tab("upgrades", "Upgrades",
             group("Upgrades", "upgrade.enabled", fields("upgrade", "start_gold start_elixir start_dark"),
                   *fields("upgrade", "order first only research_only equipment_only new_buildings town_hall"),
                   fold("Helpers and downtime",
                        *fields("upgrade", "wait_for_town_hall wake_up pause_when_idle apprentice lab_assistant")), "upgrade.builders"),
             group("Walls", *fields("walls", "enabled use keep_gold keep_elixir only_when_full"))),
         tab("clan", "Clan",
             group("Donations", *fields("clan", "donate donate_main donate_siege donate_spells donate_presets donate_fill")),
             group("Requests", *fields("clan", "request_troops request_every_minutes empty_castle")),
             group("Clan Games", *fields("clan_games", "enabled goal trade_in clear_out stuck_after fight_on rewards")))),
    page("builder_base", "Builder base",
         tab("attacking", "Attacking",
             group("Deploying", *fields("builder", "corner use_hero first_hero"),
                   fold("Hero swap and troop timing",
                        *fields("builder", "switch_hero switch_below troop_delay troop_speed"))),
             group("Abilities", *fields("builder", "hero_ability troop_abilities"),
                   fold("Ability timing",
                        *fields("builder", "hero_ability_after ability_delay ability_batch"))),
             group("Battle", *fields("builder", "speed_up return_home_after second_base stage_delay"))),
         tab("village", "Village",
             group("Collecting", *fields("builder", "collect_resources collect_minutes collect_cart"),
                   fields("builder", "cart_every_min cart_every_max"), "builder.clock_tower"),
             storages("builder_", "gold elixir")),
         tab("upgrades", "Upgrades",
             group("Upgrades", *fields("builder", "upgrade upgrade_order upgrade_first upgrade_builders")),
             group("Walls", *fields("builder", "walls walls_use walls_keep_gold walls_keep_elixir")))),
    page("wars_and_raids", "Wars & raids",
         tab("wars", "Clan wars", group("Clan wars", *fields("war", "enabled target max_stars"))),
         tab("raids", "Raid Weekend", group("Clan Capital raids",
             *fields("capital", "raid miner_heal_at fortress_heal_at district_order late_heal heal_lead spells_near_drop lightning_near_drop"))),
         tab("ranked", "Ranked", group("Ranked battles", "ranked.enabled"))),
    page("when_to_play", "When to play",
         tab("schedule", "",
             group("Playing hours", *fields("schedule", "enabled active_hours")),
             group("Breaks", "schedule.breaks", fields("schedule", "break_every_min break_every_max"),
                   fields("schedule", "break_minutes_min break_minutes_max"), "schedule.day_off_every"),
             group("When to stop", "bot.stop_when_full", fields("schedule", "daily_attacks_min daily_attacks_max")))),
    page("like_a_person", "Like a person",
         tab("person", "Overview", group("Like a person", "human.enabled")),
         *(tab(key, label, group(title, *(f"human.{habit.key}" for habit in HABITS if habit.group == key)))
           for key, label, title in (("touch", "Taps & swipes", "Taps, waits and swipes"),
                                      ("village", "Village habits", "Village"), ("battle", "Battle habits", "Battles")))),
    page("history", "History"),
    page("advanced", "Advanced",
         tab("settings", "Emulator",
             group("Emulator", *fields("device", "mode bluestacks_instance launch_emulator"), action("connection"),
                   *fields("device", "ldplayer ldplayer_index mumu_index serial"),
                   fold("ADB and sound",
                        *fields("device", "enable_adb mute adb_path"))),
             group("Custom device", *fields("device", "manual_width manual_height manual_dpi rooted_adb"), action("display"),
                   when=("device.mode", ("manual",)))),
         tab("app", "App", group("Appearance", "bot.theme"), group("Updates", "bot.check_updates")),
         tab("alerts", "Alerts", group("Discord",
             *fields("notify", "discord_webhook on_storage_full on_stopped on_emulator_restart daily_summary on_raids progress_every on_critical_error on_deploy_failed alert_cooldown_minutes"))),
         tab("report", "Bug report"),
         tab("pictures", "Pictures")),
    page("farms", "Farms"),
)


PAIR_LABELS = {
    "upgrade.start_gold": ("Upgrade thresholds", "Leave blank to wait for full storage.", ""),
    "builder.cart_every_min": ("Collection interval", "Random within this range.", "battles"),
    "schedule.break_every_min": ("Break interval", "Random within this range.", "attacks"),
    "schedule.break_minutes_min": ("Break duration", "Random within this range.", "min"),
    "schedule.daily_attacks_min": ("Attacks per day", "0 to 0 means no limit.", "attacks"),
    "bot.collect_gold": ("Collectors", "", ""),
}


VISIBILITY = {
    "bot.auto_first": ("bot.mode", ("auto",)),
    "device.bluestacks_instance": ("device.mode", ("bluestacks",)),
    "device.ldplayer": ("device.mode", ("ldplayer",)),
    "device.ldplayer_index": ("device.mode", ("ldplayer",)),
    "device.mumu_index": ("device.mode", ("mumu",)),
    "device.serial": ("device.mode", ("manual",)),
    "device.launch_emulator": ("device.mode", ("bluestacks", "ldplayer", "mumu")),
    "device.enable_adb": ("device.mode", ("bluestacks", "ldplayer")),
}


# The desktop form disables these controls while their parent setting is off.
DEPENDENCIES = (
    ("bot.mode", ("auto",), "bot.auto_first"),
    ("search.maintain_only", (False,), "search.min_gold search.min_elixir search.min_dark search.match_any "
     "search.min_own_gold_share search.sound_on_match search.max_searches"),
    ("attack.hero_abilities", (True,), "attack.hero_ability_delay attack.ability_health attack.ability_max_wait"),
    ("attack.hero_walk", ("queen", "champion"), "attack.walk_time attack.walk_invisibility_health attack.walk_fox"),
    ("attack.hero_walk", ("champion",), "attack.walk_spear_early"),
    ("attack.spells", ("earthquake", "all"), "attack.quakes_per_spot attack.quake_aim attack.funnel"),
    ("attack.spell_placement", ("together",), "attack.spell_spot"),
    ("attack.league_bonus", (True,), "attack.league_bonus_damage"),
    ("attack.end_when_no_loot", (True,), "attack.no_loot_seconds"),
    ("bot.collect_resources", (True,), "bot.collect_gold bot.collect_elixir bot.collect_dark bot.collect_ice "
     "bot.collect_every"),
    ("upgrade.enabled", (True,), "upgrade.start_gold upgrade.start_elixir upgrade.start_dark upgrade.order "
     "upgrade.pets upgrade.heroes upgrade.lab upgrade.buildings upgrade.first "
     "upgrade.only upgrade.research_only upgrade.equipment upgrade.equipment_only "
     "upgrade.new_buildings upgrade.town_hall upgrade.wait_for_town_hall "
     "upgrade.apprentice upgrade.lab_assistant upgrade.builders"),
    ("upgrade.only", ([],), "upgrade.first"),
    ("upgrade.buildings", (True,), "upgrade.only"),
    ("upgrade.lab", (True,), "upgrade.research_only"),
    ("upgrade.equipment", (True,), "upgrade.equipment_only"),
    ("walls.enabled", (True,), "walls.use walls.keep_gold walls.keep_elixir walls.only_when_full"),
    ("clan.donate", (True,), "clan.donate_fill"),
    ("clan.request_troops", (True,), "clan.request_every_minutes clan.empty_castle"),
    ("clan_games.enabled", (True,), "clan_games.goal clan_games.trade_in clan_games.clear_out "
     "clan_games.stuck_after clan_games.fight_on clan_games.rewards"),
    ("war.enabled", (True,), "war.target war.max_stars"),
    ("capital.raid", (True,), "capital.miner_heal_at capital.fortress_heal_at capital.district_order "
     "capital.late_heal capital.heal_lead capital.spells_near_drop "
     "capital.lightning_near_drop"),
    ("builder.use_hero", (True,), "builder.troop_delay builder.first_hero builder.switch_hero"),
    ("builder.switch_hero", (True,), "builder.switch_below"),
    ("builder.hero_ability", (True,), "builder.hero_ability_after"),
    ("builder.troop_abilities", (True,), "builder.ability_delay builder.ability_batch"),
    ("builder.second_base", (True,), "builder.stage_delay"),
    ("builder.collect_resources", (True,), "builder.collect_minutes"),
    ("builder.collect_cart", (True,), "builder.cart_every_min builder.cart_every_max"),
    ("builder.upgrade", (True,), "builder.upgrade_order builder.upgrade_heroes builder.upgrade_lab "
     "builder.upgrade_buildings builder.upgrade_first builder.upgrade_builders"),
    ("builder.walls", (True,), "builder.walls_use builder.walls_keep_gold builder.walls_keep_elixir"),
    ("schedule.enabled", (True,), "schedule.active_hours"),
    ("schedule.breaks", (True,), "schedule.break_every_min schedule.break_minutes_min"),
    ("device.mode", ("bluestacks",), "device.bluestacks_instance"),
    ("device.mode", ("bluestacks", "ldplayer"), "device.enable_adb"),
    ("device.mode", ("ldplayer",), "device.ldplayer device.ldplayer_index"),
    ("device.mode", ("mumu",), "device.mumu_index"),
    ("device.mode", ("manual",), "device.serial"),
    ("search.maintain_only", (False,), "search.minimums_by_hand"),
    ("schedule.breaks", (True,), "schedule.break_every_max schedule.break_minutes_max"),
    ("human.enabled", (True,), " ".join(f"human.{habit.key}" for habit in HABITS)),
)
