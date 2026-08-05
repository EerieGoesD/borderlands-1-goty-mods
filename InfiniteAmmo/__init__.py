from pathlib import Path

from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import SETTINGS_DIR, build_mod, get_pc, hook
from mods_base.options import BoolOption

# Frames between checks. The game only clears this on its own now and then.
REFRESH_FRAMES = 30

NoReload = BoolOption("No Reload", False, "Yes", "No")

frames = REFRESH_FRAMES


def set_it(on: bool) -> None:
    pc = get_pc()
    if pc is None or pc.Pawn is None:
        return

    try:
        manager = pc.Pawn.InvManager
        if manager is not None and bool(manager.bInfiniteAmmo) is not on:
            manager.bInfiniteAmmo = on
    except Exception as ex:
        logging.dev_warning(f"[Infinite Ammo] could not set the ammo ({ex})")


def top_up() -> None:
    """Keeps the magazine full, so a reload is never called for."""
    pc = get_pc()
    if pc is None or pc.Pawn is None:
        return

    try:
        gun = pc.Pawn.Weapon
        if gun is None:
            return
        full = int(gun.ClipSize)
        if int(gun.ReloadCnt) < full:
            gun.ReloadCnt = full
    except Exception as ex:
        logging.dev_warning(f"[Infinite Ammo] could not fill the magazine ({ex})")


@hook(hook_func="Engine.GameViewportClient:PostRender", hook_type=Type.POST)
def on_render(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    global frames

    if NoReload.value is True:
        top_up()

    frames += 1
    if frames < REFRESH_FRAMES:
        return
    frames = 0

    set_it(True)


def on_disable() -> None:
    """Back to spending ammo the way the game does."""
    set_it(False)


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

build_mod(
    options=[NoReload],
    keybinds=[],
    hooks=[on_render],
    commands=[],
    settings_file=Path(f"{SETTINGS_DIR}/InfiniteAmmo.json"),
)

logging.info(f"Infinite Ammo Loaded: {__version__}, {__version_info__}")
