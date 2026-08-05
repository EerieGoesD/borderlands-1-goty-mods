from pathlib import Path

from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import SETTINGS_DIR, build_mod, get_pc, hook


@hook(hook_func="Engine.GameViewportClient:PostRender", hook_type=Type.POST)
def on_render(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
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
        logging.dev_warning(f"[No Reload] could not fill the magazine ({ex})")


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

build_mod(
    options=[],
    keybinds=[],
    hooks=[on_render],
    commands=[],
    settings_file=Path(f"{SETTINGS_DIR}/NoReload.json"),
)

logging.info(f"No Reload Loaded: {__version__}, {__version_info__}")
