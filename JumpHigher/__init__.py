from pathlib import Path

import unrealsdk  # type: ignore
from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import SETTINGS_DIR, build_mod, get_pc, hook
from mods_base.options import BoolOption, SliderOption

# The push the game gives you out of the box.
STOCK_JUMP = 630

# How high that push gets you, in units.
STOCK_HEIGHT = 240

# How fast you are carried upwards, in units per second. Kept well under what the game
# is happy with, so none of its own limits get in the way.
CLIMB_SPEED = 2500.0

# How sharply the climb eases off near the top, so you stop at the height you asked for.
EASE = 4.0

# How far below the top we let go, in units.
LET_GO = 25.0

# How many frames of no height gained before the push stops, for when you hit a roof.
STUCK_FRAMES = 15

FONT = "ui_fonts.font_willowbody_18pt"

# Where the reading sits, in pixels from the top left corner.
READING_LEFT = 30
READING_TOP = 120

# What the game calls being off the ground.
IN_THE_AIR = 2

JumpHeight = SliderOption("Jump Height", 240, 240, 10000, 10, True)
ShowJump = BoolOption("Show jump height [DEBUG]", False, "Yes", "No")

font = None
white = None

# Where you left the ground, and the highest you got, so the jump can be measured.
ground = 0.0
took_off = None
peak = 0.0
last_jump = 0.0

# True while you are being carried up to the height you asked for.
lifting = False

# The height last seen while lifting, and how long it has not changed.
last_height = 0.0
stuck = 0


@hook(hook_func="Engine.GameViewportClient:PostRender", hook_type=Type.POST)
def on_render(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    """Carries you up to whatever height the slider says."""
    global font, white, ground, took_off, peak, last_jump
    global lifting, last_height, stuck

    pc = get_pc()
    if pc is None or pc.Pawn is None:
        return

    try:
        pawn = pc.Pawn
        height = float(pawn.Location.Z)
        target = float(JumpHeight.value)
        in_air = int(pawn.Physics) == IN_THE_AIR

        if not in_air:
            ground = height
            # The jump itself stays the one the game came with.
            if float(pawn.JumpZBaseValue) != float(STOCK_JUMP):
                pawn.JumpZBaseValue = float(STOCK_JUMP)
            if float(pawn.JumpZ) != float(STOCK_JUMP):
                pawn.JumpZ = float(STOCK_JUMP)
            if took_off is not None:
                last_jump = peak - took_off
                took_off = None
            lifting = False
            stuck = 0
        else:
            if took_off is None:
                took_off = ground
                peak = height
                last_height = height
                stuck = 0
                # A jump no bigger than the game's own is left alone.
                lifting = target > STOCK_HEIGHT

            if height > peak:
                peak = height

            if lifting:
                remaining = target - (height - took_off)

                # A roof, or anything else in the way, stops the push.
                if height <= last_height + 0.5:
                    stuck += 1
                else:
                    stuck = 0
                last_height = height

                if remaining <= LET_GO or stuck > STUCK_FRAMES:
                    lifting = False
                else:
                    speed = min(CLIMB_SPEED, remaining * EASE)
                    velocity = pawn.Velocity
                    if abs(float(velocity.Z) - speed) > 1.0:
                        velocity.Z = speed
                        pawn.Velocity = velocity
    except Exception as ex:
        logging.dev_warning(f"[Jump Higher] could not set the jump ({ex})")
        return

    if ShowJump.value is False:
        return

    canvas = __args.Canvas
    if canvas is None:
        return

    try:
        if font is None:
            font = unrealsdk.find_object("Font", FONT)
            white = unrealsdk.make_struct("Color", R=255, G=255, B=255, A=255)

        now = peak - took_off if took_off is not None else last_jump

        canvas.Font = font
        canvas.DrawColor = white
        canvas.SetPos(READING_LEFT, READING_TOP)
        canvas.DrawText(
            f"jump {now:.0f}   set to {float(JumpHeight.value):.0f}",
            False,
            1.0,
            1.0,
        )
    except Exception as ex:
        logging.dev_warning(f"[Jump Higher] could not draw the jump ({ex})")


def on_enable() -> None:
    """Starts a fresh jump."""
    global took_off, lifting, stuck

    took_off = None
    lifting = False
    stuck = 0


def on_disable() -> None:
    """Back to the jump the game came with."""
    global took_off, lifting

    took_off = None
    lifting = False

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
    on_enable=on_enable,
    keybinds=[],
    hooks=[on_render],
    commands=[],
    on_disable=on_disable,
    settings_file=Path(f"{SETTINGS_DIR}/JumpHigher.json"),
)

logging.info(f"Jump Higher Loaded: {__version__}, {__version_info__}")
