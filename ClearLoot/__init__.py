from pathlib import Path

import unrealsdk  # type: ignore
from unrealsdk import logging  # type: ignore

from mods_base import SETTINGS_DIR, build_mod
from mods_base.options import ButtonOption

# What the game calls an item lying on the ground.
PICKUP = "WillowPickup"

# The game takes a dropped item away itself once its time runs out. Asking it to
# remove one outright is refused, so the time is set to almost nothing instead and
# the game clears it the way it clears old loot.
MOMENT = 0.01


def clear_them() -> int:
    """Marks every item lying in the area to be taken away, and says how many."""
    done = 0

    # Everything is dealt with here and now. Keeping an item until a later frame
    # takes the game down, since the game is free to let go of it in between.
    for pickup in unrealsdk.find_all(PICKUP):
        try:
            if str(pickup.Name).startswith("Default__"):
                continue
            if pickup.bDeleteMe is True or pickup.bPendingDelete is True:
                continue
            # Part of the level itself rather than something dropped.
            if pickup.bStatic is True or pickup.bNoDelete is True:
                continue

            pickup.LifeSpan = MOMENT
            done += 1
        except Exception as ex:
            logging.dev_warning(f"[Clear Loot] could not clear an item ({ex})")
            continue

    return done


def on_clear(option) -> None:
    clear_them()


Clear = ButtonOption("Clear Loot in This Area", on_press=on_clear)


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

build_mod(
    options=[Clear],
    keybinds=[],
    hooks=[],
    commands=[],
    settings_file=Path(f"{SETTINGS_DIR}/ClearLoot.json"),
)

logging.info(f"Clear Loot Loaded: {__version__}, {__version_info__}")
