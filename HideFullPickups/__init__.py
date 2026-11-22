from pathlib import Path

import unrealsdk  # type: ignore
from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Block, Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import SETTINGS_DIR, build_mod, get_pc, hook

# Frames between one look at everything lying around.
RECHECK_FRAMES = 60


# Temporary: logs what happens while you look at a pickup.
DEBUG = False

# The pickups hidden, by name. Only names are kept: the game frees a pickup the moment
# somebody takes it, and touching a freed one takes the game down.
hidden: set[str] = set()
frames = 0


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


def says_full(pickup: UObject) -> bool:
    """Whether this is ammo, health or money: the only pickups the game marks FULL.
    Gear you cannot use yet, such as a gun above your level, keeps its beam."""
    try:
        tag = str(pickup.Inventory.DefinitionData.ItemDefinition).lower()
    except Exception:
        return False
    return any(word in tag for word in ("ammodrop", "ammo", "health", "medkit", "currency", "credit", "money", "cash"))


def can_use(pickup: UObject) -> bool:
    """Whether the player could actually pick this up right now."""
    if not says_full(pickup):
        return True

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
    name = str(obj)
    if can_use(obj):
        hidden.discard(name)
        return None

    if DEBUG:
        dump_pickup(obj)

    hidden.add(name)

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
    """Puts every hidden pickup back on screen, looking each one up fresh."""
    pc = get_pc()
    hud = None if pc is None else pc.myHUD

    for pickup in unrealsdk.find_all("WillowPickup"):
        if not hidden:
            break
        name = str(pickup)
        if name not in hidden:
            continue
        hidden.discard(name)
        if not alive(pickup):
            continue
        try:
            if hud is not None:
                hud.AddPostRenderedActor(pickup)
            pickup.SpawnPickupParticles()
        except Exception:
            pass
    hidden.clear()


def on_disable() -> None:
    restore_all()


@hook(hook_func="Engine.GameViewportClient:PostRender", hook_type=Type.POST)
def on_render(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    global frames

    pc = get_pc()
    if pc is None or pc.Pawn is None:
        return

    frames += 1
    if frames < RECHECK_FRAMES:
        return
    frames = 0

    # Everything is looked at here and now. Holding on to a pickup between frames
    # takes the game down, since the game frees it the moment somebody takes it.
    for pickup in unrealsdk.find_all("WillowPickup"):
        name = str(pickup)
        if not alive(pickup):
            hidden.discard(name)
            continue

        try:
            usable = can_use(pickup)
        except Exception:
            continue

        hud = pc.myHUD

        if usable:
            if name in hidden:
                hidden.discard(name)
                try:
                    if hud is not None:
                        hud.AddPostRenderedActor(pickup)
                    pickup.SpawnPickupParticles()
                except Exception:
                    pass
        elif name not in hidden:
            hidden.add(name)
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
