from pathlib import Path

import unrealsdk  # type: ignore
from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from .elements import ELEMENT_BY_ENEMY
from mods_base import SETTINGS_DIR, build_mod, get_pc, hook

FONT = "ui_fonts.font_willowbody_18pt"

# Where the game draws the targeted enemy's level and name, as a share of the
# screen. The line goes just under the name, starting at the same left edge.
NAME_LEFT = 0.427
NAME_BELOW = 0.389

GOOD = (120, 255, 140)
BAD = (232, 124, 124)

# What the game calls each sort of gun, and the word used for it here.
GUN_WORDS = (
    ("revolver", "Revolver"),
    ("shotgun", "Shotgun"),
    ("sniper", "Sniper"),
    ("smg", "SMG"),
    ("combat_rifle", "Combat Rifle"),
    ("support_machinegun", "Combat Rifle"),
    ("rocket", "Launcher"),
    ("repeater", "Repeater"),
    ("machine_pistol", "Repeater"),
)
ELEMENT_WORDS = (
    ("incendiary", "Fire"),
    ("shock", "Shock"),
    ("corrosive", "Corrosive"),
    ("explosive", "Explosive"),
)

# What to use against each kind of enemy: the gun type, then the element.
ADVICE = {
    "bandit": ("Revolver or Sniper", "Fire, Shock on a shield"),
    "psycho": ("Shotgun", "Fire"),
    "bruiser": ("Shotgun or SMG", "Fire"),
    "bmidget": ("Sniper or Revolver", "Fire"),
    "midget": ("Shotgun", "Fire"),
    "skag": ("Shotgun or Revolver", "Fire"),
    "alpha": ("Shotgun", "Fire"),
    "skagfire": ("Revolver", "Shock"),
    "spider": ("Revolver or Shotgun", "Explosive"),
    "spidfire": ("Sniper or Revolver", "Explosive"),
    "bspider": ("Sniper or Revolver", "Explosive"),
    "rakk": ("SMG, Shotgun or Combat Rifle", "Fire"),
    "rakkfire": ("Shotgun or SMG", "Shock"),
    "scythid": ("Shotgun or SMG", "None"),
    "lance": ("Revolver or Sniper", "Corrosive"),
    "defender": ("Sniper", "Corrosive"),
    "chem": ("Revolver", "Fire"),
    "royal": ("Revolver or SMG", "Shock then Corrosive"),
    "assassin": ("Shotgun or SMG", "Shock then Fire"),
    "devast": ("Sniper or Revolver", "Corrosive"),
    "probe": ("SMG or Combat Rifle", "Shock"),
    "guardian": ("SMG or Revolver", "Shock"),
    "turret": ("Revolver", "Corrosive"),
    "crab": ("Eridian", "Corrosive"),
    "larva": ("Revolver", "Explosive"),
    "green": ("Revolver or Sniper", "Fire"),
    "drifter": ("Sniper or Revolver", "Shock"),
    "zombie": ("Combat Rifle, SMG or Revolver", "Fire"),
    "suicide": ("Revolver", "Fire"),
    "tank": ("Combat Rifle", "Fire"),
    "clap": ("Revolver", "Corrosive"),
    "hyper": ("Revolver", "Corrosive"),
    "hguard": ("Sniper", "Corrosive"),
    "vehicle": ("Launcher", "Corrosive"),
    "none": ("Revolver", "None"),
}

# Bosses and named enemies that do not follow their family, by the name shown.
NAMED = {
    "General Knoxx": ("Sniper or Revolver", "Explosive"),
    "Pumpkin Head": ("Sniper or Launcher", "Explosive"),
    "Queen Tarantella": ("Revolver", "None"),
    "Widowmaker": ("Revolver", "Explosive"),
    "Shank": ("SMG or Shotgun", "Shock then Fire"),
    "Motor Head": ("Revolver", "Fire or Corrosive"),
    "Crawmerax the Invincible": ("Sniper or Revolver", "Corrosive"),
    "Rakkinishu": ("Shotgun or Combat Rifle", "Explosive"),
    "Mothrakk": ("Sniper or Launcher", "Explosive"),
    "Rakk Hive": ("Sniper or Launcher", "Explosive"),
    "Awesome Rakk Hive": ("Sniper or Launcher", "Explosive"),
    "Ultimate Rakk Hive": ("Sniper or Launcher", "Explosive"),
    "Rakk-Trap Hive": ("Sniper or Launcher", "Explosive"),
    "The Destroyer": ("Sniper or Launcher", "Explosive"),
    "Moe": ("Shotgun", "Shock"),
    "Marley": ("Shotgun", "Fire"),
    "Franken Bill": ("Revolver or Sniper", "Fire"),
    "Undead Ned": ("Sniper", "Fire"),
    "MINAC": ("Revolver", "Corrosive"),
    "Ajax": ("Revolver", "Corrosive"),
    # Bosses whose names say nothing about what they are.
    "Helob": ("Revolver or Shotgun", "Explosive"),
    "King Aracobb": ("Revolver or Shotgun", "Explosive"),
    "Digit": ("Shotgun or Revolver", "Fire"),
    "Pinky": ("Shotgun or Revolver", "Fire"),
    "Scar": ("Shotgun or Revolver", "Fire"),
    "Skrappy": ("Shotgun or Revolver", "Fire"),
    "Skrappy \"all grown up\"": ("Shotgun or Revolver", "Fire"),
    "Dumpster Diver": ("Shotgun", "Fire"),
    "King Wee Wee": ("Shotgun", "Fire"),
    "Meat Popsicle": ("Shotgun", "Fire"),
    "Mini Steve": ("Shotgun", "Fire"),
    "Truxican Wrestler": ("Shotgun", "Fire"),
    "Bigfoot": ("Shotgun or SMG", "Fire"),
    "Father O'Callahan": ("Shotgun or SMG", "Fire"),
    "Hank Reiss": ("Shotgun or SMG", "Fire"),
    "Red Jack": ("Shotgun or SMG", "Fire"),
    "Whiskey Wesley": ("Shotgun or SMG", "Fire"),
    "Chaz": ("Revolver or Shotgun", "Fire"),
    "Ned": ("Revolver", "Fire"),
    "Ceresia": ("Shotgun or SMG", "Shock then Fire"),
    "Helicon": ("Shotgun or SMG", "Shock then Fire"),
    "Hera": ("Shotgun or SMG", "Shock then Fire"),
    "Minerva": ("Shotgun or SMG", "Shock then Fire"),
    "Vulcana": ("Shotgun or SMG", "Shock then Fire"),
    # Kyros cannot be corroded, and carries ten times the usual shield.
    "Commander Kyros": ("SMG", "Shock"),
    "Commander Typhon": ("Revolver or Sniper", "Corrosive, Shock on a shield"),
    "Master McCloud": ("Revolver or Sniper", "Corrosive"),
    "Skyscraper": ("Sniper or Revolver", "Shock"),
    "Mad Mel": ("Launcher", "Corrosive"),
    "Cluck-Trap": ("Revolver", "Corrosive"),
    "Comandant Steele-Trap": ("Revolver", "Corrosive"),
    "Dr. Ned-Trap": ("Revolver", "Corrosive"),
    "General Knoxx-Trap": ("Revolver", "Corrosive"),
    "Undead Ned-Trap": ("Revolver", "Corrosive"),
}


def kind_of(path: str, name: str) -> str:
    """Which family an enemy belongs to, from its balance entry and shown name."""
    p, n = path.lower(), name.lower()

    # The robot copies in the Claptrap DLC keep what they were copied from.
    if "-trap" in n or "trapling" in n:
        if "claptrap" in n:
            return "clap"
        base = n.replace("-trapling", "ling").replace("-trap", "")
        return kind_of(p.replace("-trap", ""), base)
    if "claptrap" in n:
        return "clap"
    if "hyperion" in n:
        return "hguard" if any(w in n for w in ("guard", "beefeater", "custodian", "sentry")) else "hyper"
    if "scythid" in p or any(w in n for w in ("scythid", "crawler", "bleeder", "slither")):
        return "scythid"
    if "spiderant" in n:
        if any(w in n for w in ("burner", "incinerator", "cremator")):
            return "spidfire"
        if any(w in n for w in ("badass", "badmutha", "superbad")):
            return "bspider"
        return "spider"
    if "rakk" in n:
        return "rakkfire" if "fire" in n else "rakk"
    if "wereskag" in n:
        return "skag"
    if "skag" in n or "alpha" in n:
        if any(w in n for w in ("rider", "rapparee", "rustler", "ravager", "raider")):
            return "midget"
        if "fire" in n:
            return "skagfire"
        if "alpha" in n:
            return "alpha"
        return "skag"
    if "guardian" in n:
        return "guardian"
    if "devastator" in n:
        return "devast"
    if "chemical" in n:
        return "chem"
    if "royal" in n:
        return "royal"
    if "assassin" in n:
        return "assassin"
    if "probe" in n:
        return "probe"
    if any(w in n for w in ("zombie", "torso", "defiler", "ghost", "corpse eater", "skelerakk")):
        return "zombie"
    if any(w in n for w in ("tankenstein", "franken tank", "loot goon")):
        return "tank"
    if "suicide" in n:
        return "suicide"
    if "turret" in n or "scorpio" in n:
        return "turret"
    if any(w in n for w in ("defender", "warden", "sentinel")):
        return "defender"
    if any(w in n for w in ("lance", "infantry", "marine", "commando", "rocketeer", "engineer", "machinist", "technician", "medic", "pyro", "shock trooper")):
        return "lance"
    if "armored craw" in n or n == "crab worm":
        return "crab"
    if "larva" in n:
        return "larva"
    if "green craw" in n:
        return "green"
    if "maggot" in n:
        return "skag"
    if "drifter" in n:
        return "drifter"
    if any(w in n for w in ("banger", "punk", "enforcer")) or "prisoners" in p:
        return "bandit"
    if "badass midget" in n:
        return "bmidget"
    if any(w in n for w in ("shotgunner", "midget raider", "midget ravager", "midget rustler", "shorty")):
        return "midget"
    if any(w in n for w in ("psycho", "maniac", "lunatic", "midget", "little", "stunted")):
        return "psycho"
    if any(w in n for w in ("bruiser", "brute", "bully")):
        return "bruiser"
    if "lancer" in n or "vehicle" in p:
        return "vehicle"
    return "bandit"


def advice_for(pawn: UObject) -> tuple[str, str] | None:
    """The gun and element for the enemy under the crosshair, or nothing if it is
    not an enemy."""
    try:
        state = pawn.BalanceDefinitionState
        balance = state.BalanceDefinition
        if balance is None:
            # A car has no entry of its own. One with an enemy at the wheel takes
            # the vehicle advice, the same for a bandit runner or a Lancer.
            driver = getattr(pawn, "Driver", None)
            if driver is not None and "AIPawn" in str(driver.Class):
                return ADVICE["vehicle"]
            return None
        path = str(balance)
        grade = int(state.GradeIndex)
    except Exception:
        return None

    name = ""
    try:
        grades = balance.Grades
        if 0 <= grade < len(grades):
            name = str(grades[grade].GradeModifiers.DisplayName)
    except Exception:
        pass

    gun, element = NAMED.get(name) or ADVICE[kind_of(path, name)]

    # The element comes from the game's own data for this exact enemy when there is
    # one. Shields that bandits carry as items are not in that data, so their reminder
    # to shock a shield stays.
    try:
        worked_out = ELEMENT_BY_ENEMY.get(balance._path_name())
    except Exception:
        worked_out = None
    if worked_out:
        if "Shock on a shield" in element and "Shock" not in worked_out:
            worked_out += ", Shock on a shield"
        element = worked_out
    return gun, element


# The advice for the enemy last seen under the crosshair, and that enemy's name, so
# it is only worked out again when the target changes. Only text is kept, never the
# enemy itself, since the game is free to let go of it at any time.
shown: tuple[str, str] | None = None
shown_for = ""

# The same for the gun in your hands.
held: tuple[str | None, str | None] = (None, None)
held_for = ""

font = None
colours: dict = {}


def target_advice(pc: UObject) -> tuple[str, str] | None:
    """The gun and element for whatever the HUD says is under the crosshair."""
    global shown, shown_for

    try:
        pawn = pc.myHUD.HUDMovie.CurrentTargetable[0]
    except Exception:
        return None
    if pawn is None:
        return None

    try:
        who = str(pawn)
    except Exception:
        return None
    if who != shown_for:
        shown_for = who
        shown = advice_for(pawn)
    return shown


def weapon_facts(pc: UObject) -> tuple[str | None, str | None]:
    """The sort of gun in your hands and the element it fires, if any."""
    global held, held_for

    try:
        weapon = pc.Pawn.Weapon
    except Exception:
        return (None, None)
    if weapon is None:
        return (None, None)

    try:
        which = str(weapon)
    except Exception:
        return (None, None)
    if which == held_for:
        return held
    held_for = which

    family = None
    try:
        definition = weapon.DefinitionData.WeaponTypeDefinition
        kind = str(definition.Name).lower()
        if "alien" in str(definition.Outer).lower():
            family = "Eridian"
        else:
            for needle, word in GUN_WORDS:
                if needle in kind:
                    family = word
                    break
    except Exception:
        pass

    element = None
    try:
        damage_type = weapon.StaticGetWeaponDamageType(weapon.DefinitionData)[0]
        if damage_type is not None:
            package = str(damage_type.Outer.Outer.Name).lower()
            for needle, word in ELEMENT_WORDS:
                if needle in package:
                    element = word
                    break
    except Exception:
        pass

    held = (family, element)
    return held


def wanted_guns(text: str) -> set:
    """Which gun types an advice line names, such as "SMG, Shotgun or Combat Rifle"."""
    return {part.strip() for part in text.replace(" or ", ", ").split(",") if part.strip()}


def wanted_elements(text: str) -> set:
    """Which elements an advice line accepts. "Fire" accepts fire only,
    "None" accepts a plain gun."""
    if text == "None":
        return {None}
    accepted = set()
    banned = False
    for word in text.replace(",", " ").split():
        if word == "never":
            banned = True
            continue
        if word in ("Fire", "Shock", "Corrosive", "Explosive") and not banned:
            accepted.add(word)
    return accepted


def paint(canvas, x: float, y: float, text: str, colour) -> float:
    """Draws one piece with a black edge, and says how wide it was."""
    canvas.DrawColor = colours["black"]
    canvas.SetPos(x + 1, y + 1)
    canvas.DrawText(text, False, 1.0, 1.0)
    canvas.DrawColor = colour
    canvas.SetPos(x, y)
    canvas.DrawText(text, False, 1.0, 1.0)
    try:
        return float(canvas.TextSize(text, 1.0, 1.0)[1])
    except Exception:
        return len(text) * 9.0


@hook(hook_func="Engine.GameViewportClient:PostRender", hook_type=Type.POST)
def on_render(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    global font

    pc = get_pc()
    if pc is None or pc.Pawn is None or pc.myHUD is None:
        return

    advice = target_advice(pc)
    if advice is None:
        return
    try:
        if pc.bStatusMenuOpen is True:
            return
    except Exception:
        pass

    canvas = __args.Canvas
    if canvas is None:
        return

    try:
        if font is None:
            font = unrealsdk.find_object("Font", FONT)
            for name, (r, g, b) in (("white", (255, 255, 255)), ("black", (0, 0, 0)), ("good", GOOD), ("bad", BAD)):
                colours[name] = unrealsdk.make_struct("Color", R=r, G=g, B=b, A=255)

        gun, element = advice
        family, firing = weapon_facts(pc)

        # Each half judged on its own: the gun in your hands against the gun type,
        # and the element it fires against the elements the line accepts.
        gun_colour = colours["good"] if family in wanted_guns(gun) else colours["bad"]
        element_colour = colours["good"] if firing in wanted_elements(element) else colours["bad"]

        canvas.Font = font
        x = canvas.SizeX * NAME_LEFT
        y = canvas.SizeY * NAME_BELOW
        x += paint(canvas, x, y, gun, gun_colour)
        x += paint(canvas, x, y, " / ", colours["white"])
        paint(canvas, x, y, element, element_colour)
    except Exception as ex:
        logging.dev_warning(f"[Enemy Weakness Indicator] could not draw ({ex})")


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

build_mod(
    options=[],
    keybinds=[],
    hooks=[on_render],
    commands=[],
    settings_file=Path(f"{SETTINGS_DIR}/EnemyWeakness.json"),
)

logging.info(f"Enemy Weakness Indicator Loaded: {__version__}, {__version_info__}")
