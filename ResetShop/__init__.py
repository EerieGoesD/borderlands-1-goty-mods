import math
from pathlib import Path

import unrealsdk  # type: ignore
from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import SETTINGS_DIR, build_mod, get_pc, hook, keybind

LABEL = "Reset Shop"

# What the game calls a shop.
SHOP = "WillowVendingMachine"

# How close a shop has to be to count as one you are standing at, in the game's units
# (about a centimetre each). Shops stand side by side, so this takes in the whole row.
NEAR = 2000.0


def shops_near(pc) -> list:
    """Every shop close to you, looked up fresh each time."""
    spot = pc.Pawn.Location
    near = []
    for shop in unrealsdk.find_all(SHOP):
        try:
            if str(shop.Name).startswith("Default__"):
                continue
            if shop.bDeleteMe is True:
                continue
            where = shop.Location
            distance = math.sqrt(
                (float(where.X) - float(spot.X)) ** 2
                + (float(where.Y) - float(spot.Y)) ** 2
                + (float(where.Z) - float(spot.Z)) ** 2
            )
            if distance <= NEAR:
                near.append(shop)
        except Exception:
            continue
    return near


def reset_near() -> bool:
    """Fills the shops you are standing at with new items, the game's own way.

    Returns whether any shop was reset.
    """
    pc = get_pc()
    if pc is None or pc.Pawn is None:
        return False

    near = shops_near(pc)
    if not near:
        logging.info(f"[{LABEL}] no shop near you")
        return False

    done = False
    for shop in near:
        try:
            pc.ServerPlayerResetShop(shop)
            logging.info(f"[{LABEL}] reset {shop.Name}")
            done = True
        except Exception as ex:
            logging.dev_warning(f"[{LABEL}] could not reset {shop.Name} ({ex})")
    return done


@keybind("Reset Shop", "F9")
def on_reset() -> None:
    reset_near()


@hook(hook_func="WillowGame.VendingMachineGFxMovie:HandleInputKey", hook_type=Type.PRE)
def on_shop_key(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    """The shop screen keeps keys to itself, so the key is caught there too, and the
    screen's list is filled again with the new items."""
    try:
        if on_reset.key is None or str(__args.ukey) != on_reset.key:
            return
        if int(getattr(__args.uevent, "value", __args.uevent)) != 0:
            return
    except Exception:
        return
    if reset_near():
        try:
            obj.RefreshVendingMachine(True)
        except Exception as ex:
            logging.dev_warning(f"[{LABEL}] could not refresh the shop screen ({ex})")


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

build_mod(
    options=[],
    keybinds=[on_reset],
    hooks=[on_shop_key],
    commands=[],
    settings_file=Path(f"{SETTINGS_DIR}/ResetShop.json"),
)

logging.info(f"Reset Shop Loaded: {__version__}, {__version_info__}")
