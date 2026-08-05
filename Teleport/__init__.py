import re
from pathlib import Path

import unrealsdk  # type: ignore
from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import SETTINGS_DIR, build_mod, get_pc, hook
from mods_base.options import ButtonOption, DropdownOption

NOTHING = "None found"

# Frames between looks at where you have been, so the list is ready without asking.
REFRESH_FRAMES = 120
frames = REFRESH_FRAMES

# The places you can go, by the name shown in the list.
places: dict[str, str] = {}

# Where you asked to go, held until the menu is out of the way.
waiting: str | None = None


def pretty(name: str) -> str:
    """Turns the game's own run together names into readable ones."""
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name)


def gather() -> list[str]:
    """Every place you have been to in this playthrough."""
    places.clear()

    pc = get_pc()
    if pc is None:
        return [NOTHING]

    try:
        been = pc.ActivatedTeleportersList
    except Exception:
        return [NOTHING]

    for spot in been:
        name = str(spot)
        if name:
            places[pretty(name)] = name

    return sorted(places) or [NOTHING]


def on_refresh(_option) -> None:
    """Looks again at where you have been, and puts it in the list."""
    names = gather()
    Pick.choices = names
    if Pick.value not in names:
        Pick.value = names[0]


@hook(
    hook_func="WillowGame.WillowGFxMenuScreenGeneric:Screen_Activate",
    hook_type=Type.PRE,
    immediately_enable=True,
)
def on_menu_screen(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    """The list is filled in just before a menu screen is drawn, so it is ready the
    first time you open the mod's settings rather than the second."""
    on_refresh(Refresh)


def shut_the_menu() -> None:
    """Puts the menu away, since the game is stopped while it is up."""
    for manager in unrealsdk.find_all("WillowGFxUIManager"):
        try:
            menu = manager.GetPlayingMovie()
        except Exception:
            continue
        if menu is None:
            continue

        # Backed out a screen at a time, the same as pressing Escape, so the menu
        # tidies up after itself and opens properly the next time.
        try:
            depth = len(list(menu.ScreenStack))
        except Exception:
            depth = 1

        for _ in range(depth):
            try:
                menu.Nav_Back()
            except Exception:
                break

        try:
            menu.Close()
        except Exception:
            pass

    # Backing out this way leaves the mod menu half way through drawing itself again,
    # which is what left the pause screen blank. It is put back to a clean start.
    try:
        from willow1_mod_menu import options as mod_menu  # noqa: PLC0415

        mod_menu.reactivate_upper_screen.disable()
        mod_menu.populator_stack.clear()
        mod_menu.nested_selection_stack.clear()
    except Exception:
        pass


def on_travel(option) -> None:
    """Takes you to the chosen place, once the menu is out of the way."""
    global waiting

    # Nothing of ours runs while the mod is off, so the trip would never happen.
    if not this_mod.is_enabled:
        try:
            from ui_utils import TrainingBox  # noqa: PLC0415

            TrainingBox(
                title="Teleport",
                message="This mod is turned off.\n\nSet Enabled to Yes, then press Go There.",
            ).show()
        except Exception as ex:
            logging.warning(f"[Teleport] the mod is turned off ({ex})")
        return

    where = places.get(Pick.value)
    if where is None:
        return

    waiting = where
    shut_the_menu()


@hook(hook_func="Engine.GameViewportClient:PostRender", hook_type=Type.POST)
def on_render(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    """The trip itself, made the moment the game is running again."""
    global waiting, frames

    # The list is kept up to date on its own, since at startup you have not loaded
    # a character yet and there is nowhere to go.
    frames += 1
    if frames >= REFRESH_FRAMES:
        frames = 0
        on_refresh(Refresh)

    if waiting is None:
        return

    pc = get_pc()
    if pc is None:
        return

    try:
        if pc.IsPaused() is True:
            return
    except Exception:
        return

    where, waiting = waiting, None

    try:
        pc.ServerTeleportPlayerToOutpost(where)
    except Exception as ex:
        logging.dev_warning(f"[Teleport] could not take you there ({ex})")


Pick = DropdownOption("Place", NOTHING, [NOTHING])
Travel = ButtonOption("Go There", on_press=on_travel)
Refresh = ButtonOption("Refresh the List", on_press=on_refresh)


def on_enable() -> None:
    on_refresh(Refresh)


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

this_mod = build_mod(
    options=[Pick, Travel, Refresh],
    keybinds=[],
    hooks=[on_render],
    commands=[],
    on_enable=on_enable,
    settings_file=Path(f"{SETTINGS_DIR}/Teleport.json"),
)

logging.info(f"Teleport Loaded: {__version__}, {__version_info__}")
