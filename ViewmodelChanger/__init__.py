import time
from pathlib import Path

import unrealsdk  # type: ignore
from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import SETTINGS_DIR, build_mod, get_pc, hook
from mods_base.options import BoolOption, ButtonOption, NestedOption, SliderOption

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

# How long the gun takes to move into and out of its sprinting, melee and grenade
# places, in seconds. Kept short so the move is not seen as the gun growing or shrinking.
BLEND_SECONDS = 0.1

# These three are kept when the mod is reloaded from the console: the copy being
# replaced puts every gun back from them, and it only does so after this file has run.

# Each gun type's own position, read off the game the first time it is in your hands,
# by the type's name. Other mods' guns get theirs the same way.
start: dict[str, tuple[float, float, float]] = globals().get("start", {})

# The gun FOV a type had before a moved slider changed it, so it can be put back. A
# slider left at its default never touches the FOV, so another mod's FOV stays.
fov_before: dict[str, float] = globals().get("fov_before", {})

# The group each gun type belongs to, by the type's name.
group_by_type: dict[str, str | None] = globals().get("group_by_type", {})


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


def slider(name: str) -> SliderOption:
    return SliderOption(name, 0, -100, 100, 1, True)


class Group:
    """The settings for one group of guns."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.fov = SliderOption("Gun FOV", GROUP_FOV[name], 10, 100, 1, True)
        self.forward = slider("Forward and Back")
        self.right = slider("Left and Right")
        self.up = slider("Up and Down")

        # Where the gun sits while you sprint. Off, it stays where it is.
        self.sprint_on = BoolOption("Sprint Position", False, "On", "Off")
        self.sprint_forward = slider("Forward and Back")
        self.sprint_right = slider("Left and Right")
        self.sprint_up = slider("Up and Down")

        # Where the gun sits while aiming down its sights, from the game's own spot.
        self.aim_forward = slider("Forward and Back")
        self.aim_up = slider("Up and Down")

        self.option = NestedOption(
            name,
            [
                self.fov,
                self.forward,
                self.right,
                self.up,
                NestedOption(
                    "Sprinting",
                    [self.sprint_on, self.sprint_forward, self.sprint_right, self.sprint_up],
                ),
                NestedOption("Aiming", [self.aim_forward, self.aim_up]),
            ],
        )

    def values(self) -> list:
        return [
            self.fov, self.forward, self.right, self.up, self.sprint_on, self.sprint_forward,
            self.sprint_right, self.sprint_up, self.aim_forward, self.aim_up,
        ]


groups = {name: Group(name) for name in GROUP_FOV}

# Where the gun sits during a melee and a grenade throw, on top of where it was, for
# every gun.
MeleeForward = slider("Forward and Back")
MeleeUp = slider("Up and Down")
GrenadeForward = slider("Forward and Back")
GrenadeUp = slider("Up and Down")
MeleeGroup = NestedOption("Melee", [MeleeForward, MeleeUp])
GrenadeGroup = NestedOption("Grenade Throw", [GrenadeForward, GrenadeUp])

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


def refresh(with_fov: bool = True) -> None:
    """Moves the gun in your hands to where its type now says."""
    pc = get_pc()
    if pc is None or pc.Pawn is None:
        return
    pawn = pc.Pawn
    # The gun FOV goes straight onto the screen's gun view, the same way other FOV mods
    # do it, so nothing else about the camera is worked out again.
    if with_fov:
        try:
            pc.ForegroundFOV = float(pawn.Weapon.DefinitionData.WeaponTypeDefinition.FirstPersonMeshFOV)
        except Exception as ex:
            logging.dev_warning(f"[{LABEL}] could not update the gun FOV ({ex})")
    try:
        pawn.SetArmPosition()
    except Exception as ex:
        logging.dev_warning(f"[{LABEL}] could not move the gun ({ex})")


def held_aim(weapon: UObject) -> float:
    """How far the gun is aimed down its sights, from 0 to 1, following the game's own
    aiming animation."""
    try:
        if int(weapon.ZoomState) == 0:
            return 0.0
        return max(0.0, min(1.0, float(weapon.GetZoomEffect())))
    except Exception:
        return 0.0


# How far the gun has moved into its sprinting, melee and grenade places, from 0 to 1.
moves = {"sprint": 0.0, "melee": 0.0, "grenade": 0.0}
frame_at = time.monotonic()

# The gun type in your hands, by name, and when it came out. While a gun is being
# switched to, it is not put in its sprinting place.
held_path: str | None = None
switched_at = 0.0
switch_seconds = 0.0


def towards(current: float, target: float, step: float) -> float:
    return min(target, current + step) if target > current else max(target, current - step)


@hook(hook_func="Engine.GameViewportClient:PostRender", hook_type=Type.POST)
def on_render(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    """Every frame, puts the gun in your hands where the settings say for what you are
    doing: standing, sprinting, aiming, in a melee or throwing a grenade."""
    global frame_at, held_path, switched_at, switch_seconds

    now = time.monotonic()
    pc = get_pc()
    if pc is None or pc.Pawn is None:
        frame_at = now
        return
    try:
        pawn = pc.Pawn
        weapon = pawn.Weapon
        gun_type = weapon.DefinitionData.WeaponTypeDefinition
        path = gun_type._path_name()
    except Exception:
        frame_at = now
        return

    try:
        if path not in group_by_type:
            group_by_type[path] = group_of(gun_type)
            offset = gun_type.PlayerViewOffset
            start[path] = (float(offset.X), float(offset.Y), float(offset.Z))
        group = group_by_type[path]
        if group is None:
            frame_at = now
            return
        settings = groups[group]

        # Nothing moves on while the game is paused.
        paused = pc.WorldInfo.Pauser is not None
        step = 0.0 if paused else min(1.0, (now - frame_at) / BLEND_SECONDS)
        frame_at = now

        if path != held_path:
            held_path = path
            switched_at = now
            try:
                switch_seconds = float(weapon.EquipTime)
            except Exception:
                switch_seconds = 1.0

        meleeing = pc.bPerformingMeleeAttack is True
        throwing = pc.bThrowingGrenade is True
        # The game counts you as sprinting only on the ground. It also lets you reload,
        # melee, throw or switch guns mid-sprint, so the sprinting place waits for those.
        sprinting = (
            settings.sprint_on.value is True
            and int(pawn.bIsSprinting) != 0
            and int(pawn.Physics) == 1
            and int(pawn.bReloading) == 0
            and not meleeing
            and not throwing
            and now - switched_at >= switch_seconds
        )
        moves["sprint"] = towards(moves["sprint"], 1.0 if sprinting else 0.0, step)
        moves["melee"] = towards(moves["melee"], 1.0 if meleeing else 0.0, step)
        moves["grenade"] = towards(moves["grenade"], 1.0 if throwing else 0.0, step)
        aim = held_aim(weapon)

        forward = float(settings.forward.value)
        right = float(settings.right.value)
        up = float(settings.up.value)
        sprint = moves["sprint"]
        forward += (float(settings.sprint_forward.value) - forward) * sprint
        right += (float(settings.sprint_right.value) - right) * sprint
        up += (float(settings.sprint_up.value) - up) * sprint
        forward += float(MeleeForward.value) * moves["melee"] + float(GrenadeForward.value) * moves["grenade"]
        up += float(MeleeUp.value) * moves["melee"] + float(GrenadeUp.value) * moves["grenade"]
        # The sights only line up at the game's own spot, so aiming moves the gun from
        # your settings to there, plus the aiming settings, as the animation goes.
        forward = forward * (1.0 - aim) + float(settings.aim_forward.value) * aim
        right = right * (1.0 - aim)
        up = up * (1.0 - aim) + float(settings.aim_up.value) * aim

        fov = None if settings.fov.value == settings.fov.default_value else float(settings.fov.value)
        changes_fov = fov is not None
        if fov is not None:
            own = fov_before.get(path, float(gun_type.FirstPersonMeshFOV))
            fov = None if aim >= 1.0 else fov + (own - fov) * aim

        x, y, z = start[path]
        offset = gun_type.PlayerViewOffset
        off = (
            abs(float(offset.X) - (x + forward)) > 0.01
            or abs(float(offset.Y) - (y + right)) > 0.01
            or abs(float(offset.Z) - (z + up)) > 0.01
            or (fov is not None and abs(float(gun_type.FirstPersonMeshFOV) - fov) > 0.01)
            or (fov is None and path in fov_before)
        )
        if off:
            place(path, (fov, forward, right, up))
            refresh(changes_fov)
    except Exception as ex:
        logging.dev_warning(f"[{LABEL}] could not place the gun ({ex})")


def reset_all(option: ButtonOption) -> None:
    """Every setting back to the game's own, for every gun type."""
    for group in groups.values():
        for setting in group.values():
            setting.value = setting.default_value
    for setting in (MeleeForward, MeleeUp, GrenadeForward, GrenadeUp):
        setting.value = setting.default_value
    mod.save_settings()


ResetAll = ButtonOption("Reset to Default", on_press=reset_all)


def on_enable() -> None:
    global enabled
    enabled = True


def on_disable() -> None:
    global enabled
    enabled = False
    put_back_all()
    refresh()


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

mod = build_mod(
    options=[ResetAll] + [group.option for group in groups.values()] + [MeleeGroup, GrenadeGroup],
    keybinds=[],
    hooks=[on_render],
    commands=[],
    on_enable=on_enable,
    on_disable=on_disable,
    settings_file=Path(f"{SETTINGS_DIR}/ViewmodelChanger.json"),
)

logging.info(f"Viewmodel Changer Loaded: {__version__}, {__version_info__}")
