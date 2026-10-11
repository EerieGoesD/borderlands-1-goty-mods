from pathlib import Path

from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import SETTINGS_DIR, build_mod, get_pc, hook

LABEL = "One Shot One Kill"

# What the target is left with just before your hit lands, so the hit itself kills
# it the normal way: your kill, your XP, its loot.
LAST_BIT = 1.0


def leave_last_bit(target: UObject, has_shield: bool) -> None:
    """Empties the shield and takes health down to the last bit."""
    if has_shield:
        try:
            shield = target.ShieldArmor.Data
            if shield is not None and float(shield.CurrentValue) > 0.0:
                shield.CurrentValue = 0.0
        except Exception:
            pass
    try:
        health = target.HealthPool.Data
        if health is not None and float(health.CurrentValue) > LAST_BIT:
            health.CurrentValue = LAST_BIT
    except Exception as ex:
        logging.dev_warning(f"[{LABEL}] could not lower the health ({ex})")


def from_you(instigator: UObject | None) -> bool:
    pc = get_pc()
    return pc is not None and instigator is not None and instigator == pc


@hook(hook_func="WillowGame.WillowAIPawn:TakeDamage", hook_type=Type.PRE)
def on_enemy_hit(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    try:
        if from_you(__args.InstigatedBy):
            leave_last_bit(obj, True)
    except Exception:
        pass


@hook(hook_func="WillowGame.WillowVehicle:TakeDamage", hook_type=Type.PRE)
def on_vehicle_hit(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    try:
        if not from_you(__args.InstigatedBy):
            return
        # Your own car stays out of it, even when your own rocket splashes it.
        pc = get_pc()
        if obj == pc.Pawn or getattr(obj, "Driver", None) == pc.Pawn:
            return
        leave_last_bit(obj, False)
    except Exception:
        pass


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

build_mod(
    options=[],
    keybinds=[],
    hooks=[on_enemy_hit, on_vehicle_hit],
    commands=[],
    settings_file=Path(f"{SETTINGS_DIR}/OneShotOneKill.json"),
)

logging.info(f"One Shot One Kill Loaded: {__version__}, {__version_info__}")
