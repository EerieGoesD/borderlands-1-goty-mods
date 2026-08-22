import math
from pathlib import Path

import unrealsdk  # type: ignore
from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import SETTINGS_DIR, build_mod, get_pc, hook, keybind
from mods_base.options import SliderOption

# What the game calls walking about and flying through everything.
ON_FOOT = 1
IN_THE_AIR = 2
FLYING = 4

# How long a fall has to last before you are put back where you took off.
LOST = 180

# What the game counts as half a turn, for working out where you are looking.
HALF_TURN = 32768.0

# Roughly how many frames a second the game draws.
FRAMES_A_SECOND = 60.0

FlySpeed = SliderOption("Fly Speed", 2000, 200, 10000, 100, True)

# True from the moment you press the key until you press it again.
flying = False

# Your own speed in the air, so it can be put back.
stock_speed = None

# Where you took off from, in case you land somewhere with no floor under you.
took_off_at = None

# How long you have been falling since you landed.
falling = 0

FONT = "ui_fonts.font_willowbody_18pt"

# Where the reading sits, in pixels from the top left corner.
READING_LEFT = 30
READING_TOP = 90

font = None
white = None


def turn(raw) -> float:
    """The game counts angles round and round, so this brings one back in range."""
    return float((int(raw) + 32768) % 65536 - 32768)


def land(pawn) -> None:
    """Puts you back on your feet."""
    global stock_speed

    pawn.bCollideWorld = True
    pawn.SetCollision(True, True)
    if stock_speed is not None:
        pawn.AirSpeed = stock_speed
        stock_speed = None
    pawn.SetPhysics(ON_FOOT)


@keybind("No Clip", "Z")
def on_toggle() -> None:
    """Turns walking through walls on and off."""
    global flying, stock_speed, took_off_at, falling

    pc = get_pc()
    if pc is None or pc.Pawn is None:
        return

    pawn = pc.Pawn

    try:
        if flying:
            land(pawn)
            flying = False
            falling = 0
            return

        spot = pawn.Location
        took_off_at = (float(spot.X), float(spot.Y), float(spot.Z))
        falling = 0
        stock_speed = float(pawn.AirSpeed)
        pawn.AirSpeed = float(FlySpeed.value)
        pawn.bCollideWorld = False
        pawn.SetCollision(False, False)
        pawn.SetPhysics(FLYING)
        flying = True
    except Exception as ex:
        logging.dev_warning(f"[No Clip] could not switch ({ex})")


@hook(hook_func="Engine.GameViewportClient:PostRender", hook_type=Type.POST)
def on_render(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    """Holds you in the air, catches a fall through the map, and writes the reading."""
    global falling, font, white

    pc = get_pc()
    if pc is None or pc.Pawn is None:
        return

    try:
        pawn = pc.Pawn

        if flying:
            # The game keeps trying to put you back on the ground, so this holds
            # you up and points your movement wherever you are looking.
            if int(pawn.Physics) != FLYING:
                pawn.SetPhysics(FLYING)
            if pawn.bCollideWorld is not False:
                pawn.bCollideWorld = False
                pawn.SetCollision(False, False)

            # Whether you are holding a movement key.
            push = pawn.Acceleration
            pressing = (
                abs(float(push.X)) + abs(float(push.Y)) + abs(float(push.Z)) > 1.0
            )

            # The game's own shoving is switched off, we do the moving.
            still = pawn.Velocity
            still.X = 0.0
            still.Y = 0.0
            still.Z = 0.0
            pawn.Velocity = still

            if pressing:
                look = pc.Rotation
                pitch = turn(look.Pitch) * math.pi / HALF_TURN
                yaw = turn(look.Yaw) * math.pi / HALF_TURN

                # How much of the key you are holding is forwards and how much
                # is sideways, worked out from where you are facing.
                ahead = math.cos(yaw)
                across = math.sin(yaw)
                forwards = float(push.X) * ahead + float(push.Y) * across
                sideways = -float(push.X) * across + float(push.Y) * ahead

                # Forwards follows your aim, sideways stays level.
                flat = math.cos(pitch)
                x = flat * ahead * forwards - across * sideways
                y = flat * across * forwards + ahead * sideways
                z = math.sin(pitch) * forwards

                length = math.sqrt(x * x + y * y + z * z)
                if length > 0.0:
                    step = float(FlySpeed.value) / FRAMES_A_SECOND / length
                    spot = pawn.Location
                    pawn.Location = unrealsdk.make_struct(
                        "Vector",
                        X=float(spot.X) + x * step,
                        Y=float(spot.Y) + y * step,
                        Z=float(spot.Z) + z * step,
                    )

            falling = 0
        elif took_off_at is not None and int(pawn.Physics) == IN_THE_AIR:
            falling += 1
            if falling >= LOST:
                falling = 0
                x, y, z = took_off_at
                pawn.Location = unrealsdk.make_struct("Vector", X=x, Y=y, Z=z)
                pawn.Velocity = unrealsdk.make_struct("Vector", X=0.0, Y=0.0, Z=0.0)
        else:
            falling = 0
    except Exception as ex:
        logging.dev_warning(f"[No Clip] could not hold you up ({ex})")
        return

    canvas = __args.Canvas
    if canvas is None:
        return

    try:
        if font is None:
            font = unrealsdk.find_object("Font", FONT)
            white = unrealsdk.make_struct("Color", R=255, G=255, B=255, A=255)

        canvas.Font = font
        canvas.DrawColor = white
        canvas.SetPos(READING_LEFT, READING_TOP)
        canvas.DrawText(f"No Clip: {'On' if flying else 'Off'}", False, 1.0, 1.0)
    except Exception as ex:
        logging.dev_warning(f"[No Clip] could not write the reading ({ex})")


def on_disable() -> None:
    """Puts you back on your feet if the mod is turned off mid-flight."""
    global flying, stock_speed, took_off_at, falling

    if flying:
        pc = get_pc()
        if pc is not None and pc.Pawn is not None:
            try:
                land(pc.Pawn)
            except Exception as ex:
                logging.dev_warning(f"[No Clip] could not put you back ({ex})")

    flying = False
    stock_speed = None
    took_off_at = None
    falling = 0


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

build_mod(
    options=[FlySpeed],
    keybinds=[on_toggle],
    hooks=[on_render],
    commands=[],
    on_disable=on_disable,
    settings_file=Path(f"{SETTINGS_DIR}/NoClip.json"),
)

logging.info(f"No Clip Loaded: {__version__}, {__version_info__}")
