import time
from pathlib import Path

import unrealsdk  # type: ignore
from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import SETTINGS_DIR, build_mod, get_pc, hook
from mods_base.options import ButtonOption, NestedOption, SliderOption

LABEL = "Viewmodel Changer"

# Every gun type, the group it is set from, and where the game puts it on screen:
# its field of view, then how far forward, right and up it sits. Read off the game.
GUN_TYPES = [
    ("Pistols", "gd_weap_repeater_pistol.A_Weapon.WeaponType_repeater_pistol", 55, -4, 2, 2),
    ("Pistols", "gd_weap_stock_weapons.A_Weapon.WeaponType_repeater_pistol_stock", 55, 0, 0, 0),
    ("Pistols", "gd_weap_machine_pistol.A_Weapon.WeaponType_machine_pistol", 55, -2, 2, 4),
    ("Pistols", "gd_weap_stock_weapons.A_Weapon.WeaponType_machine_pistol_stock", 55, -2, 2, 4),
    ("Revolvers", "gd_weap_revolver_pistol.A_Weapon.WeaponType_revolver_pistol", 55, -4, 2, 2),
    ("SMGs", "gd_weap_patrol_smg.A_Weapon.WeaponType_patrol_smg", 45, 0, 0, 0),
    ("SMGs", "gd_weap_stock_weapons.A_Weapon.WeaponType_patrol_smg_stock", 45, 0, 0, 0),
    ("Combat Rifles", "gd_weap_combat_rifle.A_Weapon.WeaponType_combat_rifle", 55, 10, 0, 0),
    ("Combat Rifles", "dlc3_gd_weap_stock.A_Weapon.WeaponType_combat_rifle_stock", 55, 10, 0, 0),
    ("Combat Rifles", "gd_weap_support_machinegun.A_Weapon.WeaponType_support_machinegun", 55, 10, 0, 0),
    ("Combat Rifles", "gd_weap_stock_weapons.A_Weapon.WeaponType_support_machinegun_stock", 55, 0, 0, 0),
    ("Shotguns", "gd_weap_combat_shotgun.A_Weapon.WeaponType_combat_shotgun", 55, 0, 0, 0),
    ("Shotguns", "gd_weap_stock_weapons.A_Weapon.WeaponType_combat_shotgun_stock", 55, 0, 0, 0),
    ("Shotguns", "gd_weap_assault_shotgun.A_Weapon.WeaponType_assault_shotgun", 55, 0, 0, 0),
    ("Sniper Rifles", "gd_weap_sniper_rifle.A_Weapon.WeaponType_sniper_rifle", 55, 3, 3.5, 0),
    ("Sniper Rifles", "gd_weap_sniper_rifle_semiauto.A_Weapon.WeaponType_sniper_rifle_semiauto", 55, 3, 3.5, 0),
    ("Launchers", "gd_weap_rocket_launcher.A_Weapon.WeaponType_rocket_launcher", 65, 0, 10, 0),
    ("Launchers", "gd_weap_grenade_launcher.A_Weapon.WeaponType_grenade_launcher", 65, 0, 0, -16),
    ("Eridian Weapons", "gd_weap_alien_rifle.A_Rifle.a_weap.WeaponType_Eridan_Elementalgun", 55, 0, 0, 0),
    ("Eridian Weapons", "dlc3_gd_weap_UniqueParts.EridanRifle.WeaponType_Eridan_Elementalgun", 55, 0, 0, 0),
    ("Eridian Weapons", "gd_weap_alien_rifle.A_Launcher.a_weap.WeaponType_Eridan_Cannon", 55, 0, 0, 0),
    ("Eridian Weapons", "gd_weap_alien_rifle.A_Shotgun.a_weap.WeaponType_Eridan_Thunder_Storm", 55, 0, 0, 0),
    ("Eridian Weapons", "gd_weap_alien_rifle.A_SMG.a_weap.WeaponType_Eridan_Blaster", 55, 0, 0, 0),
    ("Eridian Weapons", "gd_weap_alien_rifle.A_Sniper.a_weap.WeaponType_Eridan_Lightning", 55, 0, 0, 0),
]

GROUP_NAMES = list(dict.fromkeys(group for group, *_rest in GUN_TYPES))

# How often the gun in your hands is checked, in seconds, in case the game put its
# type back to normal, such as after loading an area.
CHECK_SECONDS = 0.5
checked_at = 0.0


class Group:
    """The four settings for one group of guns."""

    def __init__(self, name: str) -> None:
        self.name = name
        fov = next(fov for group, _path, fov, *_rest in GUN_TYPES if group == name)
        self.fov = SliderOption("Gun FOV", fov, 10, 100, 1, True, on_change_anytime=self.changed)
        self.forward = SliderOption("Forward and Back", 0, -100, 100, 1, True, on_change_anytime=self.changed)
        self.right = SliderOption("Left and Right", 0, -100, 100, 1, True, on_change_anytime=self.changed)
        self.up = SliderOption("Up and Down", 0, -100, 100, 1, True, on_change_anytime=self.changed)
        self.option = NestedOption(name, [self.fov, self.forward, self.right, self.up])

    def wanted(self) -> tuple[float, float, float, float]:
        return (self.fov.value, self.forward.value, self.right.value, self.up.value)

    def changed(self, option: SliderOption, value: float) -> None:
        # Called before the setting takes the new value, so it is put in by hand.
        fov, forward, right, up = self.wanted()
        if option is self.fov:
            fov = value
        elif option is self.forward:
            forward = value
        elif option is self.right:
            right = value
        elif option is self.up:
            up = value
        if not enabled:
            return
        place_group(self.name, (fov, forward, right, up))
        refresh()


groups = {name: Group(name) for name in GROUP_NAMES}

enabled = False


def place(path: str, fov: float, x: float, y: float, z: float) -> None:
    """Sets one gun type's field of view and position, if the game has it loaded."""
    try:
        gun_type = unrealsdk.find_object("WeaponTypeDefinition", path)
    except Exception:
        return
    if gun_type is None:
        return
    try:
        gun_type.FirstPersonMeshFOV = float(fov)
        gun_type.PlayerViewOffset = unrealsdk.make_struct("Vector", X=float(x), Y=float(y), Z=float(z))
    except Exception as ex:
        logging.dev_warning(f"[{LABEL}] could not set {path} ({ex})")


def place_group(name: str, wanted: tuple[float, float, float, float]) -> None:
    fov, forward, right, up = wanted
    for group, path, _fov, x, y, z in GUN_TYPES:
        if group == name:
            place(path, fov, x + forward, y + right, z + up)


def place_all() -> None:
    for name, group in groups.items():
        place_group(name, group.wanted())


def put_back_all() -> None:
    for _group, path, fov, x, y, z in GUN_TYPES:
        place(path, fov, x, y, z)


def refresh() -> None:
    """Moves the gun in your hands to where its type now says."""
    pc = get_pc()
    if pc is None or pc.Pawn is None:
        return
    pawn = pc.Pawn
    weapon = getattr(pawn, "Weapon", None)
    if weapon is not None:
        try:
            weapon.UpdateForegroundFOV()
        except Exception as ex:
            logging.dev_warning(f"[{LABEL}] could not update the gun FOV ({ex})")
    try:
        pawn.SetArmPosition()
    except Exception as ex:
        logging.dev_warning(f"[{LABEL}] could not move the gun ({ex})")


def held_is_off() -> bool:
    """Whether the gun in your hands is not where the settings put it."""
    pc = get_pc()
    if pc is None or pc.Pawn is None:
        return False
    try:
        gun_type = pc.Pawn.Weapon.DefinitionData.WeaponTypeDefinition
        path = gun_type._path_name()
    except Exception:
        return False
    for group, known, _fov, x, y, z in GUN_TYPES:
        if known != path:
            continue
        fov, forward, right, up = groups[group].wanted()
        offset = gun_type.PlayerViewOffset
        return (
            abs(float(gun_type.FirstPersonMeshFOV) - fov) > 0.01
            or abs(float(offset.X) - (x + forward)) > 0.01
            or abs(float(offset.Y) - (y + right)) > 0.01
            or abs(float(offset.Z) - (z + up)) > 0.01
        )
    return False


@hook(hook_func="Engine.GameViewportClient:PostRender", hook_type=Type.POST)
def on_render(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    """Now and then, puts the gun in your hands back where the settings say."""
    global checked_at

    now = time.monotonic()
    if now - checked_at < CHECK_SECONDS:
        return
    checked_at = now

    try:
        if held_is_off():
            place_all()
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
    place_all()
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
