from pathlib import Path

import unrealsdk  # type: ignore
from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import SETTINGS_DIR, build_mod, get_pc, hook
from mods_base.options import BoolOption, SliderOption

# Frames between sweeps.
REFRESH_FRAMES = 10

# The game measures in its own units. Fifty of them make a metre.
UNITS_PER_METRE = 50.0

Reach = SliderOption("Reach in metres", 8, 2, 20, 1, True)
LootAmmo = BoolOption("Loot Ammo", True, "Yes", "No")
LootMoney = BoolOption("Loot Money", True, "Yes", "No")
LootWeapons = BoolOption("Loot Weapons", True, "Yes", "No")

frames = 0

# What each pickup turned out to be, so its name is only read once.
kinds: dict[UObject, str] = {}


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
    return "gear"


def wanted(kind: str) -> bool:
    if kind == "money":
        return LootMoney.value is True
    if kind == "ammo":
        return LootAmmo.value is True
    return LootWeapons.value is True


DEBUG = False
seen: set[str] = set()


def driver() -> UObject | None:
    """You, when you are behind the wheel. Nothing when you are on foot."""
    pc = get_pc()
    if pc is None:
        return None

    pawn = getattr(pc, "Pawn", None)
    if pawn is None:
        return None

    if DEBUG:
        kind = str(pawn.Class.Name)
        if kind not in seen:
            seen.add(kind)
            fields = [a for a in dir(pawn) if "river" in a or "ehicle" in a]
            logging.info(f"[Vehicle Loot] riding {kind}: {', '.join(sorted(fields))}")

    # In a vehicle the pawn is the vehicle itself, which knows who is driving it.
    return getattr(pawn, "Driver", None)


@hook(hook_func="Engine.GameViewportClient:PostRender", hook_type=Type.POST)
def on_render(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    global frames

    frames += 1
    if frames < REFRESH_FRAMES:
        return
    frames = 0

    me = driver()
    if me is None:
        if DEBUG:
            logging.info("[Vehicle Loot] no driver")
        return

    try:
        here = get_pc().Pawn.Location
    except Exception:
        return

    reach = Reach.value * UNITS_PER_METRE

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

            kind = kinds.get(pickup)
            if kind is None:
                kind = kind_of(pickup)
                kinds[pickup] = kind
            if not wanted(kind):
                continue

            pickup.GiveTo(me, True)
            if DEBUG:
                logging.info(f"[Vehicle Loot] took {pickup.Inventory.Class.Name}")
        except Exception as ex:
            if DEBUG:
                logging.info(f"[Vehicle Loot] could not take ({ex})")
            continue


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

build_mod(
    options=[Reach, LootWeapons, LootMoney, LootAmmo],
    keybinds=[],
    hooks=[on_render],
    commands=[],
    settings_file=Path(f"{SETTINGS_DIR}/VehicleLoot.json"),
)

logging.info(f"Vehicle Loot Loaded: {__version__}, {__version_info__}")
