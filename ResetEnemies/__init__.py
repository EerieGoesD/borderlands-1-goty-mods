from pathlib import Path

import unrealsdk  # type: ignore
from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import SETTINGS_DIR, build_mod, get_pc, hook
from mods_base.options import ButtonOption

# What the game calls a spot that enemies come out of.
DEN = "PopulationOpportunityDen"

# What the game calls an enemy.
ENEMY = "WillowAIPawn"

# How long to wait after you close the menu before starting, in frames.
SETTLING = 30

# Frames left to wait.
waiting = 0


def master():
    """The thing that does the spawning."""
    for found in unrealsdk.find_all("WillowPopulationMaster"):
        if not str(found.Name).startswith("Default__"):
            return found
    return None


def clear_the_dead() -> None:
    """Takes the dead out of the way.

    Every one of them is dealt with here and now. Keeping one until the next frame
    takes the game down, since the game is free to let go of it in between.
    """
    for body in unrealsdk.find_all(ENEMY):
        try:
            if str(body.Name).startswith("Default__"):
                continue
            if body.bDeleteMe is True or body.bPendingDelete is True:
                continue
            if body.bIsDead is not True:
                continue

            # The game will not let go of a body, so it is taken off screen
            # and made unable to touch anything.
            body.bHidden = True
            body.SetCollision(False, False)
            mesh = getattr(body, "Mesh", None)
            if mesh is not None:
                mesh.SetHidden(True)
        except Exception:
            continue


def fill_the_dens() -> None:
    """Tells every spawn point in the area to send its enemies out again.

    The same goes here: every spot is told here and now, never a frame later.
    """
    spawner = master()
    if spawner is None:
        return

    for den in unrealsdk.find_all(DEN):
        try:
            if str(den.Name).startswith("Default__"):
                continue
            if den.bDeleteMe is True or den.bPendingDelete is True:
                continue

            # The spot keeps a tally of everything it has ever sent out and a time
            # it is not allowed to send anything before. Both are wound back so it
            # treats the area as untouched.
            tally = den.SpawnData

            # A spot with no enemy type set, or no room for any, is not a real
            # spawn point. Telling one of those to spawn takes the game down.
            if str(tally.PopulationDefName) in ("", "None"):
                continue
            if int(tally.MaxActiveActors) <= 0:
                continue

            tally.NextSpawnTime = 0.0
            tally.NumTotalActors = 0
            den.SpawnData = tally

            den.bNoRespawning = False
            den.DoSpawning(spawner)
        except Exception as ex:
            logging.dev_warning(f"[Reset Enemies] {den.Name} would not fill ({ex})")
            continue


def reset_the_area(option: ButtonOption) -> None:
    """Lines the area up to be filled again once the menu is out of the way."""
    global waiting

    waiting = SETTLING


ResetNow = ButtonOption(
    "Reset Current Area",
    on_press=reset_the_area,
    description="Close the menu and the enemies come back at their own spawn points.",
)


@hook(hook_func="Engine.GameViewportClient:PostRender", hook_type=Type.POST)
def on_render(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    """Does the work once the menu is out of the way, all in one frame."""
    global waiting

    if waiting <= 0:
        return

    pc = get_pc()
    if pc is None or pc.Pawn is None:
        return

    try:
        if pc.bStatusMenuOpen is True:
            return
    except Exception:
        pass

    waiting -= 1
    if waiting > 0:
        return

    clear_the_dead()
    fill_the_dens()


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
