import re
from pathlib import Path

import unrealsdk  # type: ignore
from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import SETTINGS_DIR, Game, build_mod, get_pc, hook
from mods_base.options import BoolOption, SliderOption

FLASH_CARD = "topLevel_mc.card"
PICKUP_CARD = "inventory.card1"

LABEL = "Expected DPS"
SHIELD_LABEL = "Shield Power"

# Seconds of fighting the shield score is measured over.
SHIELD_WINDOW = 60.0

ACCURACY_FIELDS = ("accuracy", "acc")

TAGS = re.compile(r"<[^>]+>")
NUMBER = re.compile(r"\d+(?:[.,]\d+)?")

# One paragraph of the card's text. The game rewrites whatever we put there into its
# own wrapping, so a whole paragraph is taken at a time and read without its tags.
BLOCK = re.compile(r"<TEXTFORMAT.*?</TEXTFORMAT>|<font.*?</font>", re.IGNORECASE | re.DOTALL)


def without_ours(text: str) -> str:
    """The card's text with our own lines taken out, however the game has written them."""

    def drop(match: re.Match[str]) -> str:
        plain = TAGS.sub("", match.group(0)).strip()
        return "" if plain.startswith((LABEL, SHIELD_LABEL)) else match.group(0)

    return "\n".join(line for line in BLOCK.sub(drop, text).split("\n") if line.strip())

DisregardAccuracy = BoolOption("Disregard Accuracy", True, "Yes", "No")
DisregardCritical = BoolOption("Disregard Critical", True, "Yes", "No")
DisregardElements = BoolOption("Disregard Elements", False, "Yes", "No")
FontSize = SliderOption("Score font size", 9, 0, 24, 1, True)

CRIT_ATTRIBUTE = "PlayerCriticalHitBonus"

# Elements are measured against plain flesh, the surface with no resistance either way.
FLESH_SURFACE = 1

# How big a splash each element throws, as a share of the shot that threw it.
ELEMENT_SPLASH = {
    "incendiary": 0.6,
    "shock": 1.0,
    "corrosive": 0.4,
    "explosive": 1.5,
}

# What the game calls each sort of gun.
FAMILY_NAMES = {
    "repeater": ("repeater", "machine_pistol"),
    "revolver": ("revolver",),
    "smg": ("smg",),
    "shotgun": ("shotgun",),
    "rifle": ("combat_rifle",),
    "sniper": ("sniper",),
}

# What the cheapest splash costs from the tech pool, and how hard it hits.
PROC_TABLE = {
    "repeater": (4.0, 1.0),
    "revolver": (0.0, 1.0),
    "smg": (12.0, 1.0),
    "shotgun": (20.0, 1.0),
    "rifle": (20.0, 1.0),
    "sniper": (32.0, 1.0),
}

# How fast the tech pool refills, the same for every gun, measured in game.
POOL_REFILL = 4.0

comparing_item: UObject | None = None

SHIELD_DEFINITION = "gd_shields.A_Item.Item_Shield"
DELAY_ATTRIBUTE = "d_attributes.ShieldResourcePool.ShieldOnIdleRegenerationDelay"
delay_patched = False


def patch_shield_delay() -> None:
    """Shields only track capacity and recharge rate, so ask the game for the delay too."""
    global delay_patched
    if delay_patched:
        return

    try:
        unrealsdk.load_package(SHIELD_DEFINITION)
        definition = unrealsdk.find_object("ItemDefinition", SHIELD_DEFINITION)
        attribute = unrealsdk.find_object("ResourcePoolAttributeDefinition", DELAY_ATTRIBUTE)

        definition.ObjectFlags |= 0x4000
        definition.UIStats[2].Attribute = attribute
        delay_patched = True
    except Exception as ex:
        logging.dev_warning(f"[{LABEL}] could not expose the shield delay ({ex})")


# Temporary: dumps a weapon's own damage numbers once, to compare against the card.
DUMP_WEAPON = False
dumped: set[str] = set()


def dump_weapon(weapon: UObject, card_damage: float | None) -> None:
    name = str(weapon.GetShortHumanReadableName())
    if name in dumped:
        return
    dumped.add(name)

    found: list[str] = []
    for attr in dir(weapon):
        if attr.startswith("_"):
            continue
        try:
            value = getattr(weapon, attr)
        except Exception:
            continue
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            found.append(f"{attr}={value}")

    logging.info(f"[{LABEL}] {name}: card damage {card_damage}")
    logging.info(f"[{LABEL}] {name}: {', '.join(sorted(found))}")

    # The pause between bursts lives on the weapon's own type, not on the gun.
    try:
        kind = weapon.DefinitionData.WeaponTypeDefinition
        burst = [
            f"{attr}={getattr(kind, attr)}"
            for attr in dir(kind)
            if "urst" in attr or "utomatic" in attr
        ]
        logging.info(f"[{LABEL}] {name}: type {kind.Name} burst {', '.join(sorted(burst))}")
    except Exception as ex:
        logging.info(f"[{LABEL}] {name}: no weapon type ({ex})")

    # The element the gun fires, and the burn numbers attached to it.
    try:
        damage_type = weapon.StaticGetWeaponDamageType(weapon.DefinitionData)[0]
        tech = weapon.StaticCalculateWeaponTechLevelForUI(weapon.DefinitionData)[0]
        logging.info(f"[{LABEL}] {name}: element {damage_type} tech {tech}")

        if damage_type is not None:
            numbers: list[str] = []
            objects: list[str] = []
            for attr in dir(damage_type):
                if attr.startswith("_"):
                    continue
                try:
                    value = getattr(damage_type, attr)
                except Exception:
                    continue
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    numbers.append(f"{attr}={value}")
                elif type(value).__name__ in ("UObject", "WrappedArray"):
                    objects.append(f"{attr}={value}")
            logging.info(f"[{LABEL}] {name}: element numbers {', '.join(sorted(numbers))}")
            logging.info(f"[{LABEL}] {name}: element objects {', '.join(sorted(objects))}")
    except Exception as ex:
        logging.info(f"[{LABEL}] {name}: no element ({ex})")

    # Everything on the incendiary status effect, structs and arrays included.
    if "burn" not in dumped:
        dumped.add("burn")
        try:
            effect = unrealsdk.find_object(
                "StatusEffectDefinition",
                "gd_Incendiary.StatusEffect.Incendiary_Status",
            )
            for attr in dir(effect):
                if attr.startswith("_"):
                    continue
                try:
                    value = getattr(effect, attr)
                except Exception:
                    continue
                kind = type(value).__name__
                if kind in ("BoundFunction", "UClass", "EnumType", "UScriptStruct"):
                    continue
                logging.info(f"[{LABEL}] burn {attr} ({kind}) = {value}")
        except Exception as ex:
            logging.info(f"[{LABEL}] burn lookup failed ({ex})")

    # The bonus lines printed under the card, where a critical bonus would live.
    try:
        for entry in weapon.WeaponCardModifierStats:
            attribute = str(entry.AttributePresentation)
            logging.info(
                f"[{LABEL}] {name}: bonus {attribute} value={entry.ModifierValue}"
                f" shown={entry.bShouldDisplay}",
            )
    except Exception as ex:
        logging.info(f"[{LABEL}] {name}: no card bonuses ({ex})")

    # Shields keep their stats in a list rather than plain properties.
    try:
        stats = weapon.UIStatModifiers
        definition = weapon.DefinitionData.ItemDefinition
        for index, stat in enumerate(stats):
            try:
                attribute = str(definition.UIStats[index].Attribute)
            except Exception:
                attribute = "?"
            logging.info(
                f"[{LABEL}] {name}: UIStat {index} {attribute} total={stat.ModifierTotal}",
            )
    except Exception as ex:
        logging.info(f"[{LABEL}] {name}: no UIStatModifiers ({ex})")

    # The recharge delay is not in the stat list, so try reading the attribute directly.
    try:
        delay = unrealsdk.find_object(
            "ResourcePoolAttributeDefinition",
            "d_attributes.ShieldResourcePool.ShieldOnIdleRegenerationDelay",
        )
        logging.info(f"[{LABEL}] {name}: delay GetValue={delay.GetValue(weapon)}")
    except Exception as ex:
        logging.info(f"[{LABEL}] {name}: delay unreadable ({ex})")


def get_string(movie: UObject, path: str) -> str:
    try:
        return str(movie.GetVariableString(path))
    except Exception:
        return ""


def read_weapon(weapon: UObject, name: str, fallback: float) -> float:
    value = getattr(weapon, name, None)
    if value is None or not isinstance(value, (int, float)) or isinstance(value, bool):
        return fallback
    return float(value)


def read_accuracy(movie: UObject, card: str) -> float:
    """Accuracy is the one number only the card has."""
    for field in ACCURACY_FIELDS:
        numbers = NUMBER.findall(get_string(movie, f"{card}.{field}.text"))
        if numbers:
            return float(numbers[0].replace(",", "."))
    return 100.0


def find_status_effect(weapon: UObject) -> UObject | None:
    """The burn, shock or corrode effect belonging to whatever element the gun fires."""
    try:
        damage_type = weapon.StaticGetWeaponDamageType(weapon.DefinitionData)[0]
        if damage_type is None:
            return None
        package = str(damage_type.Outer.Outer.Name)
    except Exception:
        return None

    for effect in unrealsdk.find_all("StatusEffectDefinition"):
        try:
            if effect.bDoesDamageOverTime is not True:
                continue
            if str(effect.Outer.Outer.Name) != package:
                continue
            if str(effect.Name).endswith("_Status"):
                return effect
        except Exception:
            continue
    return None


def read_element(weapon: UObject) -> str | None:
    """Which element the gun fires, by name, or nothing for a plain gun."""
    try:
        damage_type = weapon.StaticGetWeaponDamageType(weapon.DefinitionData)[0]
        if damage_type is None:
            return None
        package = str(damage_type.Outer.Outer.Name).lower()
    except Exception:
        return None

    for element in ELEMENT_SPLASH:
        if element in package:
            return element
    return None


def read_family(weapon: UObject) -> str | None:
    """Which sort of gun it is, since each sort procs differently."""
    try:
        kind = str(weapon.DefinitionData.WeaponTypeDefinition.Name).lower()
    except Exception:
        return None

    for family, needles in FAMILY_NAMES.items():
        for needle in needles:
            if needle in kind:
                return family
    return None


def read_proc_level(weapon: UObject) -> int:
    """The x1 to x4 rating printed beside the element on the card."""
    try:
        level = int(weapon.StaticCalculateWeaponTechLevelForUI(weapon.DefinitionData)[0])
    except Exception:
        return 1
    return min(max(level, 1), 4)


def read_element_dps(weapon: UObject, shots_per_second: float) -> float:
    """The damage a second the element itself adds, on top of the bullets.

    An elemental gun fires ordinary bullets and now and then throws a splash of its
    element on top. How often is set by the tech pool, which refills at a fixed rate
    and is spent on every splash. A higher rating throws a bigger splash.
    """
    element = read_element(weapon)
    family = read_family(weapon)
    if element is None or family is None:
        return 0.0

    cost, proc_multiplier = PROC_TABLE[family]
    damage = read_weapon(weapon, "InstantHitDamage", 0)
    level = read_proc_level(weapon)

    if cost <= 0:
        procs = shots_per_second
    else:
        procs = min(POOL_REFILL / cost, shots_per_second)

    return procs * damage * ELEMENT_SPLASH[element] * proc_multiplier * level


def read_crit_bonus(weapon: UObject) -> float:
    """The gun's own critical bonus, 1.0 meaning the card's +100% Critical Hit Damage."""
    try:
        for entry in weapon.WeaponCardModifierStats:
            if CRIT_ATTRIBUTE in str(entry.AttributePresentation):
                return float(entry.ModifierValue)
    except Exception:
        pass
    return 0.0


def get_dps(movie: UObject, card: str, weapon: UObject) -> float | None:
    """Damage per second over a full magazine, including the reload that follows it."""
    damage = read_weapon(weapon, "InstantHitDamage", 0)
    projectiles = read_weapon(weapon, "ProjectilesPerShot", 1)
    fire_interval = read_weapon(weapon, "FireInterval", 0)
    clip_size = read_weapon(weapon, "ClipSize", 0)
    shot_cost = read_weapon(weapon, "ShotCost", 1)
    reload_time = read_weapon(weapon, "ReloadTime", 0)

    if DUMP_WEAPON:
        dump_weapon(weapon, damage)

    if damage <= 0 or fire_interval <= 0:
        logging.dev_warning(
            f"[{LABEL}] could not read stats:"
            f" damage={damage} fire interval={fire_interval}",
        )
        return None

    shot_damage = damage * max(projectiles, 1)
    if DisregardAccuracy.value is False:
        shot_damage *= read_accuracy(movie, card) / 100
    if DisregardCritical.value is False:
        shot_damage *= 1 + read_crit_bonus(weapon)

    shots = clip_size / max(shot_cost, 1)

    if shots < 1:
        span = fire_interval
    else:
        # A burst gun stops after every burst and waits for another click, which costs
        # about one extra shot's worth of time each time.
        burst = read_weapon(weapon, "AutomaticBurstCount", 0)
        pauses = 0.0
        if burst > 0:
            pauses = -(-shots // burst) * fire_interval
        span = shots * fire_interval + pauses + reload_time

    rounds = max(shots, 1)
    bullets = rounds * shot_damage / span

    if DisregardElements.value is True:
        return bullets

    return bullets + read_element_dps(weapon, rounds / span)


def get_ui_stats(item: UObject) -> dict[str, float]:
    """Shields and grenade mods keep their numbers in a list rather than plain properties."""
    stats: dict[str, float] = {}
    try:
        definition = item.DefinitionData.ItemDefinition
        for index, modifier in enumerate(item.UIStatModifiers):
            name = str(definition.UIStats[index].Attribute).rsplit(".", 1)[-1].rstrip("'")
            stats[name] = float(modifier.ModifierTotal)
    except Exception:
        return stats
    return stats


def get_shield_score(item: UObject) -> float | None:
    """Damage the shield soaks over a minute: its capacity plus everything it recharges."""
    stats = get_ui_stats(item)
    capacity = stats.get("ShieldMaxValue")
    rate = stats.get("ShieldOnIdleRegenerationRate")
    if capacity is None or rate is None:
        return None

    delay = stats.get("ShieldOnIdleRegenerationDelay", 0.0)
    return capacity + rate * max(SHIELD_WINDOW - delay, 0)


def apply_line(movie: UObject, card: str, label: str, value: float | None) -> None:
    path = f"{card}.funstats.htmlText"
    text = without_ours(get_string(movie, path))

    if value is not None:
        line = (
            f'<font size="{FontSize.value}" color="#ffd200">'
            f"{label} {round(value):,}</font>"
        )
        text = f"{line}\n{text}" if text else line

    movie.SetVariableString(path, text)


def apply_dps(movie: UObject, card: str, weapon: UObject | None) -> None:
    dps = None if weapon is None else get_dps(movie, card, weapon)
    apply_line(movie, card, LABEL, dps)


def apply_shield(movie: UObject, card: str, item: UObject | None) -> None:
    score = None if item is None else get_shield_score(item)
    apply_line(movie, card, SHIELD_LABEL, score)


def is_weapon(item: UObject | None) -> bool:
    return item is not None and "WillowWeapon" in str(item.Class)


def is_shield(item: UObject | None) -> bool:
    return item is not None and "ShieldMaxValue" in get_ui_stats(item)


def apply_item(movie: UObject, card: str, item: UObject | None) -> None:
    if is_weapon(item):
        apply_dps(movie, card, item)
    elif is_shield(item):
        apply_shield(movie, card, item)


def highlighted_item(movie: UObject) -> UObject | None:
    """The backpack tracks the highlighted item itself, vendors keep it in a list."""
    try:
        return movie.GetCurrentHighlightedObject()
    except AttributeError:
        pass

    try:
        if movie.bOnItemOfTheDay is True:
            return movie.ItemOfTheDayData.Item
        return movie.ActiveTextList.GetHighlightedObject()
    except Exception:
        return None


def update_cards(movie: UObject) -> None:
    patch_shield_delay()

    item = highlighted_item(movie)

    if DUMP_WEAPON and item is not None and not is_weapon(item):
        dump_weapon(item, None)

    if is_shield(item):
        if movie.IsComparing() is True:
            if is_shield(comparing_item):
                apply_shield(movie, f"{FLASH_CARD}1", comparing_item)
            apply_shield(movie, f"{FLASH_CARD}2", item)
        else:
            apply_shield(movie, f"{FLASH_CARD}1", item)
        return

    if not is_weapon(item):
        return

    if movie.IsComparing() is True:
        # Card 1 is what you started comparing from, card 2 is the highlighted item.
        if is_weapon(comparing_item):
            apply_dps(movie, f"{FLASH_CARD}1", comparing_item)
        apply_dps(movie, f"{FLASH_CARD}2", item)
    else:
        apply_dps(movie, f"{FLASH_CARD}1", item)


@hook(
    hook_func="WillowGame.StatusMenuExGFxMovie:UpdateCardPanelWithCurrentCell",
    hook_type=Type.POST,
)
def on_card_key(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    update_cards(obj)


@hook(
    hook_func="WillowGame.StatusMenuExGFxMovie:UpdateCardPanelWithCurrentActiveListEntry",
    hook_type=Type.POST,
)
def on_card_mouse(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    update_cards(obj)


@hook(
    hook_func="WillowGame.StatusMenuExGFxMovie:extSetMouseOverCell",
    hook_type=Type.POST,
)
def on_card_hover(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    """Resting the mouse on a row is the only thing that happens when hovering."""
    update_cards(obj)


# Enhanced fills its cards at a moment the original does not, and without these two
# the reading never appears there. In the original the card is not ready this early,
# and writing then would wipe the bonus lines, so they are only used on Enhanced.


@hook(
    hook_func="WillowGame.StatusMenuExGFxMovie:UpdateCardPanel",
    hook_type=Type.POST,
)
def on_card_panel(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    """The card being filled in, whichever way you got there."""
    update_cards(obj)


@hook(
    hook_func="WillowGame.VendingMachineGFxMovie:UpdateCardPanel",
    hook_type=Type.POST,
)
def on_vendor_panel(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    """The shop's card being filled in, whichever way you got there."""
    update_cards(obj)


# Neither of these is used at the moment: they fill the card before the game has
# put its bonus lines on, which loses them.
ENHANCED_ONLY = ()


@hook(
    hook_func="WillowGame.StatusMenuExGFxMovie:extCompare",
    hook_type=Type.PRE,
)
def on_compare_start(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    global comparing_item
    comparing_item = highlighted_item(obj)


@hook(
    hook_func="WillowGame.StatusMenuExGFxMovie:extCard2Visible",
    hook_type=Type.POST,
)
def on_compare(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    update_cards(obj)


@hook(
    hook_func="WillowGame.ItemPickupGFxMovie:UpdateCompareAgainstThing",
    hook_type=Type.POST,
)
def on_pickup_card(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    patch_shield_delay()

    try:
        ground_item = obj.MyHUDOwner.ItemComparison[0]
    except Exception:
        return

    apply_item(obj, PICKUP_CARD, ground_item)



# Temporary: times how long a full magazine takes when you fire it as fast as you can.
MEASURE_FIRE = False
last_shot = 0.0
magazine_start = 0.0
shots_fired = 0


@hook(hook_func="WillowGame.WillowWeapon:FireAmmunition", hook_type=Type.POST)
def on_fire(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    if MEASURE_FIRE is False:
        return

    try:
        from mods_base import get_pc

        if obj is not get_pc().Pawn.Weapon:
            return
    except Exception:
        return

    global last_shot, magazine_start, shots_fired

    import time

    now = time.perf_counter()
    gap = now - last_shot
    last_shot = now

    # A long silence means a reload or a new burst of shooting, so start counting again.
    if gap > 1.5 or shots_fired == 0:
        magazine_start = now
        shots_fired = 1
        return

    shots_fired += 1
    span = now - magazine_start
    logging.info(
        f"[{LABEL}] shot {shots_fired} at {span:.3f}s"
        f" ({shots_fired / span:.2f} a second so far)",
    )


# Temporary: watches the tech pool refill on the gun in your hands.
MEASURE_POOL = False
pool_frames = 0
pool_last = None
pool_time = 0.0


def item_score(item: UObject) -> float:
    """How good a thing is, so the best sits at the top of the list."""
    if is_weapon(item):
        score = get_dps(None, "", item)
        return 0.0 if score is None else score
    if is_shield(item):
        score = get_shield_score(item)
        return 0.0 if score is None else score
    return 0.0


# The extra page you reach with Page Up and Page Down in the backpack.
DPS_PAGE = 4

# What the page is built from: the plain backpack sort, nothing filtered out,
# and no headings, so everything sits in one straight list.
PLAIN_SORT = 2
NO_FILTER = 0
NO_HEADINGS = 0

# A line holding a real thing, rather than a heading.
ROW_KIND = 0

# The name written above the page. The game keeps its menu wording in text files
# under the game folder, so the name is added there once and looked up by this key.
PAGE_KEY = "DPSSort"
PAGE_NAME = "DPS"
PAGE_SECTION = "[StatusMenu]"


def name_dps_page() -> None:
    """Adds the page name to the game's wording files, if it is not there yet."""
    folder = Path(__file__).parents[2] / "WillowGame" / "Localization"
    for text_file in folder.glob("*/WillowGame.*"):
        try:
            lines = text_file.read_text(encoding="utf-8", errors="replace").splitlines()
            if any(line.startswith(f"{PAGE_KEY}=") for line in lines):
                continue
            if PAGE_SECTION not in lines:
                continue

            place = lines.index(PAGE_SECTION) + 1
            lines.insert(place, f"{PAGE_KEY}={PAGE_NAME}")
            text_file.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
        except Exception as ex:
            logging.dev_warning(f"[{LABEL}] could not name the score page ({ex})")


def add_dps_page(movie: UObject) -> None:
    """Gives the backpack screen one more page to cycle through."""
    try:
        configs = list(movie.SortConfigurations)
        if len(configs) <= DPS_PAGE:
            configs.append(configs[0])
            movie.SortConfigurations = configs
            configs = list(movie.SortConfigurations)

        page = configs[DPS_PAGE]
        if str(page.SortTitleLookupKey) == PAGE_KEY:
            return

        page.SortType = PLAIN_SORT
        page.FilterType = NO_FILTER
        page.CategoryType = NO_HEADINGS
        page.SortTitleLookupKey = PAGE_KEY
        configs[DPS_PAGE] = page
        movie.SortConfigurations = configs
    except Exception as ex:
        logging.dev_warning(f"[{LABEL}] could not add the score page ({ex})")


@hook(hook_func="WillowGame.StatusMenuExGFxMovie:SortContainer", hook_type=Type.PRE)
def on_sorting(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    add_dps_page(obj)


@hook(hook_func="WillowGame.StatusMenuExGFxMovie:SortContainer", hook_type=Type.POST)
def on_sorted(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    """Puts the list in order of how good each thing is, best first."""
    try:
        if int(obj.LeftSideSortConfigIndex) != DPS_PAGE:
            return

        container = __args.Container
        rows = list(container.OneTimeArray)

        # Read the list out as plain numbers first, so putting it back cannot
        # end up copying a row over one it still needs.
        entries = [(int(entry.ArrayIdx), int(entry.Kind)) for entry in container.TextEntries]

        def rank(entry: tuple[int, int]) -> float:
            place, kind = entry
            if kind != ROW_KIND:
                return float("inf")
            return item_score(rows[place].Data)

        container.TextEntries = [
            unrealsdk.make_struct("GFxTextEntry", ArrayIdx=place, Kind=kind)
            for place, kind in sorted(entries, key=rank, reverse=True)
        ]
        container.UpdateTextEntries()
    except Exception as ex:
        logging.dev_warning(f"[{LABEL}] could not order the score page ({ex})")


@hook(hook_func="Engine.GameViewportClient:PostRender", hook_type=Type.POST)
def on_pool_tick(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    if MEASURE_POOL is False:
        return

    global pool_frames, pool_last, pool_time

    import time

    try:
        weapon = get_pc().Pawn.Weapon
        level = float(weapon.TechLevel)
        if level <= 0:
            return

        data = weapon.TechPool.Data
        value = float(data.CurrentValue)
        top = float(data.MaxValue)
    except Exception as ex:
        if pool_frames == 0:
            pool_frames = 1
            logging.info(f"[{LABEL}] pool unreadable ({ex})")
        return

    now = time.perf_counter()

    if pool_last is not None and abs(value - pool_last) > 0.01:
        gap = now - pool_time
        rate = (value - pool_last) / gap if gap > 0 else 0.0
        logging.info(
            f"[{LABEL}] pool {pool_last:.2f} to {value:.2f} of {top:.2f}"
            f" over {gap:.3f}s, {rate:+.2f} a second, tech {level}",
        )

    pool_last = value
    pool_time = now


@hook(
    hook_func="WillowGame.VendingMachineGFxMovie:UpdateCardPanelWithItemOfTheDay",
    hook_type=Type.POST,
)
def on_vendor_daily(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    update_cards(obj)


@hook(
    hook_func="WillowGame.VendingMachineGFxMovie:UpdateCardPanelWithCurrentActiveListEntry",
    hook_type=Type.POST,
)
def on_vendor_item(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    update_cards(obj)


@hook(
    hook_func="WillowGame.VendingMachineGFxMovie:extSetMouseOverCell",
    hook_type=Type.POST,
)
def on_vendor_hover(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    """The mouse resting on a row in the shop."""
    update_cards(obj)


@hook(
    hook_func="WillowGame.VendingMachineGFxMovie:extCompare",
    hook_type=Type.PRE,
)
def on_vendor_compare_start(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    global comparing_item
    comparing_item = highlighted_item(obj)


@hook(
    hook_func="WillowGame.VendingMachineGFxMovie:extCard2Visible",
    hook_type=Type.POST,
)
def on_vendor_compare(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    update_cards(obj)


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

name_dps_page()

build_mod(
    options=[
        DisregardAccuracy,
        DisregardCritical,
        DisregardElements,
        FontSize,
    ],
    keybinds=[],
    hooks=[
        on_card_key,
        on_card_mouse,
        on_card_hover,
        on_compare_start,
        on_compare,
        on_vendor_daily,
        on_vendor_item,
        on_vendor_hover,
        on_vendor_compare_start,
        on_vendor_compare,
        on_pickup_card,
        on_fire,
        on_pool_tick,
        on_sorting,
        on_sorted,
        *(ENHANCED_ONLY if Game.get_current() is Game.BL1E else ()),
    ],
    commands=[],
    settings_file=Path(f"{SETTINGS_DIR}/GearScore.json"),
)

patch_shield_delay()

logging.info(f"Gear Score Loaded: {__version__}, {__version_info__}")
