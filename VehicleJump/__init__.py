from pathlib import Path

import unrealsdk  # type: ignore
from unrealsdk import logging  # type: ignore

from mods_base import SETTINGS_DIR, build_mod, get_pc, keybind
from mods_base.options import SliderOption

# What the game calls a car you are sitting in.
VEHICLE = "WillowVehicle"

JumpHeight = SliderOption("Jump Height", 800, 200, 10000, 10, True)


def in_a_vehicle(pawn) -> bool:
    try:
        return VEHICLE in str(pawn.Class.Name)
    except Exception:
        return False


@keybind("Vehicle Jump", "SpaceBar")
def on_jump() -> None:
    """Throws the vehicle upwards."""
    pc = get_pc()
    if pc is None or pc.Pawn is None:
        return

    if not in_a_vehicle(pc.Pawn):
        return

    # A car is a physics body, so its own Velocity field is not what moves it.
    try:
        mesh = pc.Pawn.Mesh
        if mesh is None:
            return
        up = unrealsdk.make_struct("Vector", X=0.0, Y=0.0, Z=float(JumpHeight.value))
        here = unrealsdk.make_struct("Vector", X=0.0, Y=0.0, Z=0.0)
        mesh.AddImpulse(up, here, "", True)
    except Exception as ex:
        logging.dev_warning(f"[Vehicle Jump] could not jump ({ex})")


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

build_mod(
    options=[JumpHeight],
    keybinds=[on_jump],
    hooks=[],
    commands=[],
    settings_file=Path(f"{SETTINGS_DIR}/VehicleJump.json"),
)

logging.info(f"Vehicle Jump Loaded: {__version__}, {__version_info__}")
