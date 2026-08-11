from pathlib import Path

import unrealsdk  # type: ignore
from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import SETTINGS_DIR, build_mod, get_pc, hook, keybind
from mods_base.options import BoolOption, SliderOption

# What the game calls a car you are sitting in.
VEHICLE = "WillowVehicle"

FONT = "ui_fonts.font_willowbody_18pt"

# Where the reading sits, in pixels from the top left corner.
READING_LEFT = 30
READING_TOP = 120

JumpHeight = SliderOption("Jump Height", 800, 200, 10000, 10, True)
ShowJump = BoolOption("Show jump height [DEBUG]", False, "Yes", "No")

# Push squared per unit of height. The starting number is only a first guess; every
# jump measures the real one and corrects it.
push_per_height = 5920.0


def push_for(height: float) -> float:
    """The push that gets the car that many units off the ground."""
    return (height * push_per_height) ** 0.5


def learn(asked: float, got: float) -> None:
    """Corrects the guess from a jump that has just finished."""
    global push_per_height

    if asked <= 0 or got <= 1:
        return

    # A single odd reading should not throw the whole thing off.
    change = min(2.0, max(0.5, asked / got))
    push_per_height = min(50000.0, max(1.0, push_per_height * change))

font = None
white = None

# Where the car left the ground, and the highest it got, so the jump can be measured.
took_off = None
peak = 0.0
last_jump = 0.0

# The car's own top speed, kept so it can be put back after a jump.
stock_top_speed = None

# True once the wheels have actually left the ground on this jump.
in_the_air = False


def in_a_vehicle(pawn) -> bool:
    try:
        return VEHICLE in str(pawn.Class.Name)
    except Exception:
        return False


@keybind("Vehicle Jump", "SpaceBar")
def on_jump() -> None:
    """Throws the vehicle upwards."""
    global took_off, peak, in_the_air

    pc = get_pc()
    if pc is None or pc.Pawn is None:
        return

    if not in_a_vehicle(pc.Pawn):
        return

    # One jump at a time, so holding the key does not stack pushes.
    if took_off is not None:
        return
    try:
        if not bool(pc.Pawn.bVehicleOnGround):
            return
    except Exception:
        pass

    push = push_for(float(JumpHeight.value))

    # A car is a physics body, so its own Velocity field is not what moves it.
    try:
        mesh = pc.Pawn.Mesh
        if mesh is None:
            return

        # The car's own top speed holds the jump down, so it is lifted out of the way
        # for the jump and put back on landing.
        global stock_top_speed
        if stock_top_speed is None:
            stock_top_speed = float(pc.Pawn.MaxSpeed)
        pc.Pawn.MaxSpeed = 1000000.0

        up = unrealsdk.make_struct("Vector", X=0.0, Y=0.0, Z=push)
        here = unrealsdk.make_struct("Vector", X=0.0, Y=0.0, Z=0.0)
        mesh.AddImpulse(up, here, "", True)
        took_off = float(pc.Pawn.Location.Z)
        peak = took_off
        in_the_air = False
    except Exception as ex:
        logging.dev_warning(f"[Vehicle Jump] could not jump ({ex})")


@hook(hook_func="Engine.GameViewportClient:PostRender", hook_type=Type.POST)
def on_render(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    """Watches the jump, puts the car's top speed back, and writes the reading."""
    global font, white, took_off, peak, last_jump, stock_top_speed, in_the_air

    pc = get_pc()
    if pc is None or pc.Pawn is None or not in_a_vehicle(pc.Pawn):
        return

    try:
        height = float(pc.Pawn.Location.Z)

        if took_off is not None:
            if height > peak:
                peak = height

            on_ground = False
            try:
                on_ground = bool(pc.Pawn.bVehicleOnGround)
            except Exception:
                on_ground = height <= took_off + 1.0

            if not on_ground:
                in_the_air = True

            if in_the_air and on_ground:
                last_jump = peak - took_off
                took_off = None
                in_the_air = False
                learn(float(JumpHeight.value), last_jump)
                if stock_top_speed is not None:
                    pc.Pawn.MaxSpeed = stock_top_speed
                    stock_top_speed = None
    except Exception as ex:
        logging.dev_warning(f"[Vehicle Jump] could not measure the jump ({ex})")
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
        logging.dev_warning(f"[Vehicle Jump] could not draw the jump ({ex})")


def on_enable() -> None:
    """Starts fresh, so an odd jump earlier cannot follow you around."""
    global took_off, push_per_height, in_the_air

    took_off = None
    in_the_air = False
    push_per_height = 5920.0


def on_disable() -> None:
    """Puts the car's top speed back if the mod is turned off mid-jump."""
    global took_off, stock_top_speed

    took_off = None

    if stock_top_speed is None:
        return

    pc = get_pc()
    if pc is not None and pc.Pawn is not None and in_a_vehicle(pc.Pawn):
        try:
            pc.Pawn.MaxSpeed = stock_top_speed
        except Exception as ex:
            logging.dev_warning(f"[Vehicle Jump] could not put the top speed back ({ex})")
    stock_top_speed = None


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

build_mod(
    options=[JumpHeight, ShowJump],
    keybinds=[on_jump],
    hooks=[on_render],
    commands=[],
    on_enable=on_enable,
    on_disable=on_disable,
    settings_file=Path(f"{SETTINGS_DIR}/VehicleJump.json"),
)

logging.info(f"Vehicle Jump Loaded: {__version__}, {__version_info__}")
