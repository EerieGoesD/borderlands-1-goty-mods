from pathlib import Path
from random import choice

import unrealsdk  # type: ignore
from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Block, Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import SETTINGS_DIR, build_mod, hook
from mods_base.options import BoolOption

ShowPaint = BoolOption("Show the paint picked [DEBUG]", False, "Yes", "No")

# True while we are doing the painting ourselves, so we do not call it forever.
painting = False

# The colour the tick still needs moving to, once the game is back to drawing.
waiting = None


def colours() -> list:
    """The Catch-a-Ride's own colours, in the order it shows them."""
    for holder in unrealsdk.find_all("VehicleSpawnStationGFxDefinition"):
        try:
            found = list(holder.VehicleMaterials)
        except Exception:
            continue
        if found:
            return found
    return []


def move_the_tick() -> None:
    """Puts the terminal's tick on the colour the car came out in."""
    global waiting

    spot = waiting
    waiting = None

    for menu in unrealsdk.find_all("VehicleSpawnStationGFxMovie"):
        if str(menu.Name).startswith("Default__"):
            continue
        try:
            menu.PrimaryColorIndex = spot
            menu.AS_SetPrimaryColorIndex(spot)
            menu.AS_UpdateColorBox(f"cell{spot + 1}")
        except Exception as ex:
            logging.dev_warning(f"[Random Vehicle Colour] could not move the tick ({ex})")


@hook(hook_func="Engine.GameViewportClient:PostRender", hook_type=Type.POST)
def on_render(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    """Moves the tick a frame after the car came out, not during the spawn itself."""
    if waiting is not None:
        move_the_tick()


@hook(hook_func="WillowGame.WillowVehicle:SetVehicleMaterial", hook_type=Type.PRE)
def on_paint(
    obj: UObject,
    args: WrappedStruct,
    __ret: any,
    func: BoundFunction,
):
    """Paints the car that just came out of the Catch-a-Ride at random."""
    global painting, waiting

    if painting:
        return None

    try:
        bank = colours()
        if not bank:
            return None

        # The one the game picked is left out, so the car always looks different.
        was = str(args.MatInst)
        spots = [i for i, c in enumerate(bank) if str(c.Material) != was]
        if not spots:
            return None

        spot = choice(spots)
        pick = bank[spot].Material

        painting = True
        try:
            func(pick)
        finally:
            painting = False

        waiting = spot

        if ShowPaint.value is True:
            logging.info(f"[Random Vehicle Colour] painted it {bank[spot].MaterialName}")

        return Block
    except Exception as ex:
        logging.dev_warning(f"[Random Vehicle Colour] could not paint it ({ex})")

    return None


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

build_mod(
    options=[ShowPaint],
    keybinds=[],
    hooks=[on_paint, on_render],
    commands=[],
    settings_file=Path(f"{SETTINGS_DIR}/RandomVehicleColour.json"),
)

logging.info(f"Random Vehicle Colour Loaded: {__version__}, {__version_info__}")
