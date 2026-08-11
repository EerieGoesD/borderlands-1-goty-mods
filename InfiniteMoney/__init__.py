from pathlib import Path

from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import SETTINGS_DIR, build_mod, get_pc, hook
from mods_base.options import SliderOption

# How often the money is looked at again, in frames.
REFRESH_FRAMES = 30

Amount = SliderOption("Money", 9999999, 1000, 9999999, 1000, True)

frames = REFRESH_FRAMES

# What you had before the mod touched it, so turning the mod off gives it back.
original: int | None = None


def wallet():
    """The record that holds your money, or None."""
    pc = get_pc()
    if pc is None:
        return None
    try:
        return pc.PlayerReplicationInfo
    except Exception:
        return None


@hook(hook_func="Engine.GameViewportClient:PostRender", hook_type=Type.POST)
def on_render(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    """Holds your money at whatever the slider says."""
    global frames, original

    frames += 1
    if frames < REFRESH_FRAMES:
        return
    frames = 0

    pri = wallet()
    if pri is None:
        return

    try:
        wanted = int(Amount.value)
        now = int(pri.CurrencyOnHand)
        if now == wanted:
            return
        if original is None:
            original = now
        pri.CurrencyOnHand = wanted
    except Exception as ex:
        logging.dev_warning(f"[Infinite Money] could not set the money ({ex})")


def on_enable() -> None:
    """Forgets any amount remembered from a previous character."""
    global original
    original = None


def on_disable() -> None:
    """Back to the money you had before."""
    global original

    if original is None:
        return

    pri = wallet()
    if pri is not None:
        try:
            pri.CurrencyOnHand = original
        except Exception as ex:
            logging.dev_warning(f"[Infinite Money] could not put the money back ({ex})")
    original = None


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

build_mod(
    options=[Amount],
    keybinds=[],
    hooks=[on_render],
    commands=[],
    on_enable=on_enable,
    on_disable=on_disable,
    settings_file=Path(f"{SETTINGS_DIR}/InfiniteMoney.json"),
)

logging.info(f"Infinite Money Loaded: {__version__}, {__version_info__}")
