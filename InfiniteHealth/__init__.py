from pathlib import Path

from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import SETTINGS_DIR, build_mod, get_pc, hook

# Frames between checks. The game only clears this on its own now and then.
REFRESH_FRAMES = 30

frames = REFRESH_FRAMES


def set_it(on: bool) -> None:
    pc = get_pc()
    if pc is None or pc.Pawn is None:
        return

    try:
        if bool(pc.Pawn.bIsInvulnerable) is not on:
            pc.Pawn.bIsInvulnerable = on
    except Exception as ex:
        logging.dev_warning(f"[Infinite Health] could not set the health ({ex})")


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

    set_it(True)


def on_disable() -> None:
    """Back to taking damage the way the game does."""
    set_it(False)


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

build_mod(
    options=[],
    keybinds=[],
    hooks=[on_render],
    commands=[],
    settings_file=Path(f"{SETTINGS_DIR}/InfiniteHealth.json"),
)

logging.info(f"Infinite Health Loaded: {__version__}, {__version_info__}")
