from pathlib import Path

import unrealsdk  # type: ignore
from unrealsdk import logging  # type: ignore

from mods_base import SETTINGS_DIR, build_mod
from mods_base.options import BoolOption, ButtonOption

# The chests, as the game names them.
RED_CHEST = "InteractiveObj_TreasureChest"
WHITE_CHEST = "InteractiveObj_Crate_Metal"

# What the game calls a chest that is shut and one that has been opened.
SHUT = "closed"
OPENED = "Opened"

ResetRed = BoolOption("Reset Red Chests", True, "Yes", "No")
ResetWhite = BoolOption("Reset White Chests", True, "Yes", "No")


def wanted(definition: str) -> bool:
    if RED_CHEST in definition:
        return ResetRed.value is True
    if WHITE_CHEST in definition:
        return ResetWhite.value is True
    return False


def shut_them() -> int:
    """Puts every opened chest in the area back to shut, and says how many."""
    done = 0

    for chest in unrealsdk.find_all("WillowInteractiveObject"):
        try:
            if chest.bCanBeUsed is True:
                continue
            if not wanted(str(chest.InteractiveObjectDefinition)):
                continue
        except Exception:
            continue

        # The game keeps a chest's open and shut states as its own named sets, and
        # switching to the shut one plays the lid closing on its own.
        try:
            chest.DisableBehaviorSet(OPENED)
            chest.EnableBehaviorSet(SHUT)
        except Exception as ex:
            logging.dev_warning(f"[Reset Chests] could not switch a chest ({ex})")
            continue

        try:
            chest.bCanBeUsed = True
            done += 1
        except Exception:
            continue

    return done


def on_reset(option) -> None:
    shut_them()


Reset = ButtonOption("Reset Chests in This Area", on_press=on_reset)


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

build_mod(
    options=[Reset, ResetRed, ResetWhite],
    keybinds=[],
    hooks=[],
    commands=[],
    settings_file=Path(f"{SETTINGS_DIR}/ResetChests.json"),
)

logging.info(f"Reset Chests Loaded: {__version__}, {__version_info__}")
