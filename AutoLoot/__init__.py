import time
from pathlib import Path

import unrealsdk  # type: ignore
from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import SETTINGS_DIR, build_mod, get_pc, hook
from mods_base.options import BoolOption, SliderOption

# The game measures in its own units. Fifty of them make a metre.
UNITS_PER_METRE = 50.0

Reach = SliderOption("Reach in metres", 5, 1, 20, 1, True)
# Each look walks every object in the area, so more often shows as stutter.
ChecksPerSecond = SliderOption(
    "Checks per second",
    1,
    1,
    10,
    1,
    True,
    description="How often loot around you is looked for. Lower is better for performance.",
)
LootAmmo = BoolOption("Loot Ammo", True, "Yes", "No")
LootHealth = BoolOption("Loot Health", True, "Yes", "No")
LootMoney = BoolOption("Loot Money", True, "Yes", "No")
LootWeapons = BoolOption("Loot Weapons", True, "Yes", "No")

# When loot was last looked for, so the slider means seconds whatever the frame rate.
last_look = 0.0



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
    global last_look

    me = on_foot()
    if me is None:
        return

    now = time.monotonic()
    if now - last_look < 1.0 / max(int(ChecksPerSecond.value), 1):
        return
    last_look = now

    try:
        here = me.Location
    except Exception:
        return

    reach = Reach.value * UNITS_PER_METRE

    # Everything is looked at here and now. Holding on to a pickup between frames
    # takes the game down, since the game frees it the moment somebody takes it.
    for pickup in unrealsdk.find_all("WillowPickup"):
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

            kind = kind_of(pickup)
            if not wanted(kind):
                continue

            # Ammo, money and health you are already full up on are left alone,
            # asked the way the game asks it.
            if pickup.Inventory.CanBeUsedBy(me) is not True:
                continue

            # False leaves what you are holding alone, it just goes in the backpack.
            pickup.GiveTo(me, False)
        except Exception:
            continue


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

build_mod(
    options=[LootWeapons, LootMoney, LootAmmo, LootHealth, Reach, ChecksPerSecond],
    keybinds=[],
    hooks=[on_render],
    commands=[],
    settings_file=Path(f"{SETTINGS_DIR}/AutoLoot.json"),
)

logging.info(f"Auto Loot Loaded: {__version__}, {__version_info__}")
