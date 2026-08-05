from pathlib import Path

from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Block, Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import SETTINGS_DIR, build_mod, get_pc, hook

# The press waiting to be made again, and how many frames until it is. Ending the
# skill you have out does not finish inside the same press, so the fresh one is
# asked for a few frames later, with everything the game's own press carried.
waiting: tuple | None = None
frames = 0


@hook(
    hook_func="WillowGame.WillowPlayerController:StartActiveSkillCooldown",
    hook_type=Type.PRE,
)
def on_cooldown(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> type[Block] | None:
    """The wait never starts, so your action skill is always ready."""
    return Block


@hook(
    hook_func="WillowGame.WillowPlayerController:ServerStartSimpleSkill",
    hook_type=Type.PRE,
)
def on_start(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    """The game will not start a skill that is already running, so the one you have
    out is ended and a fresh one is asked for a moment later."""
    global waiting, frames

    if waiting is not None:
        return

    try:
        number = int(__args.SkillNumber)
        # Only the action skill. Other keys come through here too.
        if number != int(obj.ActionSkillPlayerSkillIndex):
            return
        if float(obj.ActionSkillTime) < 0.0:
            return
    except Exception:
        return

    try:
        obj.ResetActionSkill()
    except Exception as ex:
        logging.dev_warning(f"[No Skill Cooldown] could not end the skill ({ex})")
        return

    # Everything the game's own press carried is kept and handed back with the
    # fresh one, above all the callback it uses to hand the keys back afterwards.
    # Losing that is what left guns refusing to fire.
    try:
        waiting = (
            number,
            int(__args.TapCount),
            float(__args.ChargeTime),
            __args.StateChangeDelegate,
        )
    except Exception:
        waiting = (number, 0, 0.0, None)
    frames = 4


@hook(hook_func="Engine.GameViewportClient:PostRender", hook_type=Type.POST)
def on_render(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    """Sets the skill off again once the last one has finished."""
    global waiting, frames

    if waiting is None:
        return

    frames -= 1
    if frames > 0:
        return

    press, waiting = waiting, None
    number, taps, charge, callback = press

    pc = get_pc()
    if pc is None:
        return

    try:
        if callback is not None:
            pc.ServerStartSimpleSkill(number, taps, charge, False, callback)
        else:
            pc.ServerStartSimpleSkill(number, taps, charge)
    except Exception as ex:
        logging.warning(f"[No Skill Cooldown] could not set the skill off ({ex})")


def on_enable() -> None:
    """Any wait you are already sitting on is cleared the moment you turn this on."""
    pc = get_pc()
    if pc is None:
        return

    try:
        pool = pc.SkillCooldownPool.Data
        if float(pool.CurrentValue) != 0.0:
            pool.CurrentValue = 0.0
    except Exception as ex:
        logging.dev_warning(f"[No Skill Cooldown] could not clear the wait ({ex})")


def on_disable() -> None:
    global waiting, frames

    waiting = None
    frames = 0


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

build_mod(
    options=[],
    keybinds=[],
    hooks=[on_cooldown, on_start, on_render],
    commands=[],
    on_enable=on_enable,
    on_disable=on_disable,
    settings_file=Path(f"{SETTINGS_DIR}/NoSkillCooldown.json"),
)

logging.info(f"No Skill Cooldown Loaded: {__version__}, {__version_info__}")
