from pathlib import Path

import unrealsdk  # type: ignore
from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Block, Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import SETTINGS_DIR, build_mod, get_pc, hook
from mods_base.options import BoolOption

StopSpread = BoolOption("Also Stop Spread", False, "Yes", "No")


# A scope's own drifting sits on the gun's kind rather than on the gun, so the
# numbers it came with are kept here to be handed back.
sway: dict[UObject, tuple[float, float]] = {}

# Our own entries on the game's lists of aim adjustments, while they are on there.
mine: tuple[UObject, UObject] | None = None

# How wide the aim is held. Not quite nothing, since the crosshair is worked out by
# dividing by it.
TIGHT = 0.01


def held_gun(pc: UObject) -> UObject | None:
    try:
        return pc.Pawn.Weapon
    except Exception:
        return None


def stop_sway(gun: UObject) -> None:
    """Holds a scope still while you are looking down it."""
    try:
        kind = gun.DefinitionData.WeaponTypeDefinition
        if kind is None:
            return
        if kind not in sway:
            sway[kind] = (
                float(kind.ZoomWanderPitchAmplitude),
                float(kind.ZoomWanderYawAmplitude),
            )
        if float(kind.ZoomWanderPitchAmplitude) != 0.0:
            kind.ZoomWanderPitchAmplitude = 0.0
        if float(kind.ZoomWanderYawAmplitude) != 0.0:
            kind.ZoomWanderYawAmplitude = 0.0
    except Exception:
        pass


def give_sway_back() -> None:
    """Puts every scope's drifting back the way it came."""
    for kind, (pitch, yaw) in list(sway.items()):
        try:
            kind.ZoomWanderPitchAmplitude = pitch
            kind.ZoomWanderYawAmplitude = yaw
        except Exception:
            pass
    sway.clear()


@hook(hook_func="WillowGame.WillowWeapon:AddSpread", hook_type=Type.PRE)
def on_spread(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    """Each shot's direction goes through here to have the scatter added. The call
    is skipped and the aim handed back exactly as it came in, so every shot flies
    dead centre and nothing else notices."""
    if StopSpread.value is not True:
        return None

    try:
        return Block, __args.BaseAim
    except Exception as ex:
        logging.dev_warning(f"[No Recoil] could not straighten the shot ({ex})")
        return None


@hook(hook_func="WillowGame.WillowWeapon:GetAdjustedAim", hook_type=Type.PRE)
def on_aim(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    """The wobble is already in the aim by the time the scatter is added, so the
    shot's direction is simply handed back as exactly where you are looking."""
    if StopSpread.value is not True:
        return None

    pc = get_pc()
    if pc is None:
        return None

    try:
        return Block, pc.Rotation
    except Exception as ex:
        logging.dev_warning(f"[No Recoil] could not aim the shot ({ex})")
        return None


@hook(hook_func="Engine.GameViewportClient:PostRender", hook_type=Type.PRE)
def on_settle(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    """How wide the crosshair opens, written just before the screen is drawn.
    Writing it after the drawing is what made it flicker, since the crosshair had
    already gone up by the game's own number."""
    if StopSpread.value is not True:
        return

    pc = get_pc()
    if pc is None:
        return

    try:
        pool = pc.AccuracyPool.Data
        if float(pool.MinValue) != TIGHT:
            pool.MinValue = TIGHT
        if float(pool.MaxValue) != TIGHT:
            pool.MaxValue = TIGHT
        if float(pool.CurrentValue) != TIGHT:
            pool.CurrentValue = TIGHT
    except Exception:
        pass


def pin_crosshair(pc: UObject, tight: bool) -> None:
    """How wide the crosshair opens.

    The game rebuilds this from a stack of adjustments every tick, so ours is put
    on that stack the same way its own skills do it. Writing the width directly
    just fights the game and flickers.
    """
    global mine

    try:
        pool = pc.AccuracyPool.Data
    except Exception:
        return

    if tight:
        if mine is not None:
            return
        try:
            low = unrealsdk.construct_object("AttributeModifier", outer=pc)
            high = unrealsdk.construct_object("AttributeModifier", outer=pc)
            # Type 1 scales what the game worked out, taking nearly all of it away.
            for item in (low, high):
                item.Type = 1
                item.Value = -0.999
            pool.MinValueModifierStack = [*pool.MinValueModifierStack, low]
            pool.MaxValueModifierStack = [*pool.MaxValueModifierStack, high]
            mine = (low, high)
        except Exception as ex:
            mine = None
            logging.dev_warning(f"[No Recoil] could not close the crosshair ({ex})")
        return

    if mine is None:
        return

    low, high = mine
    try:
        pool.MinValueModifierStack = [
            item for item in pool.MinValueModifierStack if item is not low
        ]
        pool.MaxValueModifierStack = [
            item for item in pool.MaxValueModifierStack if item is not high
        ]
    except Exception:
        pass

    mine = None


@hook(
    hook_func="WillowGame.WillowPlayerController:AddAccuracyImpulse",
    hook_type=Type.PRE,
)
def on_impulse(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> type[Block] | None:
    """Every shot shoves your aim wider, which is what opens the crosshair up as
    you keep firing. The shove never lands."""
    return Block if StopSpread.value is True else None


@hook(hook_func="Engine.GameViewportClient:PostRender", hook_type=Type.POST)
def on_render(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    """Holds the kick at nothing while you are carrying a gun."""
    pc = get_pc()
    if pc is None or pc.Pawn is None:
        return

    gun = held_gun(pc)
    if gun is None:
        return

    try:
        if gun.bDisableFireViewShake is not True:
            gun.bDisableFireViewShake = True

        if StopSpread.value is True:
            stop_sway(gun)
        elif sway:
            give_sway_back()

        # The kick that walks your aim upwards is held down as well.
        if float(pc.CurrentWeaponKickAmt) != 0.0:
            pc.CurrentWeaponKickAmt = 0.0
        if float(pc.TargetWeaponKickAmt) != 0.0:
            pc.TargetWeaponKickAmt = 0.0
    except Exception as ex:
        logging.dev_warning(f"[No Recoil] could not settle the gun ({ex})")


def on_disable() -> None:
    """Back to the way the gun came."""
    give_sway_back()

    pc = get_pc()
    if pc is None:
        return

    pin_crosshair(pc, False)

    gun = held_gun(pc)
    if gun is None:
        return

    try:
        gun.bDisableFireViewShake = False
    except Exception as ex:
        logging.dev_warning(f"[No Recoil] could not put the gun back ({ex})")


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

build_mod(
    options=[StopSpread],
    keybinds=[],
    hooks=[on_render, on_spread, on_aim, on_impulse, on_settle],
    commands=[],
    on_disable=on_disable,
    settings_file=Path(f"{SETTINGS_DIR}/NoRecoil.json"),
)

logging.info(f"No Recoil Loaded: {__version__}, {__version_info__}")
