from pathlib import Path

from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import SETTINGS_DIR, build_mod, get_pc, hook
from mods_base.options import SliderOption

# How often the size is looked at again, in frames.
REFRESH_FRAMES = 60

Slots = SliderOption("Backpack slots", 200, 15, 1000, 5, True)

frames = REFRESH_FRAMES

# The size this character had before the mod touched it, so turning the mod off
# does not throw away backpack upgrades.
original: int | None = None


@hook(hook_func="Engine.GameViewportClient:PostRender", hook_type=Type.POST)
def on_render(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    """Holds the backpack at the size the slider says."""
    global frames

    frames += 1
    if frames < REFRESH_FRAMES:
        return
    frames = 0

    pc = get_pc()
    if pc is None or pc.Pawn is None:
        return

    global original

    try:
        manager = pc.Pawn.InvManager
        if manager is None:
            return
        wanted = int(Slots.value)
        now = int(manager.InventorySlotMax_Misc)
        if now != wanted:
            if original is None and now != wanted:
                original = now
            manager.InventorySlotMax_Misc = wanted
    except Exception as ex:
        logging.dev_warning(f"[No Backpack Limit] could not set the size ({ex})")


def on_enable() -> None:
    """Forgets any size remembered from a previous character."""
    global original
    original = None


def on_disable() -> None:
    """Back to the size this character had, upgrades included."""
    global original

    if original is None:
        return

    pc = get_pc()
    if pc is None or pc.Pawn is None:
        return

    try:
        manager = pc.Pawn.InvManager
        if manager is not None:
            manager.InventorySlotMax_Misc = original
    except Exception as ex:
        logging.dev_warning(f"[No Backpack Limit] could not put the size back ({ex})")
    original = None


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

build_mod(
    options=[Slots],
    keybinds=[],
    hooks=[on_render],
    commands=[],
    on_enable=on_enable,
    on_disable=on_disable,
    settings_file=Path(f"{SETTINGS_DIR}/NoBackpackLimit.json"),
)

logging.info(f"No Backpack Limit Loaded: {__version__}, {__version_info__}")
