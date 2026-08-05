import math
from pathlib import Path

import unrealsdk  # type: ignore
from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Block, Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import SETTINGS_DIR, EInputEvent, build_mod, get_pc, hook, keybind
from mods_base.options import BoolOption

FONT = "ui_fonts.font_willowbody_18pt"

# Where the reading sits, in pixels from the top left corner.
SPEED_LEFT = 30
SPEED_TOP = 120

# Moving slower than this counts as standing still. A run carries you on for a
# moment after you let go of the keys, so this sits above that coasting speed.
STILL = 150.0

# How much wider the view goes while running, in degrees.
RUN_VIEW = 8.0

# What the game calls being off the ground.
IN_THE_AIR = 2

CameraEffect = BoolOption("Camera Effect", True, "Yes", "No")
ShowSpeed = BoolOption("Show movement speed [DEBUG]", False, "Yes", "No")

font = None
white = None

# True once the toggle key has been pressed, meaning you run without holding anything.
always_running = False

# True while the hold key is down. It does the opposite of the toggle.
key_held = False

# True only while this mod is the one starting the run.
asked_for_it = False

# True while a run has been asked for and the game has not taken it yet.
run_pending = False

# The speed a run reaches, learnt from the game the first time it grants one.
running_speed = None

# The view width the game normally uses, noted the first time it is seen.
normal_view = None


def set_view(pc: UObject, running: bool) -> None:
    """Widens the view while running and puts it back afterwards."""
    global normal_view

    try:
        if normal_view is None:
            normal_view = float(pc.DesiredFOVBaseValue)

        wanted = normal_view + RUN_VIEW if running and CameraEffect.value else normal_view
        if abs(float(pc.DesiredFOV) - wanted) > 0.01:
            pc.DesiredFOV = wanted
    except Exception as ex:
        logging.dev_warning(f"[Run And Walk] could not change the view ({ex})")


def apply() -> None:
    """Puts the character on the speed the keys are asking for."""
    global asked_for_it, run_pending, running_speed

    pc = get_pc()
    if pc is None or pc.Pawn is None:
        return

    wanted = always_running != key_held
    try:
        # Standing still is never a run, whatever the keys say. Nor is aiming,
        # nor being off the ground.
        if wanted:
            speed = pc.Pawn.Velocity
            if float(speed.X) ** 2 + float(speed.Y) ** 2 < STILL * STILL:
                wanted = False
            elif pc.IsZoomed() is True:
                wanted = False
            elif int(pc.Pawn.Physics) == IN_THE_AIR:
                wanted = False
        # The character's own flag, not the controller's, which never changes.
        if bool(pc.Pawn.bIsSprinting) == wanted:
            run_pending = False
            set_view(pc, wanted)
            if wanted:
                # Note how fast a run actually goes, so later ones can match it at once.
                speed = float(pc.Pawn.GroundSpeed)
                if speed > float(pc.Pawn.GroundSpeedBaseValue):
                    running_speed = speed
            return
        # Written straight onto the character. Asking the game to start or stop the
        # run leaves it going.
        asked_for_it = True
        try:
            if wanted:
                # Let the game start the run, so the speed goes up with the flag.
                # It holds off on a fresh run for a moment after the last one, which
                # is cleared here so holding the key always starts one straight away.
                pc.SprintStopTime = 0.0
                pc.BeginSprint()

                # The game takes its time granting a second run, so once its speed
                # is known the change is made here and does not wait on it.
                if running_speed is not None and not bool(pc.Pawn.bIsSprinting):
                    pc.Pawn.SetSprinting(True)
                    pc.Pawn.bIsSprintingBaseValue = 1
                    pc.Pawn.bIsSprinting = 1
                    pc.Pawn.GroundSpeed = running_speed
            else:
                # Told the game's own way first, so its bookkeeping stays straight and
                # the next run is accepted at once, then forced in case it ignored us.
                pc.Pawn.SetSprinting(False)
                pc.Pawn.bIsSprintingBaseValue = 0
                pc.Pawn.bIsSprinting = 0
                pc.Pawn.GroundSpeed = pc.Pawn.GroundSpeedBaseValue

                # The game notes when the run ended and refuses a fresh one for a
                # moment afterwards. Nothing ended it here, so the note is cleared.
                pc.SprintStopTime = 0.0
                pc.bIsSprinting = False
        finally:
            asked_for_it = False

        run_pending = wanted and not bool(pc.Pawn.bIsSprinting)
        set_view(pc, wanted)
    except Exception as ex:
        logging.dev_warning(f"[Run And Walk] could not change speed ({ex})")


@hook(hook_func="WillowGame.WillowPlayerController:BeginSprint", hook_type=Type.PRE)
def on_begin_sprint(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> type[Block] | None:
    """The game starts a run of its own that keeps going. Only this mod may start one."""
    return None if asked_for_it else Block


@hook(hook_func="WillowGame.WillowUIInteraction:InputKey", hook_type=Type.PRE)
def on_input(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    """The game only accepts a run while it is reading the keys, which is why the
    hold key works and a toggle alone does not. Key events retry here, but only
    while a run is still waiting to start."""
    if run_pending:
        apply()


@keybind("Run", "LeftShift", event_filter=None)
def on_run(event: EInputEvent) -> None:
    """Held down, it does the opposite of whatever the toggle says."""
    global key_held

    held = event != EInputEvent.IE_Released
    if held == key_held:
        # A held key repeats many times a second, and none of them change anything.
        return
    key_held = held
    apply()


@keybind("Auto Run", "CapsLock")
def on_toggle() -> None:
    """Switches between always running and always walking."""
    global always_running

    always_running = not always_running
    apply()


@hook(hook_func="Engine.GameViewportClient:PostRender", hook_type=Type.POST)
def on_render(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    """The game drops out of a run on its own, so the choice is held here."""
    apply()

    if ShowSpeed.value is False:
        return

    canvas = __args.Canvas
    if canvas is None:
        return

    pc = get_pc()
    if pc is None or pc.Pawn is None:
        return

    global font, white

    try:
        if font is None:
            font = unrealsdk.find_object("Font", FONT)
            white = unrealsdk.make_struct("Color", R=255, G=255, B=255, A=255)

        speed = pc.Pawn.Velocity
        moving = math.sqrt(float(speed.X) ** 2 + float(speed.Y) ** 2)
        state = "running" if bool(pc.Pawn.bIsSprinting) else "walking"

        canvas.Font = font
        canvas.DrawColor = white
        canvas.SetPos(SPEED_LEFT, SPEED_TOP)
        auto = "on" if always_running else "off"
        canvas.DrawText(
            f"{state}  {moving:.0f} / {float(pc.Pawn.GroundSpeed):.0f}"
            f"   auto run {auto}",
            False,
            1.0,
            1.0,
        )
    except Exception as ex:
        logging.dev_warning(f"[Run And Walk] could not draw the speed ({ex})")


def on_disable() -> None:
    """Back to the game's own running, with nothing of ours left behind."""
    global always_running, key_held, run_pending

    always_running = False
    key_held = False
    run_pending = False

    pc = get_pc()
    if pc is None:
        return

    set_view(pc, False)

    try:
        if pc.Pawn is None:
            return

        # A run left going would never stop, since nothing is watching it any more.
        pc.Pawn.SetSprinting(False)
        pc.Pawn.bIsSprintingBaseValue = 0
        pc.Pawn.bIsSprinting = 0
        pc.Pawn.GroundSpeed = pc.Pawn.GroundSpeedBaseValue
        pc.SprintStopTime = 0.0
        pc.bIsSprinting = False
    except Exception as ex:
        logging.dev_warning(f"[Run And Walk] could not hand the run back ({ex})")


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

build_mod(
    options=[CameraEffect, ShowSpeed],
    keybinds=[on_run, on_toggle],
    hooks=[on_render, on_begin_sprint, on_input],
    commands=[],
    settings_file=Path(f"{SETTINGS_DIR}/RunAndWalk.json"),
)

logging.info(f"Run And Walk Loaded: {__version__}, {__version_info__}")
