import os
import time
import traceback
from pathlib import Path

from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import MODS_DIR, SETTINGS_DIR, build_mod, get_ordered_mod_list, get_pc, hook
from mods_base.options import BoolOption, ButtonOption, SliderOption, SpinnerOption

LOG_STEM = "CrashDebug"
ENDINGS = [".log", ".txt"]

# Where the note can go. The mods folder is the one that always exists.
PLACES = {
    "Desktop": Path.home() / "Desktop",
    "Documents": Path.home() / "Documents",
    "Mods folder": Path(MODS_DIR),
}

# The note is a fixed set of slots written over and over, so a crash cannot lose
# what was already put down. Each write goes straight to the system, which keeps it
# even when the game dies on the very next line.
SLOT_SIZE = 160
SLOTS = 128

# How often the list of mods is looked at again, in frames.
RESCAN_FRAMES = 300

def log_path(place: str | None = None, ending: str | None = None) -> Path:
    """Where the note goes, as picked in the settings."""
    folder = PLACES.get(place or SaveTo.value)
    if folder is None or not folder.is_dir():
        folder = PLACES["Mods folder"]
    return folder / (LOG_STEM + (ending or FileEnding.value))


def show_place(place: str | None = None, ending: str | None = None) -> None:
    where = log_path(place, ending)
    WhereIsIt.display_name = f"Saved to: {where}"
    WhereIsIt.description = f"The note is written to {where}"


def on_place_picked(_option, value) -> None:
    """Starts a fresh note in the new place."""
    show_place(place=value)
    start_log(place=value)


def on_ending_picked(_option, value) -> None:
    """Starts a fresh note under the new name."""
    show_place(ending=value)
    start_log(ending=value)


SaveTo = SpinnerOption(
    "Save the note to",
    value="Mods folder",
    choices=list(PLACES),
    wrap_enabled=True,
    on_change_anytime=on_place_picked,
)
FileEnding = SpinnerOption(
    "File type",
    value=ENDINGS[0],
    choices=ENDINGS,
    wrap_enabled=True,
    on_change_anytime=on_ending_picked,
)
WhereIsIt = ButtonOption(
    "Saved to: ",
    description="",
    description_title="Where the note is saved",
)
WrapMods = BoolOption("Follow Other Mods", True, "Yes", "No")
KeepSlots = SliderOption("Lines Kept", SLOTS, 32, 512, 32, True)

log_file: int | None = None
written = 0
broken = False
wrapped: set = set()
frames = 0
last_area = ""


def clear_old_notes(keep: Path) -> None:
    """Throws away notes left in any other place or under any other ending."""
    for folder in PLACES.values():
        for tail in ENDINGS:
            old = folder / (LOG_STEM + tail)
            if old == keep:
                continue
            try:
                if old.is_file():
                    old.unlink()
            except Exception:
                continue


def start_log(place: str | None = None, ending: str | None = None) -> None:
    """Opens the note and writes the heading."""
    global log_file, written

    stop_log()
    clear_old_notes(log_path(place, ending))
    try:
        log_file = os.open(
            str(log_path(place, ending)),
            os.O_CREAT | os.O_WRONLY | os.O_TRUNC | getattr(os, "O_BINARY", 0),
        )
    except Exception as ex:
        logging.dev_warning(f"[Crash Debug] could not open the note ({ex})")
        log_file = None
        return

    global broken

    written = 0
    broken = False
    note("Crash Debug started")


def stop_log() -> None:
    global log_file

    if log_file is not None:
        try:
            os.close(log_file)
        except Exception:
            pass
    log_file = None


def note(text: str) -> None:
    """Puts one line down, in the next slot along."""
    global written

    if log_file is None:
        return

    clock = time.strftime("%H:%M:%S")
    line = f"{written:08d}  {clock}  {text}"[: SLOT_SIZE - 1]
    # The spare room sits before the line break, so no blank stretch is left in front
    # of the next one.
    line = line + " " * (SLOT_SIZE - len(line) - 1) + "\n"
    where = (written % int(KeepSlots.value)) * SLOT_SIZE

    try:
        os.lseek(log_file, where, os.SEEK_SET)
        os.write(log_file, line.encode("utf-8", "replace"))
    except Exception as ex:
        global broken
        if not broken:
            broken = True
            logging.dev_warning(f"[Crash Debug] could not write the note ({ex})")
        return

    written += 1


def follow(mod_name: str, hook_name: str, inner):
    """The same hook, with a note of it left behind before and after."""

    def watched(
        obj: UObject,
        args: WrappedStruct,
        ret: any,
        func: BoundFunction,
    ):
        note(f"{mod_name} -> {hook_name}")
        try:
            answer = inner(obj, args, ret, func)
        except Exception:
            note(f"{mod_name} !! {hook_name} {traceback.format_exc(limit=1).strip()}")
            raise
        note(f"{mod_name} <- {hook_name}")
        return answer

    watched.crash_debug_inner = inner
    return watched


def watch_mods() -> None:
    """Wraps every other mod's hooks, so the note says which one was running."""
    if WrapMods.value is not True:
        return

    for mod in get_ordered_mod_list():
        name = str(mod.name)
        if name == "Crash Debug":
            continue
        for spot in getattr(mod, "hooks", ()) or ():
            try:
                inner = spot.__wrapped__
                if getattr(inner, "crash_debug_inner", None) is not None:
                    continue
                where = spot.hook_funcs[0][0] if spot.hook_funcs else "?"
                spot.__wrapped__ = follow(name, str(where).split(":")[-1], inner)
                if spot.get_active_count() > 0:
                    spot.enable()
                wrapped.add(spot.hook_identifier)
            except Exception as ex:
                logging.dev_warning(f"[Crash Debug] could not follow {name} ({ex})")


def unwatch_mods() -> None:
    """Puts every hook back the way it was."""
    for mod in get_ordered_mod_list():
        for spot in getattr(mod, "hooks", ()) or ():
            try:
                inner = getattr(spot.__wrapped__, "crash_debug_inner", None)
                if inner is None:
                    continue
                spot.__wrapped__ = inner
                if spot.get_active_count() > 0:
                    spot.enable()
            except Exception:
                continue
    wrapped.clear()


def area_name() -> str:
    try:
        return str(get_pc().WorldInfo.GetMapName(True))
    except Exception:
        return ""


@hook(hook_func="Engine.GameViewportClient:PostRender", hook_type=Type.POST)
def on_render(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    global frames, last_area

    frames += 1
    if frames < RESCAN_FRAMES:
        return
    frames = 0

    here = area_name()
    if here and here != last_area:
        last_area = here
        note(f"area is now {here}")

    # Mods turned on after us still need following.
    watch_mods()


def on_enable() -> None:
    show_place()
    start_log()
    watch_mods()


def on_disable() -> None:
    unwatch_mods()
    note("Crash Debug stopped")
    stop_log()


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

build_mod(
    options=[SaveTo, FileEnding, WhereIsIt, WrapMods, KeepSlots],
    keybinds=[],
    hooks=[on_render],
    commands=[],
    on_enable=on_enable,
    on_disable=on_disable,
    settings_file=Path(f"{SETTINGS_DIR}/CrashDebug.json"),
)

logging.info(f"Crash Debug Loaded: {__version__}, {__version_info__}")
