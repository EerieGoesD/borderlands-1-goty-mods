from pathlib import Path

import unrealsdk  # type: ignore
from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import SETTINGS_DIR, build_mod, get_pc, hook
from mods_base.options import ButtonOption

# What the game calls a spot that enemies come out of.
DEN = "PopulationOpportunityDen"

# How long to wait after you close the menu before starting, in frames.
SETTLING = 30

# How many spawn points are told at a time, so the game is not held up.
BATCH = 4

# Frames left to wait, and the spawn points still to be told.
waiting = 0
to_do: list = []


def reset_the_area(option: ButtonOption) -> None:
    """Lines the area up to be filled again once the menu is out of the way."""
    global waiting

    waiting = SETTLING


ResetNow = ButtonOption(
    "Reset Current Area",
    on_press=reset_the_area,
    description="Close the menu, then walk away and back and the enemies are there again.",
)


@hook(hook_func="Engine.GameViewportClient:PostRender", hook_type=Type.POST)
def on_render(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    """Does the work once the menu is closed, a few spawn points at a time."""
    global waiting, to_do

    pc = get_pc()
    if pc is None or pc.Pawn is None:
        return

    try:
        if pc.bStatusMenuOpen is True:
            return
    except Exception:
        pass

    if waiting > 0:
        waiting -= 1
        if waiting == 0:
            try:
                to_do = list(unrealsdk.find_all(DEN))
            except Exception:
                to_do = []
        return

    if not to_do:
        return

    batch = to_do[:BATCH]
    del to_do[:BATCH]

    for den in batch:
        try:
            if den.bDeleteMe is True or den.bPendingDelete is True:
                continue
            den.SetEnabledStatus(True)
            den.Reset()
        except Exception:
            continue


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

build_mod(
    options=[ResetNow],
    keybinds=[],
    hooks=[on_render],
    commands=[],
    settings_file=Path(f"{SETTINGS_DIR}/ResetEnemies.json"),
)

logging.info(f"Reset Enemies Loaded: {__version__}, {__version_info__}")
