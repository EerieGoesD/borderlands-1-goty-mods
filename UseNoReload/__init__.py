from pathlib import Path

from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Block, Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import SETTINGS_DIR, build_mod, hook


@hook(hook_func="WillowGame.WillowPlayerController:Behavior_Reload", hook_type=Type.PRE)
def on_use_reload(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> type[Block] | None:
    """The reload the use key sets off. The reload key goes a different way."""
    return Block


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

build_mod(
    options=[],
    keybinds=[],
    hooks=[on_use_reload],
    commands=[],
    settings_file=Path(f"{SETTINGS_DIR}/UseNoReload.json"),
)

logging.info(f"Use No Reload Loaded: {__version__}, {__version_info__}")
