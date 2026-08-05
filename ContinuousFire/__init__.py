from pathlib import Path

from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import SETTINGS_DIR, build_mod, get_pc, hook

# 0 means the gun never stops to wait for another click.
NO_BURST = 0


@hook(hook_func="Engine.GameViewportClient:PostRender", hook_type=Type.POST)
def on_render(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    """Takes the pause out of whichever gun you are holding.

    Only the number in use is written, never the gun's own one, so putting the mod
    away gives the gun its bursts back.
    """
    pc = get_pc()
    if pc is None or pc.Pawn is None:
        return

    try:
        gun = pc.Pawn.Weapon
        if gun is None:
            return
        if int(gun.AutomaticBurstCount) != NO_BURST:
            gun.AutomaticBurstCount = NO_BURST
    except Exception as ex:
        logging.dev_warning(f"[Continuous Fire] could not settle the gun ({ex})")


def on_disable() -> None:
    """Back to the bursts the gun came with."""
    pc = get_pc()
    if pc is None or pc.Pawn is None:
        return

    try:
        gun = pc.Pawn.Weapon
        if gun is not None:
            gun.AutomaticBurstCount = int(gun.AutomaticBurstCountBaseValue)
    except Exception as ex:
        logging.dev_warning(f"[Continuous Fire] could not put the gun back ({ex})")


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

build_mod(
    options=[],
    keybinds=[],
    hooks=[on_render],
    commands=[],
    on_disable=on_disable,
    settings_file=Path(f"{SETTINGS_DIR}/ContinuousFire.json"),
)

logging.info(f"Continuous Fire Loaded: {__version__}, {__version_info__}")
