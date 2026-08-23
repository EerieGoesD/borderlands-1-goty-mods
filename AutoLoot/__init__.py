from pathlib import Path

import unrealsdk  # type: ignore
from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import SETTINGS_DIR, build_mod, get_pc, hook
from mods_base.options import BoolOption, SliderOption

# Frames between rebuilds of the list of loot lying about.
REFRESH_FRAMES = 15

# How many are looked at each frame, so the game is not held up.
BATCH = 12

# The game measures in its own units. Fifty of them make a metre.
UNITS_PER_METRE = 50.0

Reach = SliderOption("Reach in metres", 5, 1, 20, 1, True)
LootAmmo = BoolOption("Loot Ammo", True, "Yes", "No")
LootHealth = BoolOption("Loot Health", True, "Yes", "No")
LootMoney = BoolOption("Loot Money", True, "Yes", "No")
LootWeapons = BoolOption("Loot Weapons", True, "Yes", "No")

frames = REFRESH_FRAMES

# What each pickup turned out to be, so its name is only read once.
kinds: dict[UObject, str] = {}

# The loot still to be looked at, a few each frame.
waiting_on: list = []


def kind_of(pickup: UObject) -> str:
    """Money, ammo, health, or gear you would carry away."""
    try:
        tag = str(pickup.Inventory.DefinitionData.ItemDefinition).lower()
    except Exception:
        return "gear"

    if "currency" in tag or "credit" in tag or "money" in tag or "cash" in tag:
        return "money"
    if "healthdrops" in tag or "health" in tag or "medkit" in tag:
        return "health"
    if "ammodrop" in tag or "ammo" in tag:
        return "ammo"
    return "gear"


def wanted(kind: str) -> bool:
    if kind == "money":
        return LootMoney.value is True
    if kind == "ammo":
        return LootAmmo.value is True
    if kind == "health":
        return LootHealth.value is True
    return LootWeapons.value is True


def on_foot() -> UObject | None:
    """You, when you are walking. Nothing when you are in a vehicle."""
    pc = get_pc()
    if pc is None:
        return None

    pawn = getattr(pc, "Pawn", None)
    if pawn is None:
        return None

    # In a vehicle the pawn is the vehicle itself, which knows who is driving it.
    if getattr(pawn, "Driver", None) is not None:
        return None

    return pawn


@hook(hook_func="Engine.GameViewportClient:PostRender", hook_type=Type.POST)
def on_render(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    global frames, waiting_on

    me = on_foot()
    if me is None:
        waiting_on = []
        return

    frames += 1
    if frames >= REFRESH_FRAMES:
        frames = 0
        try:
            waiting_on = list(unrealsdk.find_all("WillowPickup"))
        except Exception:
            waiting_on = []

    if not waiting_on:
        return

    batch = waiting_on[:BATCH]
    del waiting_on[:BATCH]

    try:
        here = me.Location
    except Exception:
        return

    reach = Reach.value * UNITS_PER_METRE

    for pickup in batch:
        try:
            if pickup.bPickupable is not True or pickup.Inventory is None:
                continue

            spot = pickup.Location
            gap = (
                (float(spot.X) - float(here.X)) ** 2
                + (float(spot.Y) - float(here.Y)) ** 2
                + (float(spot.Z) - float(here.Z)) ** 2
            ) ** 0.5
            if gap > reach:
                continue

            kind = kinds.get(pickup)
            if kind is None:
                kind = kind_of(pickup)
                kinds[pickup] = kind
            if not wanted(kind):
                continue

            # False leaves what you are holding alone, it just goes in the backpack.
            pickup.GiveTo(me, False)
        except Exception:
            continue


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

build_mod(
    options=[LootWeapons, LootMoney, LootAmmo, LootHealth, Reach],
    keybinds=[],
    hooks=[on_render],
    commands=[],
    settings_file=Path(f"{SETTINGS_DIR}/AutoLoot.json"),
)

logging.info(f"Auto Loot Loaded: {__version__}, {__version_info__}")
