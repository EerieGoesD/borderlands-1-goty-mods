import time
from pathlib import Path

import unrealsdk  # type: ignore
from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import SETTINGS_DIR, build_mod, get_pc, hook
from mods_base.options import ButtonOption, NestedOption, SliderOption

LABEL = "Viewmodel Changer"

# The groups, each with the gun FOV the game gives its guns.
GROUP_FOV = {
    "Pistols": 55,
    "Revolvers": 55,
    "SMGs": 45,
    "Combat Rifles": 55,
    "Shotguns": 55,
    "Sniper Rifles": 55,
    "Launchers": 65,
    "Eridian Weapons": 55,
}

# How often the gun in your hands is checked, in seconds, in case the game put its
# type back to normal, such as after loading an area.
CHECK_SECONDS = 0.5
checked_at = 0.0

# Each gun type's own position, read off the game the first time it is in your hands,
# by the type's name. Other mods' guns get theirs the same way.
start: dict[str, tuple[float, float, float]] = {}

# The gun FOV a type had before a moved slider changed it, so it can be put back. A
# slider left at its default never touches the FOV, so another mod's FOV stays.
fov_before: dict[str, float] = {}

# The group each gun type belongs to, by the type's name.
group_by_type: dict[str, str | None] = {}


def group_of(gun_type: UObject) -> str | None:
    """Which group a gun type belongs to, from what kind of gun the game marks it as."""
    if gun_type.bPlasmaWeapon is True:
        return "Eridian Weapons"
    if gun_type.bSniperRifle is True:
        return "Sniper Rifles"
    if gun_type.bRocketLauncher is True:
        return "Launchers"
    if gun_type.bShotgun is True:
        return "Shotguns"
    if gun_type.bSMG is True:
        return "SMGs"
    if gun_type.bAssaultRifle is True:
        return "Combat Rifles"
    if gun_type.bPistol is True:
        return "Revolvers" if "Ammo_Revolver_Pistol" in str(gun_type.AmmoResource) else "Pistols"
    return None


class Group:
    """The four settings for one group of guns."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.fov = SliderOption("Gun FOV", GROUP_FOV[name], 10, 100, 1, True, on_change_anytime=self.changed)
        self.forward = SliderOption("Forward and Back", 0, -100, 100, 1, True, on_change_anytime=self.changed)
        self.right = SliderOption("Left and Right", 0, -100, 100, 1, True, on_change_anytime=self.changed)
        self.up = SliderOption("Up and Down", 0, -100, 100, 1, True, on_change_anytime=self.changed)
        self.option = NestedOption(name, [self.fov, self.forward, self.right, self.up])

    def wanted(self) -> tuple[float | None, float, float, float]:
        """The gun FOV, None to leave it alone, then the three moves."""
        fov = None if self.fov.value == self.fov.default_value else self.fov.value
        return (fov, self.forward.value, self.right.value, self.up.value)

    def changed(self, option: SliderOption, value: float) -> None:
        # Called before the setting takes the new value, so it is put in by hand.
        fov, forward, right, up = self.wanted()
        if option is self.fov:
            fov = None if value == self.fov.default_value else value
        elif option is self.forward:
            forward = value
        elif option is self.right:
            right = value
        elif option is self.up:
            up = value
        if not enabled:
            return
        for path, group in group_by_type.items():
            if group == self.name:
                place(path, (fov, forward, right, up))
        refresh()


groups = {name: Group(name) for name in GROUP_FOV}

enabled = False


def find_type(path: str) -> UObject | None:
    try:
        return unrealsdk.find_object("WeaponTypeDefinition", path)
    except Exception:
        return None


def place(path: str, wanted: tuple[float | None, float, float, float]) -> None:
    """Sets one gun type's FOV and position from its own, if the game has it loaded."""
    gun_type = find_type(path)
    if gun_type is None or path not in start:
        return
    fov, forward, right, up = wanted
    x, y, z = start[path]
    try:
        if fov is not None:
            if path not in fov_before:
                fov_before[path] = float(gun_type.FirstPersonMeshFOV)
            gun_type.FirstPersonMeshFOV = float(fov)
        elif path in fov_before:
            gun_type.FirstPersonMeshFOV = fov_before.pop(path)
        gun_type.PlayerViewOffset = unrealsdk.make_struct(
            "Vector", X=float(x + forward), Y=float(y + right), Z=float(z + up),
        )
    except Exception as ex:
        logging.dev_warning(f"[{LABEL}] could not set {path} ({ex})")


def put_back_all() -> None:
    for path in group_by_type:
        place(path, (None, 0, 0, 0))


def refresh() -> None:
    """Moves the gun in your hands to where its type now says."""
    pc = get_pc()
    if pc is None or pc.Pawn is None:
        return
    pawn = pc.Pawn
    # The gun FOV goes straight onto the screen's gun view, the same way other FOV mods
    # do it, so nothing else about the camera is worked out again.
    try:
        pc.ForegroundFOV = float(pawn.Weapon.DefinitionData.WeaponTypeDefinition.FirstPersonMeshFOV)
    except Exception as ex:
        logging.dev_warning(f"[{LABEL}] could not update the gun FOV ({ex})")
    try:
        pawn.SetArmPosition()
    except Exception as ex:
        logging.dev_warning(f"[{LABEL}] could not move the gun ({ex})")


def check_held() -> bool:
    """Puts the gun type in your hands where the settings say, if it is not there.

    Returns whether anything had to change.
    """
    pc = get_pc()
    if pc is None or pc.Pawn is None:
        return False
    try:
        gun_type = pc.Pawn.Weapon.DefinitionData.WeaponTypeDefinition
        path = gun_type._path_name()
    except Exception:
        return False

    if path not in group_by_type:
        group_by_type[path] = group_of(gun_type)
        offset = gun_type.PlayerViewOffset
        start[path] = (float(offset.X), float(offset.Y), float(offset.Z))
    group = group_by_type[path]
    if group is None:
        return False

    fov, forward, right, up = groups[group].wanted()
    x, y, z = start[path]
    offset = gun_type.PlayerViewOffset
    off = (
        abs(float(offset.X) - (x + forward)) > 0.01
        or abs(float(offset.Y) - (y + right)) > 0.01
        or abs(float(offset.Z) - (z + up)) > 0.01
        or (fov is not None and abs(float(gun_type.FirstPersonMeshFOV) - fov) > 0.01)
    )
    if off:
        place(path, (fov, forward, right, up))
    return off


@hook(hook_func="Engine.GameViewportClient:PostRender", hook_type=Type.POST)
def on_render(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    """Now and then, puts the gun in your hands where the settings say."""
    global checked_at

    now = time.monotonic()
    if now - checked_at < CHECK_SECONDS:
        return
    checked_at = now

    try:
        if check_held():
            refresh()
    except Exception as ex:
        logging.dev_warning(f"[{LABEL}] could not check the gun ({ex})")


def reset_all(option: ButtonOption) -> None:
    """Every setting back to the game's own, for every gun type."""
    for group in groups.values():
        for slider in (group.fov, group.forward, group.right, group.up):
            slider.value = slider.default_value
    mod.save_settings()


ResetAll = ButtonOption("Reset to Default", on_press=reset_all)


def on_enable() -> None:
    global enabled
    enabled = True
    if check_held():
        refresh()


def on_disable() -> None:
    global enabled
    enabled = False
    put_back_all()
    refresh()


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

mod = build_mod(
    options=[ResetAll] + [group.option for group in groups.values()],
    keybinds=[],
    hooks=[on_render],
    commands=[],
    on_enable=on_enable,
    on_disable=on_disable,
    settings_file=Path(f"{SETTINGS_DIR}/ViewmodelChanger.json"),
)

logging.info(f"Viewmodel Changer Loaded: {__version__}, {__version_info__}")
