from pathlib import Path

import unrealsdk  # type: ignore
from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import SETTINGS_DIR, build_mod, get_pc, hook
from mods_base.options import BoolOption, SliderOption

from .missions import ALL_MISSIONS, BASE_ONLY, WITH_DLC

FONT = "ui_fonts.font_willowbody_18pt"

# 0 is not started, 1 is active, 4 is complete.
STATUS_COMPLETE = 4

# Panel geometry, in pixels from the top right corner.
PANEL_WIDTH = 460
PANEL_TOP = 60
LINE_HEIGHT = 28
TEXT_SCALE = 1.0

# Longest line that fits the panel, anything past this is cut short.
MAX_CHARS = 46

WHITE = (255, 255, 255)
GOLD = (255, 210, 0)
GREY = (150, 150, 150)
RED = (230, 60, 60)
GREEN = (90, 220, 90)
BLUE = (90, 180, 255)

# Missions where a known bug can cost you an achievement.
# The Crimson Armory door only stays open while one of these is active and unfinished,
# so finishing them out of order can shut you out of the rest.
RISKY_MISSIONS = {
    "Armory Assault",
    "Loot Larceny",
    "Super-Marcus Sweep",
    "It's Like Christmas!",
}
WARNING_TEXT = "Careful! Possible missable/glitched achievement"

# How often the panel and the mission lookup refresh, in frames.
REFRESH_FRAMES = 60

EnableDLC = BoolOption("Enable DLC Missions", True, "Yes", "No")
NextCount = SliderOption("Upcoming missions shown", 3, 0, 8, 1, True)
ShowSkipped = BoolOption("Flag Skipped Missions", True, "On", "Off")
ShowWarnings = BoolOption("Achievement Warnings", True, "On", "Off")

definitions: dict[str, UObject] = {}

frames = REFRESH_FRAMES
cached_lines: list[tuple[str, tuple[int, int, int]]] = []

font = None
colours: dict[tuple[int, int, int], object] = {}


def find_definitions() -> None:
    """Matches the flow list against the game's own mission objects, by display name.

    The game only loads a mission's data when it needs it, so this keeps looking until
    every mission in the flow has been seen.
    """
    wanted = set(ALL_MISSIONS)
    if wanted <= set(definitions):
        return

    for mission in unrealsdk.find_all("MissionDefinition"):
        try:
            name = str(mission.MissionName)
        except Exception:
            continue
        if name in wanted and name not in definitions:
            definitions[name] = mission


finished: set[str] = set()
finished_for: UObject | None = None


def completed_names() -> set[str]:
    """Which missions are done. A mission stays done, so each is only asked once."""
    global finished, finished_for

    pc = get_pc()
    if pc is None:
        return finished

    # A different character means starting the tally again.
    if pc is not finished_for:
        finished_for = pc
        finished = set()

    for name, mission in definitions.items():
        if name in finished:
            continue
        try:
            if pc.IsMissionInStatus(mission, STATUS_COMPLETE) is True:
                finished.add(name)
        except Exception:
            break

    return finished


def tracked_name() -> str | None:
    """The mission you picked in the log, which the compass is following."""
    try:
        mission = list(unrealsdk.find_all("MissionTracker"))[-1].ActiveMission
        return str(mission.MissionName)
    except Exception:
        return None


def build_lines() -> list[tuple[str, tuple[int, int, int]]]:
    flow = WITH_DLC if EnableDLC.value is True else BASE_ONLY

    finished = completed_names()

    def is_complete(name: str) -> bool:
        return name in finished

    done = [name for name in flow.flat if is_complete(name)]
    percent = round(100 * len(done) / len(flow.flat)) if flow.flat else 0

    lines: list[tuple[str, tuple[int, int, int]]] = [
        (f"Progress  {percent}%   {len(done)}/{len(flow.flat)}", BLUE),
    ]

    def label(marker: str, name: str) -> str:
        text = f"{marker}  {flow.kind[name]} - {name}"
        if len(text) > MAX_CHARS:
            text = text[: MAX_CHARS - 3] + "..."
        return text

    current = next(
        (i for i, name in enumerate(flow.main) if not is_complete(name)),
        len(flow.main),
    )

    # Whatever you picked in the mission log is the one you are on.
    tracked = tracked_name()
    if tracked is not None and tracked in flow.kind:
        lines.append((label(">", tracked), GOLD))

    # Where you are in the timeline: the mission you are on, else the next main one.
    if tracked is not None and tracked in flow.position:
        cutoff = flow.position[tracked]
    elif current < len(flow.main):
        cutoff = flow.position[flow.main[current]]
    else:
        cutoff = len(flow.flat)

    # Everything the timeline offered before that, and never got done.
    if ShowSkipped.value is True:
        for name in flow.flat[:cutoff]:
            if not is_complete(name):
                lines.append((label("!", name), RED))

    if current < len(flow.main):
        if ShowWarnings.value is True and flow.main[current] in RISKY_MISSIONS:
            lines.append((WARNING_TEXT, RED))

        # What the timeline offers next, main and side alike, after the one you are on.
        ahead = 0
        for name in flow.flat[cutoff:]:
            if ahead >= NextCount.value:
                break
            if is_complete(name) or name == tracked:
                continue
            lines.append((label("...", name), GREY))
            ahead += 1
    else:
        lines.append(("All missions done", WHITE))

    return lines


@hook(hook_func="Engine.GameViewportClient:PostRender", hook_type=Type.POST)
def on_render(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    pc = get_pc()
    if pc is None or pc.myHUD is None:
        return

    # No character in the world means the main menu or a loading screen.
    if pc.Pawn is None:
        return

    canvas = __args.Canvas
    if canvas is None:
        return

    global frames, cached_lines

    frames += 1
    if frames >= REFRESH_FRAMES:
        frames = 0
        find_definitions()
        cached_lines = build_lines()

    global font, colours

    try:
        if font is None:
            font = unrealsdk.find_object("Font", FONT)
            colours = {
                colour: unrealsdk.make_struct(
                    "Color",
                    R=colour[0],
                    G=colour[1],
                    B=colour[2],
                    A=255,
                )
                for colour in (WHITE, GOLD, GREY, RED, GREEN, BLUE)
            }

        left = canvas.SizeX - PANEL_WIDTH
        y = PANEL_TOP

        canvas.Font = font
        for text, colour in cached_lines:
            canvas.DrawColor = colours[colour]
            canvas.SetPos(left, y)
            canvas.DrawText(text, False, TEXT_SCALE, TEXT_SCALE)
            y += LINE_HEIGHT
    except Exception as ex:
        logging.dev_warning(f"[Mission Progress] could not draw ({ex})")


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

build_mod(
    options=[EnableDLC, ShowSkipped, ShowWarnings, NextCount],
    keybinds=[],
    hooks=[on_render],
    commands=[],
    settings_file=Path(f"{SETTINGS_DIR}/MissionProgress.json"),
)

logging.info(f"Mission Progress Loaded: {__version__}, {__version_info__}")
