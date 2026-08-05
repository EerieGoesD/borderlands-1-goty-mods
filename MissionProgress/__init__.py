from pathlib import Path

import unrealsdk  # type: ignore
from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import SETTINGS_DIR, build_mod, get_pc, hook
from mods_base.options import BoolOption, SliderOption, SpinnerOption

from .missions import ALL_MISSIONS, BASE_ONLY, WITH_DLC

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

# Longest line that fits the panel, anything past this is cut short.
MAX_CHARS = 46

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

# How often the panel and the mission lookup refresh, in frames.
REFRESH_FRAMES = 300

# How often we check whether a shop screen is up, in frames. Looking for one means
# going through everything the game holds, which is the dearest thing here.
SHOP_FRAMES = 90

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

definitions: dict[str, UObject] = {}

frames = REFRESH_FRAMES
cached_lines: list[tuple[str, tuple[int, int, int]]] = []
trimmed_lines = None

# Whether a shop screen is up, and the count until that is asked again. Only the
# answer is kept, never the screens themselves, since those belong to the area you
# are in and asking one of them anything after you leave takes the game down.
shop_open = False
shop_frames = SHOP_FRAMES

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
    global frames, cached_lines, trimmed_lines, shop_open, shop_frames

    pc = get_pc()
    if pc is None or pc.myHUD is None:
        return

    # No character in the world means the main menu or a loading screen.
    if pc.Pawn is None:
        return

    # Out of the way while a menu, a shop or the pause screen is up.
    try:
        if pc.bStatusMenuOpen is True or pc.WorldInfo.Pauser is not None:
            return

        # A shop screen counts too. Hunting for one every frame is far too slow, so
        # it is asked now and then and only the yes or no is kept.
        shop_frames += 1
        if shop_frames >= SHOP_FRAMES:
            shop_frames = 0
            shop_open = False
            for shop in unrealsdk.find_all("VendingMachineGFxMovie"):
                try:
                    if "Default__" in str(shop.Name):
                        continue
                    if shop.bMovieIsOpen is True:
                        shop_open = True
                        break
                except Exception:
                    continue

        if shop_open:
            return
    except Exception:
        pass

    canvas = __args.Canvas
    if canvas is None:
        return

    frames += 1
    if frames >= REFRESH_FRAMES:
        frames = 0
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

        where = Position.value
        if where == "Top left":
            left = PANEL_MARGIN
        elif where == "Top centre":
            left = (canvas.SizeX - PANEL_WIDTH) / 2
        else:
            left = canvas.SizeX - PANEL_WIDTH - PANEL_MARGIN

        y = PANEL_TOP

        canvas.Font = font

        # A line wider than the panel wraps round to the far side of the screen, so
        # it is cut short until it fits. Measuring is not cheap, so it is done once
        # for each new set of lines rather than every frame.
        if trimmed_lines is None:
            trimmed_lines = []
            for text, colour in cached_lines:
                line = text
                for _ in range(len(text)):
                    try:
                        width = float(canvas.TextSize(line, TEXT_SCALE, TEXT_SCALE)[0])
                    except Exception:
                        # No measurement to be had, so the character cap has to do.
                        break
                    if width <= PANEL_WIDTH or len(line) <= 4:
                        break
                    line = line[:-4] + "..."
                trimmed_lines.append((line, colour))

        for line, colour in trimmed_lines:
            # A black pass all the way round first, so the words stand out against
            # whatever is behind them.
            canvas.DrawColor = colours[BLACK]
            for across, down in OUTLINE_STEPS:
                canvas.SetPos(left + across, y + down)
                canvas.DrawText(line, False, TEXT_SCALE, TEXT_SCALE)

            canvas.DrawColor = colours[colour]
            canvas.SetPos(left, y)
            canvas.DrawText(line, False, TEXT_SCALE, TEXT_SCALE)
            y += LINE_HEIGHT
    except Exception as ex:
        logging.dev_warning(f"[Mission Progress] could not draw ({ex})")


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

build_mod(
    options=[EnableDLC, ShowSkipped, ShowWarnings, NextCount, Position],
    keybinds=[],
    hooks=[on_render],
    commands=[],
    settings_file=Path(f"{SETTINGS_DIR}/MissionProgress.json"),
)

logging.info(f"Mission Progress Loaded: {__version__}, {__version_info__}")
