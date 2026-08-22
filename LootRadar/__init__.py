import math
from pathlib import Path

import unrealsdk  # type: ignore
from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Block, Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import SETTINGS_DIR, Game, build_mod, get_pc, hook
from mods_base.options import BoolOption, SliderOption, SpinnerOption

FONT = "ui_fonts.font_willowbody_18pt"

UNITS_PER_METRE = 50.0
FEET_PER_METRE = 3.28084

TEXT_SCALE = 0.6

# Frames between sweeps of the area.
REFRESH_FRAMES = 60

# How often we check whether a shop screen is up, in frames.
SHOP_FRAMES = 10

# The compass bar, measured as a share of the screen.
# Enhanced draws its bar lower down than the original does.
COMPASS_CENTRE = 0.5
COMPASS_HALF_WIDTH = 0.143
COMPASS_TOP = 0.885 if Game.get_current() is Game.BL1E else 0.833
COMPASS_ARC = 45.0

# How far above the bar the marks sit, and how big they are.
MARK_LIFT = 14
MARK_HEIGHT = 8
MARK_SIZE = 5
BANG_HEIGHT = 18

GEAR_COLOUR = (120, 255, 140)
SUPPLY_COLOUR = (90, 180, 255)
HEALTH_COLOUR = (255, 120, 160)
MONEY_COLOUR = (255, 210, 0)
CHEST_COLOUR = (255, 60, 60)
WHITE_CHEST_COLOUR = (245, 245, 245)

# The chests, as the game names them.
RED_CHEST = "InteractiveObj_TreasureChest"
WHITE_CHEST = "InteractiveObj_Crate_Metal"

ShowWeapons = BoolOption("Show Weapon Loot", True, "Yes", "No")
ShowMoney = BoolOption("Show Money Loot", True, "Yes", "No")
ShowAmmo = BoolOption("Show Ammo Loot", True, "Yes", "No")
ShowHealth = BoolOption("Show Health Loot", True, "Yes", "No")
ShowRedChests = BoolOption("Show Red Chests", True, "Yes", "No")
ShowWhiteChests = BoolOption("Show White Chests", True, "Yes", "No")
BetterOnly = BoolOption("Display Only Better Weapons", False, "Yes", "No")
HideFull = BoolOption("Hide Full Pickups", True, "On", "Off")
ShowDistance = BoolOption("Show Distance", True, "Yes", "No")
Units = SpinnerOption("Units", value="Metres", choices=["Metres", "Feet"], wrap_enabled=True)

frames = REFRESH_FRAMES

# Whether a shop screen is up, asked now and then rather than every frame.
shop_open = False
shop_frames = SHOP_FRAMES

marks: list[tuple[tuple[float, float, float], bool]] = []
hidden: set[UObject] = set()

gear = None
black = None
font = None
colours: dict[str, object] = {}

# The weakest gun of each sort in your bag, worked out once a sweep.
carried: dict[str, float] = {}


def can_take(pickup: UObject, pawn: UObject) -> bool:
    """Whether you could actually pick this up, so full ammo drops out.

    Only ammo and money can be full up. Guns and gear always count as takeable,
    even ones asking for a higher level than you have, since those still go in
    your bag to use later.
    """
    if kind_of(pickup) == "gear":
        return True
    try:
        return pickup.Inventory.CanBeUsedBy(pawn) is True
    except Exception:
        return False


def kind_of(pickup: UObject) -> str:
    """Money, ammo, or gear you would carry away."""
    try:
        tag = str(pickup.Inventory.DefinitionData.ItemDefinition).lower()
    except Exception:
        return "gear"

    if "currency" in tag or "credit" in tag or "money" in tag or "cash" in tag:
        return "money"
    if "ammodrop" in tag or "ammo" in tag:
        return "ammo"
    if "health" in tag or "medkit" in tag:
        return "health"
    return "gear"


def wanted(kind: str) -> bool:
    if kind == "money":
        return ShowMoney.value is True
    if kind == "ammo":
        return ShowAmmo.value is True
    if kind == "health":
        return ShowHealth.value is True
    return ShowWeapons.value is True


def read_number(weapon: UObject, name: str, fallback: float) -> float:
    value = getattr(weapon, name, None)
    if value is None or not isinstance(value, (int, float)) or isinstance(value, bool):
        return fallback
    return float(value)


def card_dps(weapon: UObject) -> float | None:
    """The very number Gear Score prints on the card, when that mod is there to work it out.

    Its reading counts elemental damage and whatever else its own settings say, so
    without it the beam would rank guns by a different number than the card shows.
    Accuracy is the one thing it cannot do here, since that only exists on a card and
    loot on the ground has none.
    """
    try:
        import GearScore  # type: ignore
    except Exception:
        return None

    try:
        if GearScore.DisregardAccuracy.value is not True:
            return None
        return GearScore.get_dps(None, "", weapon)
    except Exception:
        return None


def gun_dps(weapon: UObject) -> float | None:
    """Damage a second over a full magazine, including the reload that follows it."""
    matching = card_dps(weapon)
    if matching is not None:
        return matching

    try:
        damage = read_number(weapon, "InstantHitDamage", 0)
        fire_interval = read_number(weapon, "FireInterval", 0)
        if damage <= 0 or fire_interval <= 0:
            return None

        pellets = max(read_number(weapon, "ProjectilesPerShot", 1), 1)
        shots = read_number(weapon, "ClipSize", 0) / max(read_number(weapon, "ShotCost", 1), 1)
        reload_time = read_number(weapon, "ReloadTime", 0)

        if shots < 1:
            span = fire_interval
        else:
            burst = read_number(weapon, "AutomaticBurstCount", 0)
            pauses = -(-shots // burst) * fire_interval if burst > 0 else 0.0
            span = shots * fire_interval + pauses + reload_time

        return max(shots, 1) * damage * pellets / span
    except Exception:
        return None


# Shields are weighed against each other, over a minute of fighting.
SHIELD_FAMILY = "shield"
SHIELD_WINDOW = 60.0

# The game has several names for each sort of gun, and they all count as one sort.
# Snipers are checked before rifles, since the game calls them sniper rifles.
FAMILY_WORDS = (
    ("shotgun", "shotgun"),
    ("smg", "smg"),
    ("sniper", "sniper"),
    ("launcher", "launcher"),
    ("revolver", "revolver"),
    ("repeater", "repeater"),
    ("machine_pistol", "repeater"),
    ("machinegun", "rifle"),
    ("rifle", "rifle"),
)


def gun_family(weapon: UObject) -> str | None:
    """Which sort of gun it is, so like is only weighed against like."""
    try:
        kind = str(weapon.DefinitionData.WeaponTypeDefinition.Name).lower()
    except Exception:
        return None

    for word, family in FAMILY_WORDS:
        if word in kind:
            return family
    return kind


def shield_score(item: UObject) -> float | None:
    """Damage a shield soaks over a minute: its capacity plus everything it recharges.

    Shields keep their numbers in a list rather than as plain properties, and anything
    without a capacity in that list is not a shield.
    """
    stats: dict[str, float] = {}
    try:
        definition = item.DefinitionData.ItemDefinition
        for index, modifier in enumerate(item.UIStatModifiers):
            name = str(definition.UIStats[index].Attribute).rsplit(".", 1)[-1].rstrip("'")
            stats[name] = float(modifier.ModifierTotal)
    except Exception:
        return None

    capacity = stats.get("ShieldMaxValue")
    rate = stats.get("ShieldOnIdleRegenerationRate")
    if capacity is None or rate is None:
        return None

    delay = stats.get("ShieldOnIdleRegenerationDelay", 0.0)
    return capacity + rate * max(SHIELD_WINDOW - delay, 0)


def worst_carried() -> dict[str, float]:
    """The weakest gun of each sort and the weakest shield you carry, held and stowed."""
    lowest: dict[str, float] = {}

    pc = get_pc()
    if pc is None or pc.Pawn is None:
        return lowest

    bag: list[UObject] = []
    try:
        manager = pc.Pawn.InvManager
        # What you are carrying, whichever list the game keeps it in. Guns and gear
        # each have their own chain, so the shield you are wearing is on ItemChain.
        for name in ("Backpack", "InventoryChain", "ItemChain"):
            held = getattr(manager, name, None)
            if held is None:
                continue
            if isinstance(held, UObject):
                # A chain, each item pointing at the next.
                while held is not None:
                    bag.append(held)
                    held = getattr(held, "Inventory", None)
            else:
                bag += [item for item in held if item is not None]
    except Exception:
        return lowest

    for item in bag:
        family = gun_family(item)
        score = gun_dps(item)
        if family is None or score is None:
            family = SHIELD_FAMILY
            score = shield_score(item)
        if score is None:
            continue
        if family not in lowest or score < lowest[family]:
            lowest[family] = score

    return lowest


def worth_taking(pickup: UObject) -> bool:
    """Whether the gun or shield on the ground beats the weakest of its sort in your bag."""
    if BetterOnly.value is False:
        return True

    # Money and ammo are never weighed against anything.
    if kind_of(pickup) != "gear":
        return True

    try:
        item = pickup.Inventory
    except Exception:
        return True

    family = gun_family(item)
    score = gun_dps(item)
    if family is None or score is None:
        family = SHIELD_FAMILY
        score = shield_score(item)
    if score is None:
        return True

    floor = carried.get(family)
    return floor is None or score > floor


def dot(canvas, x: int, y: int, colour) -> None:
    """A small filled diamond."""
    for step in range(MARK_SIZE + 1):
        span = MARK_SIZE - step
        canvas.Draw2DLine(x - span, y - step, x + span, y - step, colour)
        canvas.Draw2DLine(x - span, y + step, x + span, y + step, colour)


def bang_shape(canvas, x: int, y: int, colour, grow: int) -> None:
    """An exclamation mark: a tall bar with a square dot under it."""
    top = y - BANG_HEIGHT - grow
    bottom = y + 3 + grow
    reach = 2 + grow

    for across in range(-reach, reach + 1):
        canvas.Draw2DLine(x + across, top, x + across, bottom, colour)

    foot = y + 8 - grow
    for down in range(5 + grow * 2):
        canvas.Draw2DLine(x - reach, foot + down, x + reach, foot + down, colour)


def bang(canvas, x: int, y: int, colour) -> None:
    """The mark itself, on a black edge so it shows against anything."""
    bang_shape(canvas, x, y, black, 1)
    bang_shape(canvas, x, y, colour, 0)


def label(canvas, x: float, y: float, text: str, colour) -> None:
    """How far away it is, in black edged text above the mark."""
    global font

    if font is None:
        font = unrealsdk.find_object("Font", FONT)

    canvas.Font = font

    canvas.DrawColor = black
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        canvas.SetPos(x + dx, y + dy)
        canvas.DrawText(text, False, TEXT_SCALE, TEXT_SCALE)

    canvas.DrawColor = colour
    canvas.SetPos(x, y)
    canvas.DrawText(text, False, TEXT_SCALE, TEXT_SCALE)


def alive(pickup: UObject) -> bool:
    """Whether the pickup still exists. Touching a gone one takes the game down."""
    try:
        if pickup is None:
            return False
        if pickup.bDeleteMe is True or pickup.bPendingDelete is True:
            return False
        return pickup.Inventory is not None
    except Exception:
        return False


def restore_all() -> None:
    """Puts every hidden pickup back on screen."""
    pc = get_pc()
    hud = None if pc is None else pc.myHUD

    for pickup in list(hidden):
        hidden.discard(pickup)
        if not alive(pickup):
            continue
        try:
            if hud is not None:
                hud.AddPostRenderedActor(pickup)
            pickup.SpawnPickupParticles()
        except Exception:
            pass


def on_disable() -> None:
    restore_all()


@hook(hook_func="WillowGame.WillowPickup:GiveTo", hook_type=Type.PRE)
def on_pick_up(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> type[Block] | None:
    """A gun no better than the one you carry stays on the ground."""
    if BetterOnly.value is True and not worth_taking(obj):
        return Block
    return None


@hook(hook_func="WillowGame.WillowPickup:SpawnPickupParticles", hook_type=Type.PRE)
def on_spawn_particles(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> type[Block] | None:
    if HideFull.value is False and BetterOnly.value is False:
        return None

    pc = get_pc()
    if pc is None or pc.Pawn is None:
        return None

    full = HideFull.value is True and not can_take(obj, pc.Pawn)
    if not full and worth_taking(obj):
        hidden.discard(obj)
        return None

    hidden.add(obj)

    # Take it off the screen straight away rather than waiting for the next sweep.
    try:
        if pc.myHUD is not None:
            pc.myHUD.RemovePostRenderedActor(obj)
    except Exception:
        pass

    return Block


# The chests in the area, looked up once per sweep.
CHESTS_EVERY = 1
chest_list: list[tuple[UObject, str]] = []
chest_frames = CHESTS_EVERY

# What each pickup turned out to be, so its name is only read once.
kinds: dict[UObject, str] = {}

# How many sweeps to sit out while a new area is being swapped in.
SETTLE_SWEEPS = 4
settling = 0
last_area = ""


def find_chests() -> list[tuple[tuple[float, float, float], str]]:
    """Chests in the area that nobody has opened yet."""
    global chest_list, chest_frames

    found: list[tuple[tuple[float, float, float], str]] = []

    if ShowRedChests.value is False and ShowWhiteChests.value is False:
        return found

    chest_frames += 1
    if chest_frames >= CHESTS_EVERY:
        chest_frames = 0
        chest_list = []
        for thing in unrealsdk.find_all("WillowInteractiveObject"):
            try:
                definition = str(thing.InteractiveObjectDefinition)
            except Exception:
                continue

            if RED_CHEST in definition:
                chest_list.append((thing, "chest"))
            elif WHITE_CHEST in definition:
                chest_list.append((thing, "white"))

    for thing, kind in chest_list:
        if kind == "chest" and ShowRedChests.value is False:
            continue
        if kind == "white" and ShowWhiteChests.value is False:
            continue
        try:
            if thing.bCanBeUsed is not True:
                continue
            spot = thing.Location
            found.append(((float(spot.X), float(spot.Y), float(spot.Z)), kind))
        except Exception:
            continue

    return found


def sweep() -> None:
    """Everything lying around in the area that is worth walking over to.

    The same pass also keeps ammo you cannot carry from lighting up.
    """
    global marks, last_area, settling, chest_list, chest_frames

    pc = get_pc()
    if pc is None or pc.Pawn is None:
        return

    # Everything held onto from the area you left is being taken apart, and asking
    # any of it anything takes the game down. So it is all dropped, and nothing is
    # looked at again until the new area has settled.
    try:
        here = str(pc.WorldInfo.GetMapName(True))
    except Exception:
        here = last_area

    if here != last_area:
        last_area = here
        settling = SETTLE_SWEEPS
        chest_list = []
        chest_frames = 0
        kinds.clear()
        hidden.clear()
        marks = []
        return

    if settling > 0:
        settling -= 1
        marks = []
        return

    marks = find_chests()

    global carried
    carried = worst_carried() if BetterOnly.value is True else {}

    pawn = getattr(pc.Pawn, "Driver", None) or pc.Pawn
    hiding = HideFull.value is True or BetterOnly.value is True
    if not hiding and hidden:
        restore_all()

    # What the game is currently drawing, asked of the game itself rather than
    # remembered, so anything left off the screen earlier gets put back.
    hud = pc.myHUD
    try:
        on_screen = set(hud.PostRenderedActors) if hud is not None else set()
    except Exception:
        on_screen = None

    for pickup in unrealsdk.find_all("WillowPickup"):
        try:
            if pickup.bDeleteMe is True or pickup.bPendingDelete is True:
                hidden.discard(pickup)
                continue
            if pickup.Inventory is None:
                continue

            takeable = can_take(pickup, pawn)
        except Exception:
            continue

        # Full ammo drops out, and so does a gun no better than the one you carry.
        better = worth_taking(pickup)
        show = takeable and better
        if HideFull.value is False:
            show = better

        if hiding:
            if show:
                missing = (
                    pickup in hidden if on_screen is None else pickup not in on_screen
                )
                hidden.discard(pickup)
                if missing:
                    try:
                        if hud is not None:
                            hud.AddPostRenderedActor(pickup)
                        pickup.SpawnPickupParticles()
                    except Exception:
                        pass
            elif pickup not in hidden:
                hidden.add(pickup)
                try:
                    if hud is not None:
                        hud.RemovePostRenderedActor(pickup)
                    pickup.DestroyPickupParticles()
                except Exception:
                    pass


        if not takeable or not better:
            continue

        kind = kinds.get(pickup)
        if kind is None:
            kind = kind_of(pickup)
            kinds[pickup] = kind

        if wanted(kind):
            try:
                spot = pickup.Location
                marks.append(
                    ((float(spot.X), float(spot.Y), float(spot.Z)), kind),
                )
            except Exception:
                continue


def bearing_to(here, x: float, y: float) -> float:
    """How far left or right of where you are looking the spot sits, in degrees."""
    try:
        angle = math.degrees(math.atan2(y - float(here.Y), x - float(here.X)))
        facing = float(get_pc().Rotation.Yaw) * 360.0 / 65536.0
    except Exception:
        return 999.0

    return (angle - facing + 180.0) % 360.0 - 180.0


@hook(hook_func="Engine.GameViewportClient:PostRender", hook_type=Type.POST)
def on_render(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    global frames, gear, black, shop_open, shop_frames

    pc = get_pc()
    if pc is None or pc.Pawn is None or pc.myHUD is None:
        return

    canvas = __args.Canvas
    if canvas is None:
        return

    frames += 1
    if frames >= REFRESH_FRAMES:
        frames = 0
        sweep()

    if not marks:
        return

    # Nothing of ours draws while the menu with the map and skills is up.
    try:
        if pc.bStatusMenuOpen is True:
            return

        # A shop screen counts too. Asking the game which screen it is playing every
        # frame is too slow, so it is asked now and then and only the answer is kept.
        shop_frames += 1
        if shop_frames >= SHOP_FRAMES:
            shop_frames = 0
            shop_open = False
            for manager in unrealsdk.find_all("WillowGFxUIManager"):
                try:
                    playing = manager.GetPlayingMovie()
                except Exception:
                    continue
                if playing is None:
                    continue
                if "VendingMachine" in str(playing.Class.Name):
                    shop_open = True
                    break

        if shop_open:
            return
    except Exception:
        pass

    if gear is None:
        black = unrealsdk.make_struct("Color", R=0, G=0, B=0, A=255)
        gear = unrealsdk.make_struct(
            "Color",
            R=GEAR_COLOUR[0],
            G=GEAR_COLOUR[1],
            B=GEAR_COLOUR[2],
            A=255,
        )
        colours["gear"] = gear
        colours["ammo"] = unrealsdk.make_struct(
            "Color",
            R=SUPPLY_COLOUR[0],
            G=SUPPLY_COLOUR[1],
            B=SUPPLY_COLOUR[2],
            A=255,
        )
        colours["health"] = unrealsdk.make_struct(
            "Color",
            R=HEALTH_COLOUR[0],
            G=HEALTH_COLOUR[1],
            B=HEALTH_COLOUR[2],
            A=255,
        )
        colours["money"] = unrealsdk.make_struct(
            "Color",
            R=MONEY_COLOUR[0],
            G=MONEY_COLOUR[1],
            B=MONEY_COLOUR[2],
            A=255,
        )
        colours["chest"] = unrealsdk.make_struct(
            "Color",
            R=CHEST_COLOUR[0],
            G=CHEST_COLOUR[1],
            B=CHEST_COLOUR[2],
            A=255,
        )
        colours["white"] = unrealsdk.make_struct(
            "Color",
            R=WHITE_CHEST_COLOUR[0],
            G=WHITE_CHEST_COLOUR[1],
            B=WHITE_CHEST_COLOUR[2],
            A=255,
        )

    try:
        here = pc.Pawn.Location
        bottom = canvas.SizeY * COMPASS_TOP - MARK_LIFT
        top = bottom - MARK_HEIGHT

        middle = int((top + bottom) / 2)

        for (x, y, z), kind in marks:
            offset = bearing_to(here, x, y)
            if offset > COMPASS_ARC or offset < -COMPASS_ARC:
                continue

            across = int(
                canvas.SizeX
                * (COMPASS_CENTRE + COMPASS_HALF_WIDTH * offset / COMPASS_ARC),
            )
            colour = colours.get(kind, gear)

            bang(canvas, across, middle, colour)

            if ShowDistance.value is True:
                gap = (
                    (x - float(here.X)) ** 2
                    + (y - float(here.Y)) ** 2
                    + (z - float(here.Z)) ** 2
                ) ** 0.5
                metres = gap / UNITS_PER_METRE
                if Units.value == "Feet":
                    text = f"{round(metres * FEET_PER_METRE)}"
                else:
                    text = f"{round(metres)}"

                label(
                    canvas,
                    across - len(text) * 4,
                    middle - BANG_HEIGHT - 18,
                    text,
                    colour,
                )
    except Exception as ex:
        logging.dev_warning(f"[Loot Radar] could not draw ({ex})")


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

build_mod(
    options=[
        ShowWeapons,
        ShowMoney,
        ShowAmmo,
        ShowHealth,
        ShowRedChests,
        ShowWhiteChests,
        BetterOnly,
        ShowDistance,
        Units,
        HideFull,
    ],
    keybinds=[],
    hooks=[on_render, on_spawn_particles, on_pick_up],
    commands=[],
    settings_file=Path(f"{SETTINGS_DIR}/LootRadar.json"),
)

logging.info(f"Loot Radar Loaded: {__version__}, {__version_info__}")
