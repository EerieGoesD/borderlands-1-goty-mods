from pathlib import Path

import unrealsdk  # type: ignore
from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Block, Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import SETTINGS_DIR, build_mod, get_pc, hook

# Frames between one look at everything lying around.
RECHECK_FRAMES = 60

# How many pickups are looked at each frame, so the game is not held up all
# at once.
BATCH = 8


# Temporary: logs what happens while you look at a pickup.
DEBUG = False

hidden: set[UObject] = set()
frames = 0

# The pickups still waiting to be looked at.
waiting_on: list = []


dumped: set[str] = set()


def dump_pickup(pickup: UObject) -> None:
    """Lists everything hanging off a pickup, to find what draws the FULL badge."""
    key = str(pickup.Class.Name)
    if key in dumped:
        return
    dumped.add(key)

    flags: list[str] = []
    others: list[str] = []
    for attr in dir(pickup):
        if attr.startswith("_"):
            continue
        try:
            value = getattr(pickup, attr)
        except Exception:
            continue
        if isinstance(value, bool):
            flags.append(f"{attr}={value}")
        elif value is not None and not isinstance(value, (int, float, str)):
            others.append(f"{attr}={type(value).__name__}")

    logging.info(f"[Hide Full Pickups] {key} flags: {', '.join(sorted(flags))}")
    logging.info(f"[Hide Full Pickups] {key} objects: {', '.join(sorted(others))}")

    try:
        for index, component in enumerate(pickup.Components):
            logging.info(
                f"[Hide Full Pickups] {key} component {index}:"
                f" {component.Class.Name} hidden={getattr(component, 'HiddenGame', '?')}",
            )
    except Exception as ex:
        logging.info(f"[Hide Full Pickups] {key} no components ({ex})")


def can_use(pickup: UObject) -> bool:
    """Whether the player could actually pick this up right now."""
    pc = get_pc()
    if pc is None or pc.Pawn is None:
        return True

    try:
        return pickup.Inventory.CanBeUsedBy(pc.Pawn) is True
    except Exception:
        return True


@hook(hook_func="WillowGame.WillowPickup:SpawnPickupParticles", hook_type=Type.PRE)
def on_spawn_particles(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> type[Block] | None:
    if can_use(obj):
        hidden.discard(obj)
        return None

    if DEBUG:
        dump_pickup(obj)

    hidden.add(obj)

    # Take it off the screen straight away rather than waiting for the next sweep.
    try:
        pc = get_pc()
        if pc is not None and pc.myHUD is not None:
            pc.myHUD.RemovePostRenderedActor(obj)
    except Exception:
        pass

    return Block


def alive(pickup: UObject) -> bool:
    """Whether the pickup still exists. Touching a gone one takes the game down."""
    try:
        if pickup is None:
            return False
        if pickup.bDeleteMe is True or pickup.bPendingDelete is True:
            return False
        return pickup.Inventory is not None
    except Exception:
        return False


def restore_all() -> None:
    """Puts every hidden pickup back on screen."""
    pc = get_pc()
    hud = None if pc is None else pc.myHUD

    for pickup in list(hidden):
        hidden.discard(pickup)
        if not alive(pickup):
            continue
        try:
            if hud is not None:
                hud.AddPostRenderedActor(pickup)
            pickup.SpawnPickupParticles()
        except Exception:
            pass


def on_disable() -> None:
    restore_all()


@hook(hook_func="Engine.GameViewportClient:PostRender", hook_type=Type.POST)
def on_render(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    global frames, waiting_on

    pc = get_pc()
    if pc is None or pc.Pawn is None:
        return

    frames += 1
    if frames >= RECHECK_FRAMES:
        frames = 0
        waiting_on = list(unrealsdk.find_all("WillowPickup"))

    if not waiting_on:
        return

    batch = waiting_on[:BATCH]
    del waiting_on[:BATCH]

    for pickup in batch:
        if not alive(pickup):
            hidden.discard(pickup)
            continue

        try:
            usable = can_use(pickup)
        except Exception:
            continue

        hud = pc.myHUD

        if usable:
            if pickup in hidden:
                hidden.discard(pickup)
                try:
                    if hud is not None:
                        hud.AddPostRenderedActor(pickup)
                    pickup.SpawnPickupParticles()
                except Exception:
                    pass
        elif pickup not in hidden:
            hidden.add(pickup)
            try:
                if hud is not None:
                    hud.RemovePostRenderedActor(pickup)
                pickup.DestroyPickupParticles()
            except Exception:
                pass


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

build_mod(
    options=[],
    keybinds=[],
    hooks=[on_spawn_particles, on_render],
    commands=[],
    settings_file=Path(f"{SETTINGS_DIR}/HideFullPickups.json"),
)

logging.info(f"Hide Full Pickups Loaded: {__version__}, {__version_info__}")
