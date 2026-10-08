import time
from pathlib import Path

import unrealsdk  # type: ignore
from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Block, Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import SETTINGS_DIR, build_mod, get_pc, hook
from mods_base.options import BoolOption

LABEL = "No Weapon Flash"

# Each gun type's own flash effect and light, by the type's name, so they can be put
# back. Only names are kept: the objects themselves may be let go of by the game
# when an area unloads.
saved_effect: dict[str, tuple[str, str] | None] = {}
saved_light: dict[str, tuple[str, str] | None] = {}
saved_burst: dict[str, tuple[str, str] | None] = {}

# Hit sparks, by where they sit. "parked" means the effect was moved to a spare slot
# on the same entry, which keeps it held so it can always come back.
saved_spark: dict[str, str | tuple[str, str] | None] = {}

# Guns whose explosions have been looked at since they were turned off, by name.
burst_checked: set[str] = set()

# The trail emitters switched off, by name, and the guns already looked at.
switched_off: set[str] = set()
trail_checked: set[str] = set()

# Surfaces load with each area, so the hit sparks are looked for again now and then
# while shooting, no more often than this, in seconds.
SPARK_RESCAN_SECONDS = 10.0
spark_scanned_at = 0.0

# Guns whose light has been taken away since the flicker was turned off, by name,
# so each is done once.
rebuilt: set[str] = set()


def name_of(obj: UObject | None) -> tuple[str, str] | None:
    """An object's class and name, enough to find it again later."""
    return None if obj is None else (str(obj.Class.Name), obj._path_name())


def find(saved_name: tuple[str, str] | None) -> UObject | None:
    if saved_name is None:
        return None
    return unrealsdk.find_object(saved_name[0], saved_name[1])


def gun_types() -> list[UObject]:
    return [
        definition
        for definition in unrealsdk.find_all("WeaponTypeDefinition", exact=False)
        if "Default__" not in definition._path_name()
    ]


def equipped_guns(pawn: UObject | None) -> list[UObject]:
    """The guns in your weapon slots, found fresh each time and never kept."""
    guns: list[UObject] = []
    try:
        item = pawn.InvManager.InventoryChain
    except Exception:
        return guns
    while item is not None and len(guns) < 8:
        try:
            if "WillowWeapon" in str(item.Class):
                guns.append(item)
            item = item.Inventory
        except Exception:
            break
    return guns


def my_pawn() -> UObject | None:
    pc = get_pc()
    return pc.Pawn if pc is not None else None


# ---- The flash effect at the barrel ----------------------------------------------


def empty_effect_type(definition: UObject | None) -> None:
    if definition is None:
        return
    try:
        path = definition._path_name()
        if path not in saved_effect:
            saved_effect[path] = name_of(definition.MuzzleFlashPSCTemplate)
        if definition.MuzzleFlashPSCTemplate is not None:
            definition.MuzzleFlashPSCTemplate = None
    except Exception as ex:
        logging.dev_warning(f"[{LABEL}] could not empty a gun type ({ex})")


def empty_effect_gun(gun: UObject | None) -> None:
    """A gun already made keeps its own copy of the flash, so that goes too."""
    if gun is None:
        return
    try:
        empty_effect_type(gun.DefinitionData.WeaponTypeDefinition)
        # Swapped the game's own way. Changing it by hand leaves the game cleaning
        # up the old effect later, which takes it down on an area change.
        for field in ("FirstPersonMuzzleFlash", "ThirdPersonMuzzleFlash"):
            effect = getattr(gun, field, None)
            if effect is not None and effect.Template is not None:
                effect.SetTemplate(None)
        model = gun.Instigator.CurrentWeaponAttachment if gun.Instigator is not None else None
        if model is not None and model.MuzzleFlashPSCTemplate is not None:
            model.MuzzleFlashPSCTemplate = None
    except Exception as ex:
        logging.dev_warning(f"[{LABEL}] could not empty a gun ({ex})")


def hide_muzzle() -> None:
    for definition in gun_types():
        empty_effect_type(definition)
    for gun in equipped_guns(my_pawn()):
        empty_effect_gun(gun)


def show_muzzle() -> None:
    for path, saved_name in saved_effect.items():
        try:
            definition = unrealsdk.find_object("WeaponTypeDefinition", path)
            if saved_name is not None:
                definition.MuzzleFlashPSCTemplate = find(saved_name)
        except Exception as ex:
            logging.dev_warning(f"[{LABEL}] could not put a gun type back ({ex})")
    saved_effect.clear()

    pawn = my_pawn()
    for gun in equipped_guns(pawn):
        try:
            effect = gun.DefinitionData.WeaponTypeDefinition.MuzzleFlashPSCTemplate
            for field in ("FirstPersonMuzzleFlash", "ThirdPersonMuzzleFlash"):
                component = getattr(gun, field, None)
                if component is not None:
                    component.SetTemplate(effect)
        except Exception as ex:
            logging.dev_warning(f"[{LABEL}] could not put a gun back ({ex})")
    try:
        model = pawn.CurrentWeaponAttachment if pawn is not None else None
        if model is not None and pawn.Weapon is not None:
            model.MuzzleFlashPSCTemplate = pawn.Weapon.DefinitionData.WeaponTypeDefinition.MuzzleFlashPSCTemplate
    except Exception as ex:
        logging.dev_warning(f"[{LABEL}] could not put the gun model back ({ex})")
    set_up_again(pawn)


# ---- The light that blinks on each shot ------------------------------------------


def empty_light_type(definition: UObject | None) -> None:
    if definition is None:
        return
    try:
        path = definition._path_name()
        if path not in saved_light:
            saved_light[path] = name_of(definition.MuzzleFlashLightTemplate)
        if definition.MuzzleFlashLightTemplate is not None:
            definition.MuzzleFlashLightTemplate = None
    except Exception as ex:
        logging.dev_warning(f"[{LABEL}] could not empty a gun type's light ({ex})")


def drop_light(gun: UObject | None) -> None:
    """A gun made while the flicker was on keeps a light that blinks on every shot.

    Its flash is taken off the gun the way unequipping does, the gun lets go of
    the light, and the flash goes back on with no light to bring back.
    """
    if gun is None:
        return
    try:
        empty_light_type(gun.DefinitionData.WeaponTypeDefinition)
        model = gun.Instigator.CurrentWeaponAttachment if gun.Instigator is not None else None
        if model is not None and model.MuzzleFlashLightTemplate is not None:
            model.MuzzleFlashLightTemplate = None
        if gun.MuzzleFlashLight is None or str(gun.Name) in rebuilt:
            return
        rebuilt.add(str(gun.Name))
        gun.DetachMuzzleFlash()
        gun.MuzzleFlashLight = None
        gun.AttachMuzzleFlash()
    except Exception as ex:
        logging.dev_warning(f"[{LABEL}] could not take a gun's light away ({ex})")


def hide_flicker() -> None:
    rebuilt.clear()
    for definition in gun_types():
        empty_light_type(definition)
    pawn = my_pawn()
    if pawn is not None:
        drop_light(pawn.Weapon)


def show_flicker() -> None:
    for path, saved_name in saved_light.items():
        try:
            definition = unrealsdk.find_object("WeaponTypeDefinition", path)
            if saved_name is not None:
                definition.MuzzleFlashLightTemplate = find(saved_name)
        except Exception as ex:
            logging.dev_warning(f"[{LABEL}] could not put a gun type's light back ({ex})")
    saved_light.clear()
    rebuilt.clear()

    pawn = my_pawn()
    try:
        model = pawn.CurrentWeaponAttachment if pawn is not None else None
        if model is not None and pawn.Weapon is not None:
            model.MuzzleFlashLightTemplate = pawn.Weapon.DefinitionData.WeaponTypeDefinition.MuzzleFlashLightTemplate
    except Exception as ex:
        logging.dev_warning(f"[{LABEL}] could not put the gun model's light back ({ex})")
    set_up_again(pawn)


def set_up_again(pawn: UObject | None) -> None:
    """The gun in your hands only picks a change up when the game sets it up, so it is
    taken off and put back on the gun the way equipping does."""
    try:
        gun = pawn.Weapon if pawn is not None else None
        if gun is not None:
            gun.DetachMuzzleFlash()
            gun.AttachMuzzleFlash()
    except Exception as ex:
        logging.dev_warning(f"[{LABEL}] could not set the flash up again ({ex})")


def firing_modes_of(gun: UObject | None) -> list[UObject]:
    """Every firing mode a gun's bullets can use: its plain one and its parts' ones."""
    modes: list[UObject] = []
    if gun is None:
        return modes
    try:
        data = gun.DefinitionData
        default = data.WeaponTypeDefinition.DefaultFiringModeDefinition
        if default is not None:
            modes.append(default)
        for prop in data._type._properties():
            part = getattr(data, str(prop.Name))
            abilities = getattr(part, "TechAbilities", None) if hasattr(part, "Class") else None
            if not abilities:
                continue
            for ability in abilities:
                if ability.TechFire is not None:
                    modes.append(ability.TechFire)
    except Exception as ex:
        logging.dev_warning(f"[{LABEL}] could not look at a gun's bullets ({ex})")
    return modes


# ---- The explosion an elemental bullet sets off where it lands --------------------


def empty_bursts_of(mode: UObject | None) -> None:
    """Empties the burst effect of every explosion one firing mode sets off on a hit."""
    if mode is None:
        return
    try:
        for behavior in mode.OnAnyImpact:
            explosion = getattr(behavior, "Definition", None)
            if explosion is None or "ExplosionDefinition" not in str(explosion.Class):
                continue
            path = explosion._path_name()
            if path not in saved_burst:
                saved_burst[path] = name_of(explosion.ExplosionPSTemplate)
            if explosion.ExplosionPSTemplate is not None:
                explosion.ExplosionPSTemplate = None
    except Exception as ex:
        logging.dev_warning(f"[{LABEL}] could not empty a bullet explosion ({ex})")


def empty_bursts_gun(gun: UObject | None) -> None:
    """A gun's elemental bullets come from its parts, so each part's firing modes go."""
    if gun is None or str(gun.Name) in burst_checked:
        return
    burst_checked.add(str(gun.Name))
    for mode in firing_modes_of(gun):
        empty_bursts_of(mode)


def hide_explosions() -> None:
    burst_checked.clear()
    for mode in unrealsdk.find_all("FiringModeDefinition"):
        if "Default__" not in mode._path_name():
            empty_bursts_of(mode)


def show_explosions() -> None:
    for path, saved_name in saved_burst.items():
        try:
            explosion = unrealsdk.find_object("ExplosionDefinition", path)
            if saved_name is not None:
                explosion.ExplosionPSTemplate = find(saved_name)
        except Exception as ex:
            logging.dev_warning(f"[{LABEL}] could not put a bullet explosion back ({ex})")
    saved_burst.clear()
    burst_checked.clear()


# ---- The trail an elemental bullet leaves on its way --------------------------------
# The trail effect is the bullet itself, so it stays. Only its emitters stop drawing.


def quiet_trail_of(mode: UObject | None) -> None:
    if mode is None:
        return
    try:
        trail = mode.PartSysTemplate
        if trail is None:
            return
        for emitter in trail.Emitters:
            if emitter is None:
                continue
            for level in emitter.LODLevels:
                if level is not None and bool(level.bEnabled):
                    level.bEnabled = False
                    switched_off.add(level._path_name())
    except Exception as ex:
        logging.dev_warning(f"[{LABEL}] could not quiet a bullet trail ({ex})")


def quiet_trails_gun(gun: UObject | None) -> None:
    if gun is None or str(gun.Name) in trail_checked:
        return
    trail_checked.add(str(gun.Name))
    for mode in firing_modes_of(gun):
        quiet_trail_of(mode)


def hide_trails() -> None:
    trail_checked.clear()
    for mode in unrealsdk.find_all("FiringModeDefinition"):
        if "Default__" not in mode._path_name():
            quiet_trail_of(mode)


def show_trails() -> None:
    for path in switched_off:
        try:
            unrealsdk.find_object("ParticleLODLevel", path).bEnabled = True
        except Exception as ex:
            logging.dev_warning(f"[{LABEL}] could not switch a bullet trail back on ({ex})")
    switched_off.clear()
    trail_checked.clear()


# ---- The sparks where a bullet lands --------------------------------------------------

# Whether hit sparks can be parked in the spare slot, worked out once.
can_park: bool | None = None


def spare_slot_fits(effect: WrappedStruct) -> bool:
    """The spare slot only shows in a censored copy of the game. It is used when it
    holds the same kind of effect, which is checked rather than assumed."""
    global can_park
    if can_park is None:
        try:
            slot = effect._type._find("CensoredEffectAlternative")
            can_park = str(slot.PropertyClass.Name) == "ParticleSystem"
        except Exception:
            can_park = False
    return can_park


def empty_spark(effect: WrappedStruct) -> str | tuple[str, str] | None:
    """Takes the spark out of one hit entry, and says how to bring it back."""
    template = effect.ParticleTemplate
    if template is None:
        return None
    if spare_slot_fits(effect) and effect.CensoredEffectAlternative is None:
        effect.CensoredEffectAlternative = template
        effect.ParticleTemplate = None
        return "parked"
    effect.ParticleTemplate = None
    return name_of(template)


def bring_spark_back(effect: WrappedStruct, how: str | tuple[str, str]) -> None:
    if how == "parked":
        effect.ParticleTemplate = effect.CensoredEffectAlternative
        effect.CensoredEffectAlternative = None
    else:
        effect.ParticleTemplate = find(how)


def hide_sparks() -> None:
    global spark_scanned_at
    spark_scanned_at = time.monotonic()

    for definition in unrealsdk.find_all("WillowImpactDefinition"):
        path = definition._path_name()
        if "Default__" in path or "Bullet" not in path:
            continue
        for field in ("FallbackEffect", "UnconditionalResponse"):
            key = f"impact|{path}|{field}"
            if key in saved_spark:
                continue
            try:
                effect = getattr(definition, field)
                how = empty_spark(effect)
                saved_spark[key] = how
                if how is not None:
                    setattr(definition, field, effect)
            except Exception as ex:
                logging.dev_warning(f"[{LABEL}] could not empty a hit spark ({ex})")

    for surface in unrealsdk.find_all("WillowPhysicalMaterialProperty"):
        path = surface._path_name()
        if "Default__" in path:
            continue
        try:
            responses = surface.ImpactResponses
            for index in range(len(responses)):
                key = f"surface|{path}|{index}"
                if key in saved_spark:
                    continue
                response = responses[index]
                impact = response.ImpactType
                if impact is None or "Bullet" not in impact._path_name():
                    saved_spark[key] = None
                    continue
                effect = response.ResponseEffect
                how = empty_spark(effect)
                saved_spark[key] = how
                if how is not None:
                    response.ResponseEffect = effect
                    responses[index] = response
        except Exception as ex:
            logging.dev_warning(f"[{LABEL}] could not empty a surface's hit sparks ({ex})")


def show_sparks() -> None:
    for key, how in saved_spark.items():
        if how is None:
            continue
        kind, path, where = key.split("|")
        try:
            if kind == "impact":
                definition = unrealsdk.find_object("WillowImpactDefinition", path)
                effect = getattr(definition, where)
                bring_spark_back(effect, how)
                setattr(definition, where, effect)
            else:
                surface = unrealsdk.find_object("WillowPhysicalMaterialProperty", path)
                responses = surface.ImpactResponses
                response = responses[int(where)]
                effect = response.ResponseEffect
                bring_spark_back(effect, how)
                response.ResponseEffect = effect
                responses[int(where)] = response
        except Exception as ex:
            logging.dev_warning(f"[{LABEL}] could not put a hit spark back ({ex})")
    saved_spark.clear()


# ---- Settings ----------------------------------------------------------------------


def is_on(option: BoolOption) -> bool:
    """Whether the mod is on. Saved settings are loaded while the mod is still being
    built, and nothing should change in the game then."""
    owner = getattr(option, "mod", None)
    return owner is not None and owner.is_enabled


def on_muzzle(option: BoolOption, shown: bool) -> None:
    if not is_on(option):
        return
    if shown:
        show_muzzle()
    else:
        hide_muzzle()


def on_flicker(option: BoolOption, shown: bool) -> None:
    if not is_on(option):
        return
    if shown:
        show_flicker()
    else:
        hide_flicker()


def on_explosions(option: BoolOption, shown: bool) -> None:
    if not is_on(option):
        return
    if shown:
        show_explosions()
    else:
        hide_explosions()


def on_decals(option: BoolOption, shown: bool) -> None:
    if not is_on(option):
        return
    if shown:
        show_sparks()
    else:
        hide_sparks()


WeaponMuzzle = BoolOption("Weapon Muzzle", False, "Enable", "Disable", on_change_anytime=on_muzzle)
WeaponFlicker = BoolOption("Weapon Flicker", False, "Enable", "Disable", on_change_anytime=on_flicker)
GunExplosions = BoolOption("Gun Explosions", False, "Enable", "Disable", on_change_anytime=on_explosions)
BulletDecals = BoolOption("Bullet Decals", False, "Enable", "Disable", on_change_anytime=on_decals)


def on_trails(option: BoolOption, shown: bool) -> None:
    if not is_on(option):
        return
    if shown:
        show_trails()
    else:
        hide_trails()


BulletTrails = BoolOption("Bullet Trails", False, "Enable", "Disable", on_change_anytime=on_trails)


def on_enable() -> None:
    if WeaponMuzzle.value is False:
        hide_muzzle()
    if WeaponFlicker.value is False:
        hide_flicker()
    if GunExplosions.value is False:
        hide_explosions()
    if BulletDecals.value is False:
        hide_sparks()
    if BulletTrails.value is False:
        hide_trails()


def on_disable() -> None:
    """Everything goes back the way the game had it."""
    if saved_effect:
        show_muzzle()
    if saved_light:
        show_flicker()
    if saved_burst:
        show_explosions()
    if saved_spark:
        show_sparks()
    if switched_off:
        show_trails()


@hook(hook_func="WillowGame.WillowWeapon:FireAmmunition", hook_type=Type.PRE)
def on_fire(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    """Any gun, anyone's, has its flash taken away just before the shot."""
    if WeaponMuzzle.value is False:
        empty_effect_gun(obj)
    if WeaponFlicker.value is False:
        drop_light(obj)
    if GunExplosions.value is False:
        empty_bursts_gun(obj)
    if BulletTrails.value is False:
        quiet_trails_gun(obj)
    if BulletDecals.value is False and time.monotonic() - spark_scanned_at >= SPARK_RESCAN_SECONDS:
        hide_sparks()


@hook(hook_func="WillowGame.WillowWeaponAttachment:PlayImpactEffects", hook_type=Type.PRE)
def on_impact(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> type[Block] | None:
    """The gun model's own hit effect, stopped outright."""
    if BulletDecals.value is False:
        return Block
    return None


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

mod = build_mod(
    options=[WeaponMuzzle, WeaponFlicker, GunExplosions, BulletDecals, BulletTrails],
    keybinds=[],
    hooks=[on_fire, on_impact],
    commands=[],
    on_enable=on_enable,
    on_disable=on_disable,
    settings_file=Path(f"{SETTINGS_DIR}/NoWeaponFlash.json"),
)

logging.info(f"No Weapon Flash Loaded: {__version__}, {__version_info__}")
