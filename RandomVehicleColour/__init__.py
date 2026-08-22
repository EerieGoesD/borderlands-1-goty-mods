from pathlib import Path
from random import choice, randrange

import unrealsdk  # type: ignore
from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Block, Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import SETTINGS_DIR, build_mod, hook
from mods_base.options import BoolOption

PickOnOpen = BoolOption("Pick at the terminal", False, "Yes", "No")

# True while we are doing the painting ourselves, so we do not call it forever.
painting = False

# The colour the tick still needs moving to, and how long it has been waiting. The
# menu builds itself over a few frames, so moving the tick straight away is undone.
waiting = None
waited = 0
SETTLING = 20
REPEAT_EVERY = 10
GIVE_UP = 120

# The colour picked when the terminal opened, or nothing if you have picked your own.
chosen = None

# Frames since the terminal opened, so your own click can be told apart from the
# menu setting itself up.
since_opened = 0


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


def move_the_tick(spot: int) -> None:
    """Puts the terminal's tick on the colour we picked."""
    for menu in unrealsdk.find_all("VehicleSpawnStationGFxMovie"):
        if str(menu.Name).startswith("Default__"):
            continue
        try:
            menu.PrimaryColorIndex = spot
            menu.AS_SetPrimaryColorIndex(spot)
            menu.AS_UpdateColorBox(f"cell{spot + 1}")
        except Exception as ex:
            logging.dev_warning(f"[Random Vehicle Colour] could not move the tick ({ex})")


def opened() -> None:
    """Picks the colour as the terminal opens, so you can see it first."""
    global chosen, waiting, waited, since_opened

    chosen = None
    since_opened = 0

    if PickOnOpen.value is not True:
        return

    try:
        bank = colours()
        if not bank:
            return

        chosen = randrange(len(bank))
        waiting = chosen
        waited = 0
    except Exception as ex:
        logging.dev_warning(f"[Random Vehicle Colour] could not pick a colour ({ex})")


@hook(
    hook_func="WillowGame.WillowPlayerController:StartUsingVehicleSpawnStationTerminal",
    hook_type=Type.POST,
)
def on_walk_up(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    """The way GOTY opens the terminal."""
    opened()


@hook(hook_func="WillowGame.VehicleSpawnStationGFxMovie:Start", hook_type=Type.POST)
def on_menu_up(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    """The way GOTY Enhanced opens the terminal."""
    opened()


@hook(
    hook_func="WillowGame.VehicleSpawnStationGFxMovie:extSetPrimaryColorIndex",
    hook_type=Type.POST,
)
def on_your_pick(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    """Your own click on a swatch wins over the one we offered."""
    global chosen

    if chosen is not None and since_opened > SETTLING:
        chosen = None


@hook(hook_func="Engine.GameViewportClient:PostRender", hook_type=Type.POST)
def on_render(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    """Moves the tick once the menu has had time to finish drawing itself."""
    global waiting, waited, since_opened

    if since_opened <= SETTLING:
        since_opened += 1

    if waiting is None:
        return

    waited += 1
    if waited < SETTLING:
        return

    # The menu redraws itself for a while after it opens, so the tick is put back
    # every so often until it stays put.
    if waited > GIVE_UP:
        waiting = None
        return

    if waited % REPEAT_EVERY == 0:
        move_the_tick(waiting)


@hook(hook_func="WillowGame.WillowVehicle:SetVehicleMaterial", hook_type=Type.PRE)
def on_paint(
    obj: UObject,
    args: WrappedStruct,
    __ret: any,
    func: BoundFunction,
):
    """Paints the car coming out of the Catch-a-Ride."""
    global painting, waiting, waited

    if painting:
        return None

    try:
        bank = colours()
        if not bank:
            return None

        # Anything wearing a colour the Catch-a-Ride does not offer is another
        # kind of vehicle, and painting it wrecks its look.
        was = str(args.MatInst)
        if was not in [str(c.Material) for c in bank]:
            return None

        if PickOnOpen.value is True:
            # You have picked your own since we offered one, so leave it alone.
            if chosen is None:
                return None
            spot = chosen
        else:
            # The one the game picked is left out, so the car always looks different.
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

        if PickOnOpen.value is not True:
            waiting = spot
            waited = SETTLING - 1

        return Block
    except Exception as ex:
        logging.dev_warning(f"[Random Vehicle Colour] could not paint it ({ex})")

    return None


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

build_mod(
    options=[PickOnOpen],
    keybinds=[],
    hooks=[on_walk_up, on_menu_up, on_your_pick, on_render, on_paint],
    commands=[],
    settings_file=Path(f"{SETTINGS_DIR}/RandomVehicleColour.json"),
)

logging.info(f"Random Vehicle Colour Loaded: {__version__}, {__version_info__}")
