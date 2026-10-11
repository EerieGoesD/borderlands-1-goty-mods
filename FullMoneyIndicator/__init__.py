import time
from pathlib import Path

import unrealsdk  # type: ignore
from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import SETTINGS_DIR, Game, build_mod, get_pc, hook

LABEL = "Full Money Indicator"
FONT = "ui_fonts.font_willowbody_18pt"
GOLD = (255, 210, 0)

# How far the amount sits above the bottom of the screen, in pixels at 1920x1080.
# Enhanced puts its level and XP bar lower, so the amount goes under that bar there.
# Older copies of the SDK do not know Enhanced by name, so it is asked for carefully.
ON_ENHANCED = getattr(Game, "BL1E", None) is not None and Game.get_current() is Game.BL1E
BOTTOM_MARGIN = 18 if ON_ENHANCED else 60

# The screen size the text is sized for. Other sizes scale it to match.
BASE_WIDTH = 1920.0
BASE_HEIGHT = 1080.0

# How often the amount is read again, in seconds.
READ_SECONDS = 0.25

# The most money the game can hold. One more dollar and the game's own count wraps
# round to a large negative number, so a negative count is put back to this top.
MOST_MONEY = 2147483647

font = None
colour = None

# The amount last read, the text drawn for it and how wide that text is. Only
# numbers and text are kept, never the game's objects.
money = None
text = ""
width = 0.0
height = 0.0
read_at = 0.0


def read_money() -> int | None:
    pc = get_pc()
    try:
        pri = pc.PlayerReplicationInfo
        amount = int(pri.CurrencyOnHand)
        if amount < 0:
            pri.CurrencyOnHand = MOST_MONEY
            amount = MOST_MONEY
            logging.info(f"[{LABEL}] money had gone past the top and turned negative, put back to ${MOST_MONEY:,}")
        return amount
    except Exception:
        return None


@hook(hook_func="Engine.GameViewportClient:PostRender", hook_type=Type.POST)
def on_render(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    global font, colour, money, text, width, height, read_at

    pc = get_pc()
    # No character in the world means the main menu or a loading screen.
    if pc is None or pc.Pawn is None:
        return

    canvas = __args.Canvas
    if canvas is None:
        return

    try:
        if font is None:
            font = unrealsdk.find_object("Font", FONT)
            colour = unrealsdk.make_struct("Color", R=GOLD[0], G=GOLD[1], B=GOLD[2], A=255)
        canvas.Font = font

        now = time.monotonic()
        if now - read_at >= READ_SECONDS:
            read_at = now
            amount = read_money()
            if amount is not None and amount != money:
                money = amount
                text = f"${amount:,}"
                # Measured once for each new amount, not every frame.
                size = canvas.TextSize(text, 1.0, 1.0)
                width = float(size[1])
                height = float(size[2])
        if not text:
            return

        screen_x = float(canvas.SizeX)
        screen_y = float(canvas.SizeY)
        scale = min(screen_x / BASE_WIDTH, screen_y / BASE_HEIGHT)
        x = (screen_x - width * scale) / 2
        y = screen_y - (height + BOTTOM_MARGIN) * scale

        canvas.DrawColor = colour
        canvas.SetPos(x, y)
        canvas.DrawText(text, False, scale, scale)
    except Exception as ex:
        logging.dev_warning(f"[{LABEL}] could not draw ({ex})")


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

build_mod(
    options=[],
    keybinds=[],
    hooks=[on_render],
    commands=[],
    settings_file=Path(f"{SETTINGS_DIR}/FullMoneyIndicator.json"),
)

logging.info(f"Full Money Indicator Loaded: {__version__}, {__version_info__}")
