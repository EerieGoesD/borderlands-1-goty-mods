import math
from pathlib import Path

import unrealsdk  # type: ignore
from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import SETTINGS_DIR, build_mod, get_pc, hook
from mods_base.options import BoolOption, SliderOption

# What the game moves you at out of the box.
STOCK_WALK = 440
STOCK_RUN = 594
STOCK_AIM = 293
STOCK_CROUCH = 176
STOCK_CAR = 2200

FONT = "ui_fonts.font_willowbody_18pt"

# Where the reading sits, in pixels from the top left corner.
SPEED_LEFT = 30
SPEED_TOP = 120

WalkSpeed = SliderOption(f"Walking (default = {STOCK_WALK})", STOCK_WALK, 100, 4000, 10, True)
RunSpeed = SliderOption(f"Running (default = {STOCK_RUN})", STOCK_RUN, 100, 4000, 10, True)
AimSpeed = SliderOption(f"Aiming (default = {STOCK_AIM})", STOCK_AIM, 100, 4000, 10, True)
CrouchSpeed = SliderOption(
    f"Crouching (default = {STOCK_CROUCH})",
    STOCK_CROUCH,
    50,
    4000,
    10,
    True,
)
CarSpeed = SliderOption(f"Driving (default = {STOCK_CAR})", STOCK_CAR, 500, 3500, 10, True)
ShowSpeed = BoolOption("Show movement speed [DEBUG]", False, "Yes", "No")

font = None
white = None


def driving(pawn: UObject) -> bool:
    """Whether what you are moving is a car rather than yourself."""
    try:
        return pawn.Wheels is not None and len(pawn.Wheels) > 0
    except Exception:
        return False


@hook(hook_func="Engine.GameViewportClient:PostRender", hook_type=Type.POST)
def on_render(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    """Holds your speed at whatever the sliders say, whichever way you are moving."""
    pc = get_pc()
    if pc is None or pc.Pawn is None:
        return

    # Behind the wheel it is the car being moved, not you.
    if driving(pc.Pawn):
        try:
            wanted = float(CarSpeed.value)
            if abs(float(pc.Pawn.PlayerSpeed) - wanted) > 0.5:
                pc.Pawn.PlayerSpeed = wanted
            if float(pc.Pawn.MaxSpeed) < wanted:
                pc.Pawn.MaxSpeed = wanted
        except Exception as ex:
            logging.dev_warning(f"[Movement Speed Changer] could not set the driving speed ({ex})")
    else:
        try:
            if bool(pc.Pawn.bIsCrouched):
                # Crouching cuts the speed by its own share on top of this number,
                # so the number is raised to cancel that out.
                share = float(pc.Pawn.CrouchedPct)
                wanted = (
                    float(CrouchSpeed.value) / share if share > 0 else float(CrouchSpeed.value)
                )
            elif pc.IsZoomed() is True:
                wanted = float(AimSpeed.value)
            elif bool(pc.Pawn.bIsSprinting):
                wanted = float(RunSpeed.value)
            else:
                wanted = float(WalkSpeed.value)

            # The game, and the Run And Walk mod, both fall back on the base number,
            # so it is held at the same place as the one in use.
            if abs(float(pc.Pawn.GroundSpeedBaseValue) - wanted) > 0.5:
                pc.Pawn.GroundSpeedBaseValue = wanted

            if abs(float(pc.Pawn.GroundSpeed) - wanted) > 0.5:
                pc.Pawn.GroundSpeed = wanted
        except Exception as ex:
            logging.dev_warning(f"[Movement Speed Changer] could not set the speed ({ex})")

    if ShowSpeed.value is False:
        return

    canvas = __args.Canvas
    if canvas is None:
        return

    global font, white

    try:
        if font is None:
            font = unrealsdk.find_object("Font", FONT)
            white = unrealsdk.make_struct("Color", R=255, G=255, B=255, A=255)

        speed = pc.Pawn.Velocity
        moving = math.sqrt(float(speed.X) ** 2 + float(speed.Y) ** 2)

        if driving(pc.Pawn):
            state = "driving"
            top = float(pc.Pawn.PlayerSpeed)
        elif bool(pc.Pawn.bIsCrouched):
            state = "crouching"
            top = float(pc.Pawn.GroundSpeed)
        elif pc.IsZoomed() is True:
            state = "aiming"
            top = float(pc.Pawn.GroundSpeed)
        elif bool(pc.Pawn.bIsSprinting):
            state = "running"
            top = float(pc.Pawn.GroundSpeed)
        else:
            state = "walking"
            top = float(pc.Pawn.GroundSpeed)

        canvas.Font = font
        canvas.DrawColor = white
        canvas.SetPos(SPEED_LEFT, SPEED_TOP)
        canvas.DrawText(f"{state}  {moving:.0f} / {top:.0f}", False, 1.0, 1.0)
    except Exception as ex:
        logging.dev_warning(f"[Movement Speed Changer] could not draw the speed ({ex})")


def on_disable() -> None:
    """Back to the speeds the game came with."""
    pc = get_pc()
    if pc is None or pc.Pawn is None:
        return

    try:
        if driving(pc.Pawn):
            pc.Pawn.PlayerSpeed = float(STOCK_CAR)
        else:
            pc.Pawn.GroundSpeedBaseValue = float(STOCK_WALK)
            pc.Pawn.GroundSpeed = float(STOCK_WALK)
    except Exception as ex:
        logging.dev_warning(f"[Movement Speed Changer] could not put the speed back ({ex})")


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

build_mod(
    options=[WalkSpeed, RunSpeed, AimSpeed, CrouchSpeed, CarSpeed, ShowSpeed],
    keybinds=[],
    hooks=[on_render],
    commands=[],
    settings_file=Path(f"{SETTINGS_DIR}/MovementSpeedChanger.json"),
)

logging.info(f"Movement Speed Changer Loaded: {__version__}, {__version_info__}")
