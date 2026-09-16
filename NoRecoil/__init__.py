from pathlib import Path

import unrealsdk  # type: ignore
from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Block, Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import SETTINGS_DIR, build_mod, get_pc, hook
from mods_base.options import BoolOption

StopSpread = BoolOption("Stop Spread", False, "Yes", "No")


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


# The small crosshair drawn while Stop Spread is on, in pixels from the centre.
CROSS_GAP = 3
CROSS_ARM = 7

white = None
black = None


def draw_crosshair(canvas: UObject) -> None:
    """A small cross in the middle of the screen, white on a thin black edge."""
    global white, black

    if white is None:
        white = unrealsdk.make_struct("Color", R=255, G=255, B=255, A=255)
        black = unrealsdk.make_struct("Color", R=0, G=0, B=0, A=255)

    cx = int(canvas.SizeX / 2)
    cy = int(canvas.SizeY / 2)
    near = CROSS_GAP
    far = CROSS_GAP + CROSS_ARM

    arms = (
        (cx - far, cy, cx - near, cy),
        (cx + near, cy, cx + far, cy),
        (cx, cy - far, cx, cy - near),
        (cx, cy + near, cx, cy + far),
    )
    for x1, y1, x2, y2 in arms:
        if y1 == y2:
            canvas.Draw2DLine(x1, y1 - 1, x2, y2 - 1, black)
            canvas.Draw2DLine(x1, y1 + 1, x2, y2 + 1, black)
        else:
            canvas.Draw2DLine(x1 - 1, y1, x2 - 1, y2, black)
            canvas.Draw2DLine(x1 + 1, y1, x2 + 1, y2, black)
        canvas.Draw2DLine(x1, y1, x2, y2, white)


def equipped_guns(pc: UObject) -> list[UObject]:
    """The guns in your four weapon slots, which is where the HUD takes its crosshair."""
    found: list[UObject] = []
    try:
        item = pc.Pawn.InvManager.InventoryChain
    except Exception:
        return found

    while item is not None and len(found) < 8:
        try:
            if "WillowWeapon" in str(item.Class):
                found.append(item)
            item = item.Inventory
        except Exception:
            break

    return found


def carried_guns(pc: UObject) -> list[UObject]:
    """Every gun you have on you, in your hands and in the backpack."""
    found: list[UObject] = []
    try:
        manager = pc.Pawn.InvManager
    except Exception:
        return found

    for name in ("InventoryChain", "Backpack"):
        held = getattr(manager, name, None)
        if held is None:
            continue
        try:
            if isinstance(held, UObject):
                item = held
                while item is not None and len(found) < 300:
                    found.append(item)
                    item = getattr(item, "Inventory", None)
            else:
                found += [item for item in held if item is not None]
        except Exception:
            continue

    return [item for item in found if "WillowWeapon" in str(item.Class)]


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


def yours(weapon: UObject) -> bool:
    """Whether the gun is in your own hands.

    These hooks run for every gun in the game, enemy guns included, so without this
    enemies fired wherever you were looking and could never hit you.
    """
    pc = get_pc()
    if pc is None or pc.Pawn is None:
        return False
    try:
        return weapon.Owner is pc.Pawn
    except Exception:
        return False


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
    if not yours(obj):
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
    if not yours(obj):
        return None

    pc = get_pc()
    if pc is None:
        return None

    try:
        return Block, pc.Rotation
    except Exception as ex:
        logging.dev_warning(f"[No Recoil] could not aim the shot ({ex})")
        return None


CROSSHAIR_COLOURS = (
    "CrosshairColor_Default",
    "CrosshairColor_Enemy",
    "CrosshairColor_Friendly",
)


def set_crosshair(gun: UObject, showing: bool) -> None:
    """Turns one gun's own crosshair on or off, every way the game has of drawing it.

    The flag alone was put back by the game on its own during firing, so the switch
    and the colours are set with it.
    """
    if gun is None:
        return

    try:
        if gun.bSuppressCrosshair is showing:
            gun.bSuppressCrosshair = not showing
        if gun.bCrosshairEnabled is not showing:
            gun.bCrosshairEnabled = showing
    except Exception:
        pass

    try:
        gun.SetCrosshairEnabled(showing)
    except Exception:
        pass

    # Whatever is left of it is drawn see through.
    alpha = 255 if showing else 0
    for field in CROSSHAIR_COLOURS:
        try:
            colour = getattr(gun, field)
            if int(colour.A) == alpha:
                continue
            setattr(
                gun,
                field,
                unrealsdk.make_struct(
                    "Color",
                    R=int(colour.R),
                    G=int(colour.G),
                    B=int(colour.B),
                    A=alpha,
                ),
            )
        except Exception:
            continue


def hide_now(gun: UObject) -> None:
    """Takes the game's crosshair off one gun straight away."""
    if gun is None or StopSpread.value is not True:
        return
    set_crosshair(gun, False)


@hook(hook_func="WillowGame.WillowPlayerController:PlayerTick", hook_type=Type.POST)
def on_tick(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    """The guns in your slots are hidden during the game's own tick, which runs before
    anything is drawn. Doing it at drawing time left the game a frame to show its own
    crosshair whenever a gun was swapped or reloaded."""
    pc = get_pc()
    if pc is None:
        return

    tight = StopSpread.value is True
    for gun in equipped_guns(pc):
        set_crosshair(gun, not tight)


@hook(
    hook_func="WillowGame.WillowWeapon:WeaponEquipping.BeginState",
    hook_type=Type.POST,
)
def on_equipping(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    """Swapping to a gun puts its own crosshair back, so it comes off again here."""
    hide_now(obj)


@hook(hook_func="WillowGame.WillowWeapon:StartReload", hook_type=Type.POST)
def on_start_reload(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    """The same at the start of a reload."""
    hide_now(obj)


@hook(hook_func="WillowGame.WillowWeapon:ReloadDone", hook_type=Type.POST)
def on_reload_done(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    """And at the end of one."""
    hide_now(obj)


@hook(hook_func="WillowGame.WillowWeapon:FireAmmunition", hook_type=Type.POST)
def on_fired(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    """Firing puts the gun's own crosshair back, so it comes off again here."""
    hide_now(obj)


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
    pc = get_pc()
    if pc is None:
        return

    if StopSpread.value is not True:
        return

    # A last look before the screen is drawn, for anything that turned the gun's own
    # crosshair back on after the tick.
    for gun in equipped_guns(pc):
        hide_now(gun)

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
    """Holds the kick at nothing while you are carrying a gun, and swaps in a small
    crosshair while Stop Spread is on."""
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

    # The game's own crosshair is hidden just before the screen is drawn, and the
    # small one goes on in its place here.
    if StopSpread.value is not True:
        return

    try:
        if pc.bStatusMenuOpen is True or pc.WorldInfo.Pauser is not None:
            return
        if getattr(pc.Pawn, "Driver", None) is not None:
            return
        canvas = __args.Canvas
        if canvas is not None:
            draw_crosshair(canvas)
    except Exception as ex:
        logging.dev_warning(f"[No Recoil] could not draw the crosshair ({ex})")


def on_disable() -> None:
    """Back to the way the gun came."""
    give_sway_back()

    pc = get_pc()
    if pc is None:
        return

    pin_crosshair(pc, False)

    for carried in carried_guns(pc):
        set_crosshair(carried, True)

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
    hooks=[
        on_render,
        on_spread,
        on_aim,
        on_impulse,
        on_settle,
        on_tick,
        on_equipping,
        on_start_reload,
        on_reload_done,
        on_fired,
    ],
    commands=[],
    on_disable=on_disable,
    settings_file=Path(f"{SETTINGS_DIR}/NoRecoil.json"),
)

logging.info(f"No Recoil Loaded: {__version__}, {__version_info__}")
