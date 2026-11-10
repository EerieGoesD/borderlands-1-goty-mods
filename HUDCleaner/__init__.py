import time
from pathlib import Path

from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import SETTINGS_DIR, build_mod, get_pc, hook
from mods_base.options import BoolOption

LABEL = "HUD Cleaner"

# Where each part sits on the HUD's Flash screen, read out of the game's own HUD file.
PLAYER = "_root.p1"
GRENADES = [f"{PLAYER}.grenade{n}" for n in range(1, 20)]

HideAll = BoolOption("Hide Entire HUD", False, "On", "Off")
HideCompass = BoolOption("Hide Compass", False, "On", "Off")
HideMission = BoolOption("Hide Mission Panel", False, "On", "Off")
HideVitals = BoolOption("Hide Health and Shield Bars", False, "On", "Off")
HideAmmo = BoolOption("Hide Ammo Panel", False, "On", "Off")
HideGrenades = BoolOption("Hide Grenade Panel", False, "On", "Off")
HideSkill = BoolOption("Hide Skill Icon", False, "On", "Off")
HideLevel = BoolOption("Hide Level Bar", False, "On", "Off")
HideTeammates = BoolOption("Hide Teammate Panels", False, "On", "Off")

PANELS = [
    (HideAll, [PLAYER]),
    (HideCompass, [f"{PLAYER}.bearing"]),
    (HideMission, [f"{PLAYER}.quest"] + [f"{PLAYER}.check{n}" for n in range(1, 6)]),
    (HideVitals, [f"{PLAYER}.health", f"{PLAYER}.health_icon", f"{PLAYER}.shield"]),
    (HideAmmo, [f"{PLAYER}.bullets", f"{PLAYER}.bullet_icon", f"{PLAYER}.bullet_c"]),
    (HideGrenades, GRENADES),
    (HideSkill, [f"{PLAYER}.character"]),
    (HideLevel, [f"{PLAYER}.xpbar", f"{PLAYER}.level", f"{PLAYER}.lvdisp"]),
    (HideTeammates, [f"{PLAYER}.coop1", f"{PLAYER}.coop2", f"{PLAYER}.coop3"]),
]

# How often the hidden parts are hidden again, in seconds, in case the game brought
# one back.
REFRESH_SECONDS = 0.1
refreshed_at = 0.0

# What each hidden part looked like before, by where it sits, so it can be put back.
# A part is made see-through rather than switched off, since the game switches some
# parts on and off by itself, such as one grenade icon per grenade you carry.
hidden: dict[str, float] = {}

# The HUD screen the parts were hidden on, by name. A new area brings a new screen.
hidden_on: str | None = None


def hud_screen() -> UObject | None:
    """The HUD's Flash screen, looked up fresh each time."""
    pc = get_pc()
    if pc is None:
        return None
    hud = getattr(pc, "myHUD", None)
    if hud is None:
        return None
    return getattr(hud, "HUDMovie", None)


def wanted_hidden() -> set[str]:
    return {path for option, paths in PANELS if option.value is True for path in paths}


def update(screen: UObject, wanted: set[str]) -> None:
    for path in wanted:
        if path not in hidden:
            try:
                alpha = float(screen.GetVariableNumber(f"{path}._alpha"))
            except Exception:
                alpha = 100.0
            hidden[path] = alpha if alpha > 0 else 100.0
        try:
            screen.SetVariableNumber(f"{path}._alpha", 0.0)
        except Exception as ex:
            logging.dev_warning(f"[{LABEL}] could not hide {path} ({ex})")

    for path in [path for path in hidden if path not in wanted]:
        alpha = hidden.pop(path)
        try:
            screen.SetVariableNumber(f"{path}._alpha", alpha)
        except Exception as ex:
            logging.dev_warning(f"[{LABEL}] could not show {path} ({ex})")


@hook(hook_func="Engine.GameViewportClient:PostRender", hook_type=Type.POST)
def on_render(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    """Keeps the parts you switched on hidden, and brings back the ones you switched off."""
    global refreshed_at, hidden_on

    now = time.monotonic()
    if now - refreshed_at < REFRESH_SECONDS:
        return
    refreshed_at = now

    screen = hud_screen()
    if screen is None:
        return

    # A new screen starts with everything showing.
    name = str(screen)
    if name != hidden_on:
        hidden.clear()
        hidden_on = name

    update(screen, wanted_hidden())


def on_disable() -> None:
    """Brings every hidden part back."""
    screen = hud_screen()
    if screen is not None and str(screen) == hidden_on:
        update(screen, set())
    hidden.clear()


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

build_mod(
    options=[option for option, _paths in PANELS],
    keybinds=[],
    hooks=[on_render],
    commands=[],
    on_disable=on_disable,
    settings_file=Path(f"{SETTINGS_DIR}/HUDCleaner.json"),
)

logging.info(f"HUD Cleaner Loaded: {__version__}, {__version_info__}")
