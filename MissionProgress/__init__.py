import time
from pathlib import Path

import unrealsdk  # type: ignore
from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import SETTINGS_DIR, build_mod, get_pc, hook
from mods_base.options import BoolOption, SliderOption, SpinnerOption

from .missions import (
    ALL_MISSIONS,
    BASE_ONLY,
    BASE_ONLY_MAIN,
    WITH_DLC,
    WITH_DLC_MAIN,
)

FONT = "ui_fonts.font_willowbody_18pt"

# 0 is not started, 1 is active, 4 is complete.
STATUS_COMPLETE = 4

# Panel geometry, in pixels.
PANEL_WIDTH = 460
PANEL_TOP = 60
LINE_HEIGHT = 28
TEXT_SCALE = 1.0

# How far the panel keeps clear of the screen edge.
PANEL_MARGIN = 20

WHITE = (255, 255, 255)
GOLD = (255, 210, 0)
GREY = (150, 150, 150)
RED = (230, 60, 60)
GREEN = (90, 220, 90)
BLUE = (90, 180, 255)
BLACK = (0, 0, 0)

# Where the black pass goes. One behind and to the side costs a single extra
# drawing of each line rather than four.
OUTLINE_STEPS = ((1, 1),)

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

# How often the panel and the mission lookup refresh, in seconds.
REFRESH_SECONDS = 5.0

# How often we check whether a shop screen is up, in seconds.
SHOP_SECONDS = 0.5

Position = SpinnerOption(
    "Position",
    value="Top right",
    choices=["Top right", "Top left", "Top centre"],
    wrap_enabled=True,
)
EnableDLC = BoolOption("Enable DLC Missions", True, "Yes", "No")
NextCount = SliderOption("Upcoming missions shown", 3, 0, 8, 1, True)
ShowSkipped = BoolOption("Flag Skipped Missions", True, "On", "Off")
ShowWarnings = BoolOption("Achievement Warnings", True, "On", "Off")
EnableSide = BoolOption("Enable Side Missions", True, "Yes", "No")

definitions: dict[str, UObject] = {}

next_build = 0.0
cached_lines: list[tuple[str, tuple[int, int, int]]] = []
trimmed_lines = None

# Whether a shop screen is up, and the count until that is asked again. Only the
# answer is kept, never the screens themselves, since those belong to the area you
# are in and asking one of them anything after you leave takes the game down.
shop_open = False
shop_asked = 0.0

# Whether a menu was up last frame.
menu_was_open = False

font = None
colours: dict[tuple[int, int, int], object] = {}


# How many times to go looking for missions the game has not loaded yet. Some are
# never loaded at all, so this stops rather than sweeping every object for ever.
LOOKUPS = 20
lookups = 0


def find_definitions() -> None:
    """Matches the flow list against the game's own mission objects, by display name.

    The game only loads a mission's data when it needs it, so this looks again now and
    then, up to a point.
    """
    global lookups

    wanted = set(ALL_MISSIONS)
    if wanted <= set(definitions) or lookups >= LOOKUPS:
        return

    lookups += 1

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


def build_lines() -> list[tuple[str, tuple[int, int, int], bool]]:
    if EnableDLC.value is True:
        flow = WITH_DLC if EnableSide.value is True else WITH_DLC_MAIN
    else:
        flow = BASE_ONLY if EnableSide.value is True else BASE_ONLY_MAIN

    finished = completed_names()

    def is_complete(name: str) -> bool:
        return name in finished

    done = [name for name in flow.flat if is_complete(name)]
    percent = round(100 * len(done) / len(flow.flat)) if flow.flat else 0

    lines: list[tuple[str, tuple[int, int, int], bool]] = [
        (f"Progress  {percent}%   {len(done)}/{len(flow.flat)}", BLUE, False),
    ]

    def risky(name: str) -> bool:
        """Whether the warning goes on this mission's row."""
        return ShowWarnings.value is True and name in RISKY_MISSIONS

    def label(marker: str, name: str) -> str:
        return f"{marker}  {flow.kind[name]} - {name}"

    current = next(
        (i for i, name in enumerate(flow.main) if not is_complete(name)),
        len(flow.main),
    )

    # Whatever you picked in the mission log is the one you are on.
    tracked = tracked_name()
    if tracked is not None and tracked in flow.kind:
        lines.append((label(">", tracked), GOLD, risky(tracked)))

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
                lines.append((label("!", name), RED, risky(name)))

    if current < len(flow.main):
        # What the timeline offers next, main and side alike, after the one you are on.
        ahead = 0
        for name in flow.flat[cutoff:]:
            if ahead >= NextCount.value:
                break
            if is_complete(name) or name == tracked:
                continue
            lines.append((label("...", name), GREY, risky(name)))
            ahead += 1
    else:
        lines.append(("All missions done", WHITE, False))

    return lines


@hook(hook_func="Engine.GameViewportClient:PostRender", hook_type=Type.POST)
def on_render(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    global next_build, cached_lines, trimmed_lines, shop_open, shop_asked, menu_was_open

    pc = get_pc()
    if pc is None or pc.myHUD is None:
        return

    # No character in the world means the main menu or a loading screen.
    if pc.Pawn is None:
        return

    # Out of the way while a menu, a shop or the pause screen is up.
    try:
        if pc.bStatusMenuOpen is True or pc.WorldInfo.Pauser is not None:
            menu_was_open = True
            return

        # Straight after the mission log closes, the panel is worked out again, so
        # picking a different mission shows up at once.
        if menu_was_open:
            menu_was_open = False
            next_build = 0.0

        # A shop screen counts too. Asking the game which screen it is playing every
        # frame is too slow, so it is asked now and then and only the answer is kept.
        now = time.monotonic()
        if now - shop_asked >= SHOP_SECONDS:
            shop_asked = now
            shop_open = False
            for manager in unrealsdk.find_all("WillowGFxUIManager"):
                try:
                    playing = manager.GetPlayingMovie()
                except Exception:
                    continue
                if playing is None:
                    continue
                if "VendingMachine" in str(playing.Class.Name):
                    shop_open = True
                    break

        if shop_open:
            return
    except Exception:
        pass

    canvas = __args.Canvas
    if canvas is None:
        return

    now = time.monotonic()
    if now >= next_build:
        next_build = now + REFRESH_SECONDS
        find_definitions()
        fresh = build_lines()
        if fresh != cached_lines:
            cached_lines = fresh
            trimmed_lines = None

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
                for colour in (WHITE, GOLD, GREY, RED, GREEN, BLUE, BLACK)
            }

        y = PANEL_TOP

        canvas.Font = font

        # Each line is measured so the warning can start where it ends. Measuring is
        # not cheap, so it is done once for each new set of lines rather than every
        # frame.
        if trimmed_lines is None:
            trimmed_lines = []
            for text, colour, warn in cached_lines:
                line = text
                try:
                    width = float(canvas.TextSize(line, TEXT_SCALE, TEXT_SCALE)[1])
                except Exception:
                    width = len(line) * 10.0

                # The warning goes on the same row, straight after the mission, and
                # the panel grows to fit it rather than cutting it short.
                after = f"  |  {WARNING_TEXT}" if warn else ""
                after_width = 0.0
                if after:
                    try:
                        after_width = float(canvas.TextSize(after, TEXT_SCALE, TEXT_SCALE)[1])
                    except Exception:
                        after_width = len(after) * 10.0
                trimmed_lines.append((line, colour, after, width, width + after_width))

        # Lines past the bottom of the screen cannot be seen, and drawing them
        # still costs, so the list stops where the screen does.
        bottom = float(canvas.SizeY) - LINE_HEIGHT

        # Asking the game for a command costs more than the command does, so both
        # are asked for once and used for the whole panel.
        set_pos = canvas.SetPos
        draw_text = canvas.DrawText

        widest = max([PANEL_WIDTH] + [row[4] for row in trimmed_lines])
        where = Position.value
        if where == "Top left":
            left = PANEL_MARGIN
        elif where == "Top centre":
            left = (canvas.SizeX - widest) / 2
        else:
            left = canvas.SizeX - widest - PANEL_MARGIN

        showing = []
        warnings = []
        for line, colour, after, width, _whole in trimmed_lines:
            if y > bottom:
                break
            showing.append((line, colour, y))
            if after:
                warnings.append((after, left + width, y))
            y += LINE_HEIGHT

        # A black pass all the way round first, so the words stand out against
        # whatever is behind them. Every line of it under the one colour, since
        # handing the game a colour costs as much as the drawing does.
        canvas.DrawColor = colours[BLACK]
        for line, _colour, at in showing:
            for across, down in OUTLINE_STEPS:
                set_pos(left + across, at + down)
                draw_text(line, False, TEXT_SCALE, TEXT_SCALE)
        for after, start, at in warnings:
            for across, down in OUTLINE_STEPS:
                set_pos(start + across, at + down)
                draw_text(after, False, TEXT_SCALE, TEXT_SCALE)

        together: dict[tuple[int, int, int], list] = {}
        for line, colour, at in showing:
            together.setdefault(colour, []).append((line, at))

        for colour, rows in together.items():
            canvas.DrawColor = colours[colour]
            for line, at in rows:
                set_pos(left, at)
                draw_text(line, False, TEXT_SCALE, TEXT_SCALE)

        if warnings:
            canvas.DrawColor = colours[RED]
            for after, start, at in warnings:
                set_pos(start, at)
                draw_text(after, False, TEXT_SCALE, TEXT_SCALE)
    except Exception as ex:
        logging.dev_warning(f"[Mission Progress] could not draw ({ex})")


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

build_mod(
    options=[EnableDLC, ShowSkipped, ShowWarnings, EnableSide, NextCount, Position],
    keybinds=[],
    hooks=[on_render],
    commands=[],
    settings_file=Path(f"{SETTINGS_DIR}/MissionProgress.json"),
)

logging.info(f"Mission Progress Loaded: {__version__}, {__version_info__}")
