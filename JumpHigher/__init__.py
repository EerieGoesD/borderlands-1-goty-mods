from pathlib import Path

import unrealsdk  # type: ignore
from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import SETTINGS_DIR, build_mod, get_pc, hook
from mods_base.options import BoolOption, SliderOption

# How high the game jumps out of the box.
STOCK_JUMP = 630

FONT = "ui_fonts.font_willowbody_18pt"

# Where the reading sits, in pixels from the top left corner.
READING_LEFT = 30
READING_TOP = 120

# What the game calls being off the ground.
IN_THE_AIR = 2

JumpHeight = SliderOption(f"Jump Height (default = {STOCK_JUMP})", STOCK_JUMP, 200, 10000, 10, True)
ShowJump = BoolOption("Show jump height [DEBUG]", False, "Yes", "No")

font = None
white = None

# Where you left the ground, and the highest you got, so the jump can be measured.
took_off = None
peak = 0.0
last_jump = 0.0


@hook(hook_func="Engine.GameViewportClient:PostRender", hook_type=Type.POST)
def on_render(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    """Holds your jump at whatever the slider says."""
    global font, white, took_off, peak, last_jump

    pc = get_pc()
    if pc is None or pc.Pawn is None:
        return

    try:
        wanted = float(JumpHeight.value)
        if abs(float(pc.Pawn.JumpZBaseValue) - wanted) > 0.5:
            pc.Pawn.JumpZBaseValue = wanted
        if abs(float(pc.Pawn.JumpZ) - wanted) > 0.5:
            pc.Pawn.JumpZ = wanted
    except Exception as ex:
        logging.dev_warning(f"[Jump Higher] could not set the jump ({ex})")

    if ShowJump.value is False:
        return

    canvas = __args.Canvas
    if canvas is None:
        return

    try:
        height = float(pc.Pawn.Location.Z)

        if int(pc.Pawn.Physics) == IN_THE_AIR:
            if took_off is None:
                took_off = height
                peak = height
            elif height > peak:
                peak = height
        elif took_off is not None:
            last_jump = peak - took_off
            took_off = None

        if font is None:
            font = unrealsdk.find_object("Font", FONT)
            white = unrealsdk.make_struct("Color", R=255, G=255, B=255, A=255)

        now = peak - took_off if took_off is not None else last_jump

        canvas.Font = font
        canvas.DrawColor = white
        canvas.SetPos(READING_LEFT, READING_TOP)
        canvas.DrawText(
            f"jump {now:.0f}   strength {float(pc.Pawn.JumpZ):.0f}",
            False,
            1.0,
            1.0,
        )
    except Exception as ex:
        logging.dev_warning(f"[Jump Higher] could not draw the jump ({ex})")


def on_disable() -> None:
    """Back to the jump the game came with."""
    global took_off

    took_off = None

    pc = get_pc()
    if pc is None or pc.Pawn is None:
        return

    try:
        pc.Pawn.JumpZBaseValue = float(STOCK_JUMP)
        pc.Pawn.JumpZ = float(STOCK_JUMP)
    except Exception as ex:
        logging.dev_warning(f"[Jump Higher] could not put the jump back ({ex})")


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

build_mod(
    options=[JumpHeight, ShowJump],
    keybinds=[],
    hooks=[on_render],
    commands=[],
    settings_file=Path(f"{SETTINGS_DIR}/JumpHigher.json"),
)

logging.info(f"Jump Higher Loaded: {__version__}, {__version_info__}")
