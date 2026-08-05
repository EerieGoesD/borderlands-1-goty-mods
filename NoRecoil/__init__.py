from pathlib import Path

from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import SETTINGS_DIR, build_mod, get_pc, hook
from mods_base.options import BoolOption

StopSpread = BoolOption(
    "Also Stop Spread",
    False,
    "Yes",
    "No",
    description="Every shot lands dead centre instead of scattering around the crosshair.",
)


def held_gun(pc: UObject) -> UObject | None:
    try:
        return pc.Pawn.Weapon
    except Exception:
        return None


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

        wanted = StopSpread.value is True
        if bool(gun.bDisableWeaponSpread) != wanted:
            gun.bDisableWeaponSpread = wanted

        # The kick that walks your aim upwards is held down as well.
        if float(pc.CurrentWeaponKickAmt) != 0.0:
            pc.CurrentWeaponKickAmt = 0.0
        if float(pc.TargetWeaponKickAmt) != 0.0:
            pc.TargetWeaponKickAmt = 0.0
    except Exception as ex:
        logging.dev_warning(f"[No Recoil] could not settle the gun ({ex})")


def on_disable() -> None:
    """Back to the way the gun came."""
    pc = get_pc()
    if pc is None:
        return

    gun = held_gun(pc)
    if gun is None:
        return

    try:
        gun.bDisableFireViewShake = False
        gun.bDisableWeaponSpread = False
    except Exception as ex:
        logging.dev_warning(f"[No Recoil] could not put the gun back ({ex})")


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

build_mod(
    options=[StopSpread],
    keybinds=[],
    hooks=[on_render],
    commands=[],
    on_disable=on_disable,
    settings_file=Path(f"{SETTINGS_DIR}/NoRecoil.json"),
)

logging.info(f"No Recoil Loaded: {__version__}, {__version_info__}")
