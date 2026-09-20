import os
import time
import traceback
from pathlib import Path

import unrealsdk  # type: ignore

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

# What the newest line is marked with, so the crash is easy to find.
NEWEST = "  <<< LAST"

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
ShowCost = BoolOption(
    "Show What Each Mod Costs",
    False,
    "On",
    "Off",
    description="Puts a list on screen of how long each mod takes every frame."
    " Needs Follow Other Mods on.",
)
CostWhere = SpinnerOption(
    "Position",
    value="Top left",
    choices=["Top left", "Top right", "Top centre"],
    wrap_enabled=True,
    description="Where the list of what each mod costs sits on screen.",
)
KeepSlots = SliderOption("Lines Kept", SLOTS, 32, 512, 32, True)

log_file: int | None = None
written = 0

# How long each mod has taken since the list was last worked out, and how much of
# the clock that stretch covered.
COST_WINDOW = 0.5
COST_FONT = "ui_fonts.font_willowbody_18pt"
COST_TOP = 200
COST_LINE = 24

# How wide the list is taken to be, and how far it keeps from the screen edge.
COST_WIDTH = 420
COST_MARGIN = 30

spent: dict[str, float] = {}
cost_lines: list[str] = []
window_frames = 0
window_time = 0.0
last_frame = 0.0
cost_font = None
cost_white = None
cost_black = None

# Where the newest line sits, so its mark can be wiped when the next one lands.
last_slot: int | None = None
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

    global last_slot

    written = 0
    last_slot = None
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
    global written, last_slot

    if log_file is None:
        return

    clock = time.strftime("%H:%M:%S")
    line = f"{written:08d}  {clock}  {text}"[: SLOT_SIZE - len(NEWEST) - 1]
    # The spare room sits before the line break, so no blank stretch is left in front
    # of the next one. The end of the newest line says so, since the lines are written
    # round and round rather than one after the other.
    line = line + " " * (SLOT_SIZE - len(line) - len(NEWEST) - 1) + NEWEST + "\n"
    where = (written % int(KeepSlots.value)) * SLOT_SIZE

    try:
        os.lseek(log_file, where, os.SEEK_SET)
        os.write(log_file, line.encode("utf-8", "replace"))

        # The line before it is not the newest any more, so its mark comes off.
        if last_slot is not None and last_slot != where:
            os.lseek(log_file, last_slot + SLOT_SIZE - len(NEWEST) - 1, os.SEEK_SET)
            os.write(log_file, b" " * len(NEWEST))
    except Exception as ex:
        global broken
        if not broken:
            broken = True
            logging.dev_warning(f"[Crash Debug] could not write the note ({ex})")
        return

    last_slot = where
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
        # Only the mod's own work is timed, never the note keeping around it.
        began = time.perf_counter() if ShowCost.value is True else None
        try:
            answer = inner(obj, args, ret, func)
        except Exception:
            note(f"{mod_name} !! {hook_name} {traceback.format_exc(limit=1).strip()}")
            raise
        if began is not None:
            spent[mod_name] = spent.get(mod_name, 0.0) + (time.perf_counter() - began)
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


def draw_costs(canvas) -> None:
    """Works out what each mod is costing, and puts the list on screen."""
    global window_frames, window_time, last_frame, cost_lines
    global cost_font, cost_white, cost_black

    now = time.perf_counter()
    if last_frame > 0.0:
        window_time += now - last_frame
        window_frames += 1
    last_frame = now

    if window_time >= COST_WINDOW and window_frames > 0:
        frame_ms = window_time / window_frames * 1000.0
        fresh = [f"Frame {frame_ms:.1f} ms"]
        for name, took in sorted(spent.items(), key=lambda pair: -pair[1]):
            each = took / window_frames * 1000.0
            share = took / window_time * 100.0
            fresh.append(f"{name}   {each:.2f} ms   {share:.0f}%")
        if len(fresh) == 1:
            fresh.append("Nothing measured. Turn Follow Other Mods on.")
        cost_lines = fresh
        spent.clear()
        window_frames = 0
        window_time = 0.0

    if canvas is None or not cost_lines:
        return

    try:
        if cost_font is None:
            cost_font = unrealsdk.find_object("Font", COST_FONT)
            cost_white = unrealsdk.make_struct("Color", R=255, G=255, B=255, A=255)
            cost_black = unrealsdk.make_struct("Color", R=0, G=0, B=0, A=255)

        canvas.Font = cost_font

        where = CostWhere.value
        if where == "Top right":
            left = canvas.SizeX - COST_WIDTH - COST_MARGIN
        elif where == "Top centre":
            left = (canvas.SizeX - COST_WIDTH) / 2
        else:
            left = COST_MARGIN

        y = COST_TOP
        for line in cost_lines:
            canvas.DrawColor = cost_black
            canvas.SetPos(left + 1, y + 1)
            canvas.DrawText(line, False, 1.0, 1.0)

            canvas.DrawColor = cost_white
            canvas.SetPos(left, y)
            canvas.DrawText(line, False, 1.0, 1.0)
            y += COST_LINE
    except Exception as ex:
        logging.dev_warning(f"[Crash Debug] could not draw the costs ({ex})")


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
    global frames, last_area, last_frame

    if ShowCost.value is True:
        draw_costs(__args.Canvas)
    else:
        last_frame = 0.0

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
    global cost_lines, window_frames, window_time, last_frame

    spent.clear()
    cost_lines = []
    window_frames = 0
    window_time = 0.0
    last_frame = 0.0

    unwatch_mods()
    note("Crash Debug stopped")
    stop_log()


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

build_mod(
    options=[SaveTo, FileEnding, WhereIsIt, WrapMods, KeepSlots, ShowCost, CostWhere],
    keybinds=[],
    hooks=[on_render],
    commands=[],
    on_enable=on_enable,
    on_disable=on_disable,
    settings_file=Path(f"{SETTINGS_DIR}/CrashDebug.json"),
)

logging.info(f"Crash Debug Loaded: {__version__}, {__version_info__}")
