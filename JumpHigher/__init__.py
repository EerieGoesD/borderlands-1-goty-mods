from pathlib import Path

import unrealsdk  # type: ignore
from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import SETTINGS_DIR, build_mod, get_pc, hook
from mods_base.options import BoolOption, SliderOption

# The push the game gives you out of the box.
STOCK_JUMP = 630

# Push squared per unit of height. The starting number is only a first guess; every
# jump measures the real one and corrects it.
push_per_height = 2000.0


def push_for(height: float) -> float:
    """The push that gets you that many units off the ground."""
    return (height * push_per_height) ** 0.5


def learn(asked: float, got: float) -> None:
    """Corrects the guess from a jump that has just finished."""
    global push_per_height

    if asked <= 0 or got <= 1:
        return

    # A single odd reading should not throw the whole thing off.
    change = min(100.0, max(0.01, asked / got))
    push_per_height = min(50000.0, max(1.0, push_per_height * change))


FONT = "ui_fonts.font_willowbody_18pt"

# Where the reading sits, in pixels from the top left corner.
READING_LEFT = 30
READING_TOP = 120

# What the game calls being off the ground.
IN_THE_AIR = 2

JumpHeight = SliderOption("Jump Height", 190, 10, 10000, 10, True)
ShowJump = BoolOption("Show jump height [DEBUG]", False, "Yes", "No")

font = None
white = None

# Where you left the ground, and the highest you got, so the jump can be measured.
took_off = None
peak = 0.0
last_jump = 0.0

# The area's own speed limit, kept so it can be put back.
stock_top_speed = None


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

    global stock_top_speed

    try:
        wanted = push_for(float(JumpHeight.value))
        if abs(float(pc.Pawn.JumpZBaseValue) - wanted) > 0.5:
            pc.Pawn.JumpZBaseValue = wanted
        if abs(float(pc.Pawn.JumpZ) - wanted) > 0.5:
            pc.Pawn.JumpZ = wanted

        # The area's own speed limit cuts the jump short, so it is lifted out of the
        # way while the mod is on and put back when it is turned off.
        volume = pc.Pawn.PhysicsVolume
        if volume is not None:
            room = wanted * 2.0
            if float(volume.TerminalVelocity) < room:
                if stock_top_speed is None:
                    stock_top_speed = (volume, float(volume.TerminalVelocity))
                volume.TerminalVelocity = room
    except Exception as ex:
        logging.dev_warning(f"[Jump Higher] could not set the jump ({ex})")

    # Every jump is measured, so the height on the slider is the height you get.
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
            learn(float(JumpHeight.value), last_jump)
    except Exception as ex:
        logging.dev_warning(f"[Jump Higher] could not measure the jump ({ex})")
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
    """Starts a fresh jump, keeping what has already been measured."""
    global took_off

    took_off = None


def on_disable() -> None:
    """Back to the jump the game came with."""
    global took_off, stock_top_speed

    took_off = None

    if stock_top_speed is not None:
        volume, was = stock_top_speed
        try:
            volume.TerminalVelocity = was
        except Exception:
            pass
        stock_top_speed = None

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
