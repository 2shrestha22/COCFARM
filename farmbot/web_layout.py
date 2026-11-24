"""The desktop window's navigation and card order for the browser."""

from __future__ import annotations

from farmbot.human import HABITS


def fields(section: str, names: str) -> tuple[str, ...]:
    return tuple(f"{section}.{name}" for name in names.split())


def group(title: str, *settings: str | tuple[str, ...], folded: bool = False, help_text: str = "") -> dict:
    return {"title": title, "fields": settings, "folded": folded, "help": help_text}


def tab(key: str, label: str, *groups: dict, intro: str = "") -> dict:
    return {"key": key, "label": label, "groups": groups, "intro": intro}


def page(key: str, title: str, subtitle: str, *tabs: dict) -> dict:
    return {"key": key, "title": title, "subtitle": subtitle, "tabs": tabs}


PAGES = (
    page("dashboard", "Dashboard", "What COCFARM is doing right now, and what it has earned.",
         tab("dashboard", "", group("What to farm", *fields("bot", "mode auto_first")))),
    page("home_village", "Home village",
         "Everything for farming the home village: which bases to attack, how to attack them, and the chores in between.",
         tab("bases", "Bases to attack",
             group("Bases to attack", *fields("search", "maintain_only min_gold min_elixir min_dark minimums_by_hand match_any")),
             group("While searching", *fields("search", "min_own_gold_share max_searches sound_on_match")),
             intro="Amounts accept 500k, 1.5m or 1,500,000."),
         tab("attacking", "Attacking",
             group("Deploying", *fields("attack", "sides placement")),
             group("Where on a side", "redline.enabled", "zone.enabled", folded=True,
                   help_text="Along the red line, or around the buildings"),
             group("", "attack.waves"),
             group("Deploy speeds", *fields("attack", "troop_speed wave_speed"), folded=True,
                   help_text="How quickly troops and waves go down"),
             group("Ending the battle", *fields("attack", "end_when_full speed_up league_bonus league_bonus_damage star_bonus end_when_no_loot")),
             group("When exactly to leave", *fields("attack", "no_loot_seconds end_at_loot_share"), folded=True,
                   help_text="How long without loot, or how much loot is enough")),
         tab("army", "Army",
             group("Troops, heroes and siege machines", *fields("attack", "super_troops use_siege hero_abilities")),
             group("Ability timing", *fields("attack", "hero_ability_delay ability_health ability_max_wait"), folded=True),
             group("", "attack.hero_walk"),
             group("Walk timing", *fields("attack", "walk_time walk_invisibility_health walk_fox walk_spear_early"), folded=True),
             group("Spells", *fields("attack", "spells quakes_per_spot quake_aim funnel spell_placement spell_spot"))),
         tab("village", "Village",
             group("Collecting", *fields("bot", "collect_resources"),
                   fields("bot", "collect_gold collect_elixir collect_dark collect_ice"),
                   *fields("bot", "collect_every collect_loot_cart use_snacks clear_gravestones collect_treasury")),
             group("Storages", *fields("storage", "read gold elixir dark")),
             group("Village data", "bot.read_village")),
         tab("upgrades", "Upgrades",
             group("Upgrades", *fields("upgrade", "enabled start_gold start_elixir start_dark order pets heroes lab equipment buildings first only research_only equipment_only new_buildings town_hall")),
             group("Helpers and resting", *fields("upgrade", "wait_for_town_hall wake_up pause_when_idle apprentice lab_assistant"), folded=True),
             group("", "upgrade.builders"),
             group("Walls", *fields("walls", "enabled use keep_gold keep_elixir only_when_full")),
             intro="Upgrades and walls, in the order under What to upgrade first (walls last by default)."),
         tab("clan", "Clan",
             group("Donations", *fields("clan", "donate donate_main donate_siege donate_spells donate_presets donate_fill")),
             group("Requests", *fields("clan", "request_troops request_every_minutes empty_castle")),
             group("Clan Games", *fields("clan_games", "enabled goal trade_in clear_out stuck_after fight_on rewards")))),
    page("builder_base", "Builder base", "Builder battles, collecting, upgrades and walls.",
         tab("attacking", "Attacking",
             group("Deploying", *fields("builder", "corner use_hero first_hero")),
             group("Hero swap and troop timing", *fields("builder", "switch_hero switch_below troop_delay troop_speed"), folded=True),
             group("Abilities", *fields("builder", "hero_ability troop_abilities")),
             group("Ability timing", *fields("builder", "hero_ability_after ability_delay ability_batch"), folded=True),
             group("Battle", *fields("builder", "speed_up return_home_after second_base stage_delay"))),
         tab("village", "Village",
             group("Collecting", *fields("builder", "collect_resources collect_minutes collect_cart"),
                   fields("builder", "cart_every_min cart_every_max"), "builder.clock_tower"),
             group("Storages", *fields("storage", "builder_read builder_gold builder_elixir"))),
         tab("upgrades", "Upgrades",
             group("Upgrades", *fields("builder", "upgrade upgrade_order upgrade_lab upgrade_heroes upgrade_buildings upgrade_first upgrade_builders")),
             group("Walls", *fields("builder", "walls walls_use walls_keep_gold walls_keep_elixir")),
             intro="Upgrades and walls, in the order under What to upgrade first (walls last by default).")),
    page("wars_and_raids", "Wars & raids",
         "The battles fought for stars, not loot: clan wars, the Clan Capital’s Raid Weekend and ranked battles. The army trained is used.",
         tab("wars", "Clan wars", group("Clan wars", *fields("war", "enabled target max_stars"))),
         tab("raids", "Raid Weekend", group("Clan Capital raids",
             *fields("capital", "raid miner_heal_at fortress_heal_at district_order late_heal heal_lead spells_near_drop lightning_near_drop"))),
         tab("ranked", "Ranked", group("Ranked battles", "ranked.enabled"))),
    page("when_to_play", "When to play", "The hours it may play, its breaks, and when it stops by itself.",
         tab("schedule", "",
             group("Playing hours", *fields("schedule", "enabled active_hours")),
             group("Breaks", "schedule.breaks", fields("schedule", "break_every_min break_every_max"),
                   fields("schedule", "break_minutes_min break_minutes_max"), "schedule.day_off_every"),
             group("When to stop", "bot.stop_when_full", fields("schedule", "daily_attacks_min daily_attacks_max")))),
    page("like_a_person", "Like a person", "How much like a person it plays.",
         tab("person", "Overview", group("Like a person", "human.enabled"),
             intro="Small habits that make it tap, wait and fight less like a machine."),
         *(tab(key, label, group(title, *(f"human.{habit.key}" for habit in HABITS if habit.group == key)))
           for key, label, title in (("touch", "Taps & swipes", "Taps, waits and swipes"),
                                      ("village", "Village habits", "Village"), ("battle", "Battle habits", "Battles")))),
    page("history", "History", "Every attack COCFARM has made: totals, loot per hour, the last two weeks, and each attack."),
    page("advanced", "Advanced", "Technical settings, alerts on your phone, and the tools for teaching COCFARM new buttons.",
         tab("settings", "Emulator",
             group("Emulator", *fields("device", "mode bluestacks_instance launch_emulator ldplayer ldplayer_index mumu_index serial")),
             group("Custom device", *fields("device", "manual_width manual_height manual_dpi rooted_adb")),
             group("ADB and sound", *fields("device", "enable_adb mute adb_path"), folded=True),
             intro="How COCFARM finds and controls the emulator: set once."),
         tab("app", "App", group("Appearance", "bot.theme"), group("Updates", "bot.check_updates"),
             intro="COCFARM itself: what it sees, how it looks, and its updates."),
         tab("alerts", "Alerts", group("Discord",
             *fields("notify", "discord_webhook on_storage_full on_stopped on_emulator_restart daily_summary on_raids progress_every on_critical_error on_deploy_failed alert_cooldown_minutes"))),
         tab("report", "Bug report"),
         tab("pictures", "Pictures", intro="COCFARM finds buttons by comparing the screen with small pictures of them.")),
    page("farms", "Farms", "The devices and account profiles used by COCFARM."),
)


PAIR_LABELS = {
    "builder.cart_every_min": ("Every", "A random number of battles in this range each time.", "battles"),
    "schedule.break_every_min": ("Every", "A new random number of attacks after each break.", "attacks"),
    "schedule.break_minutes_min": ("For", "Minutes, picked at random.", "min"),
    "schedule.daily_attacks_min": ("Attacks per day", "0 to 0 means no limit.", "attacks"),
    "bot.collect_gold": ("Collectors", "Which kinds it empties.", ""),
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
    **{path: ("device.mode", ("manual",)) for path in fields("device", "manual_width manual_height manual_dpi rooted_adb")},
}
