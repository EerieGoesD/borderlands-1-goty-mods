from pathlib import Path

import unrealsdk  # type: ignore
from unrealsdk import logging  # type: ignore

from mods_base import SETTINGS_DIR, build_mod, get_pc
from mods_base.options import ButtonOption

LABEL = "Open All Chests"

# The chests, as the game names them: red, white, the Knoxx DLC's, and strong boxes.
CHESTS = (
    "InteractiveObj_TreasureChest",
    "InteractiveObj_Crate_Metal",
    "InteractiveObj_crimson_Chest",
    "InteractiveObj_StrongBox",
)

# Units in a metre, for the note on any chest that stays shut.
UNITS_PER_METRE = 50.0


def open_them() -> int:
    """Opens every shut chest in the area the same way pressing Use on it does, and
    says how many."""
    pc = get_pc()
    if pc is None or pc.Pawn is None:
        return 0
    pawn = pc.Pawn
    here = pawn.Location
    here_x, here_y, here_z = float(here.X), float(here.Y), float(here.Z)

    done = 0
    stuck: list[str] = []
    for chest in unrealsdk.find_all("WillowInteractiveObject"):
        try:
            if chest.bCanBeUsed is not True:
                continue
            definition = str(chest.InteractiveObjectDefinition)
            if not any(name in definition for name in CHESTS):
                continue
        except Exception:
            continue

        try:
            answer = chest.UsedBy(pawn)
        except Exception as ex:
            answer = f"failed ({ex})"
        try:
            still_shut = chest.bCanBeUsed is True
            spot = chest.Location
            metres = (
                (float(spot.X) - here_x) ** 2 + (float(spot.Y) - here_y) ** 2 + (float(spot.Z) - here_z) ** 2
            ) ** 0.5 / UNITS_PER_METRE
        except Exception:
            still_shut, metres = True, -1.0
        if still_shut:
            name = definition.split(".")[-1].rstrip("'")
            stuck.append(f"{name} {metres:.0f} m away, answer {answer}")
        else:
            done += 1

    logging.info(f"[{LABEL}] opened {done} chests, {len(stuck)} stayed shut")
    for line in stuck[:20]:
        logging.info(f"[{LABEL}] stayed shut: {line}")
    return done


def on_open(option) -> None:
    open_them()


OpenAll = ButtonOption("Open Chests in This Area", on_press=on_open)


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

build_mod(
    options=[OpenAll],
    keybinds=[],
    hooks=[],
    commands=[],
    settings_file=Path(f"{SETTINGS_DIR}/OpenAllChests.json"),
)

logging.info(f"Open All Chests Loaded: {__version__}, {__version_info__}")
