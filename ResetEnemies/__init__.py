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

# How many spawn points are told at a time, so the game is not held up.
BATCH = 4

# Frames left to wait, the corpses still to be cleared, and the spawn points still
# to be told.
waiting = 0
bodies: list = []
to_do: list = []


def master():
    """The thing that does the spawning."""
    for found in unrealsdk.find_all("WillowPopulationMaster"):
        if not str(found.Name).startswith("Default__"):
            return found
    return None


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
    """Does the work once the menu is closed, a few spawn points at a time."""
    global waiting, bodies, to_do

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
                bodies = list(unrealsdk.find_all(ENEMY))
            except Exception:
                bodies = []
            try:
                to_do = list(unrealsdk.find_all(DEN))
            except Exception:
                to_do = []
        return

    # The bodies you left on the ground are cleared away first.
    if bodies:
        batch = bodies[:BATCH]
        del bodies[:BATCH]

        for body in batch:
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
        return

    if not to_do:
        return

    batch = to_do[:BATCH]
    del to_do[:BATCH]

    spawner = master()
    if spawner is None:
        to_do = []
        return

    for den in batch:
        try:
            if str(den.Name).startswith("Default__"):
                continue
            if den.bDeleteMe is True or den.bPendingDelete is True:
                continue

            # The spot keeps a tally of everything it has ever sent out and a time
            # it is not allowed to send anything before. Both are wound back so it
            # treats the area as untouched.
            tally = den.SpawnData
            tally.NextSpawnTime = 0.0
            tally.NumTotalActors = 0
            den.SpawnData = tally

            den.bNoRespawning = False
            den.DoSpawning(spawner)
        except Exception as ex:
            logging.dev_warning(f"[Reset Enemies] {den.Name} would not fill ({ex})")
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
