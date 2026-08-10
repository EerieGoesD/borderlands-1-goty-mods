from pathlib import Path

import unrealsdk  # type: ignore
from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import SETTINGS_DIR, build_mod, get_pc, hook
from mods_base.options import ButtonOption, DropdownOption

# 4 is finished, 2 is done and waiting to be handed in, 1 is under way.
STATUS_COMPLETE = 4
STATUS_READY = 2
STATUS_ACTIVE = 1

NOTHING = "None found"

# The missions in your record, by the name shown in your log.
finished: dict[str, object] = {}


def gather() -> list[str]:
    """Every mission your record knows about, whatever state it is in."""
    finished.clear()

    pc = get_pc()
    if pc is None:
        return [NOTHING]

    try:
        runs = pc.MissionPlaythroughData
    except Exception:
        return [NOTHING]

    for run in runs:
        try:
            entries = run.MissionList
        except Exception:
            continue
        for entry in entries:
            try:
                mission = entry.MissionDef
                name = str(mission.MissionName)
            except Exception:
                continue
            if name:
                finished[name] = mission

    return sorted(finished) or [NOTHING]


def on_refresh(_option) -> None:
    """Looks again at what you have finished, and puts it in the list."""
    names = gather()
    Pick.choices = names
    if Pick.value not in names:
        Pick.value = names[0]


def fresh_counters(pc, mission) -> bool:
    """Puts blank counters back on the mission's record.

    The game reads these the moment a mission goes live, and a finished record
    carries none, which is what took the game down. One is borrowed from a mission
    under way where there is one, since a real one is safer than a made up one, and
    blank ones are made only when everything you have is finished.
    """
    count = len(list(mission.Objectives))

    donor = None
    for run in pc.MissionPlaythroughData:
        for entry in run.MissionList:
            try:
                held = list(entry.Objectives)
            except Exception:
                continue
            if held:
                donor = held[0]
                break
        if donor is not None:
            break

    for run in pc.MissionPlaythroughData:
        entries = run.MissionList
        for index in range(len(entries)):
            try:
                if entries[index].MissionDef is not mission:
                    continue

                if donor is not None:
                    entries[index].Objectives = [donor] * count
                else:
                    # Nothing to copy from, so blank ones are made instead.
                    held = entries[index].Objectives
                    while len(held) > 0:
                        del held[0]
                    for _ in range(count):
                        held.emplace_struct()

                held = entries[index].Objectives
                for spot in range(len(held)):
                    held[spot].CurrentAmount = 0
            except Exception:
                continue

    # Only say yes when the counters really are there.
    for run in pc.MissionPlaythroughData:
        for entry in run.MissionList:
            try:
                if entry.MissionDef is mission and len(list(entry.Objectives)) == count:
                    return True
            except Exception:
                continue
    return False


def set_status(status: int) -> None:
    """Puts the chosen mission back to the given state."""
    mission = finished.get(Pick.value)
    if mission is None:
        return

    pc = get_pc()

    # Starting over needs the counters back first. Without them the game goes down
    # the moment anything looks at the mission.
    if status == STATUS_ACTIVE and not fresh_counters(pc, mission):
        logging.dev_warning("[Repeat Mission] could not give it fresh counters")
        return

    # The game keeps each mission's record by its place in your list, and changing it
    # through the game's own call is the only way that sticks.
    try:
        where = int(pc.GetMissionIndexForMission(mission))
    except Exception:
        where = -1

    if where >= 0:
        try:
            pc.SetMissionStatus(where, status)
        except Exception as ex:
            logging.dev_warning(f"[Repeat Mission] could not set the status ({ex})")

    # Forcing it on top only suits a mission that is already done.
    if status != STATUS_ACTIVE:
        try:
            pc.ForceMissionStatus(mission, status)
        except Exception:
            pass

    # A finished mission comes off the tracker, so the compass stops pointing at it
    # and the game picks whatever you are on instead.
    if status == STATUS_COMPLETE:
        try:
            tracker = list(unrealsdk.find_all("MissionTracker"))[-1]
            tracker.RemoveMission(mission)
        except Exception:
            pass

        try:
            pc.RemoveMissionFromClient(mission)
        except Exception:
            pass

        try:
            pc.ValidateActiveMission()
        except Exception:
            pass

        try:
            tracker = list(unrealsdk.find_all("MissionTracker"))[-1]
            tracker.UpdateObjective()
        except Exception:
            pass

    # The log only lists missions the tracker is holding, so it gets put back too.
    if status in (STATUS_READY, STATUS_ACTIVE):
        try:
            tracker = list(unrealsdk.find_all("MissionTracker"))[-1]
            tracker.AddMission(mission)
            pc.SetActiveMission(mission)
        except Exception:
            pass

        # Picking it in the log is what moves the compass, so that is done too, and
        # the tracker is told to work out where it now points.
        try:
            pc.PlayerSetMissionToTrack(mission)
        except Exception as ex:
            logging.dev_warning(f"[Repeat Mission] could not track it ({ex})")

        try:
            tracker = list(unrealsdk.find_all("MissionTracker"))[-1]
            tracker.UpdateObjective()
        except Exception:
            pass


def on_repeat(_option) -> None:
    set_status(STATUS_ACTIVE)


def on_ready(_option) -> None:
    set_status(STATUS_READY)


def on_complete(_option) -> None:
    set_status(STATUS_COMPLETE)


Pick = DropdownOption("Mission", NOTHING, [NOTHING])
Repeat = ButtonOption("Repeat Selected Mission", on_press=on_repeat)
Ready = ButtonOption("Ready to Turn In", on_press=on_ready)
Complete = ButtonOption("Mark Complete", on_press=on_complete)
Refresh = ButtonOption("Refresh the List", on_press=on_refresh)


@hook(
    hook_func="WillowGame.WillowGFxMenuScreenGeneric:Screen_Activate",
    hook_type=Type.PRE,
    immediately_enable=True,
)
def on_menu_screen(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    """The list is filled in just before a menu screen is drawn, so it is ready the
    first time you open the mod's settings rather than the second."""
    on_refresh(Refresh)


def on_enable() -> None:
    on_refresh(Refresh)


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

build_mod(
    options=[Pick, Repeat, Ready, Complete, Refresh],
    keybinds=[],
    hooks=[],
    commands=[],
    on_enable=on_enable,
    settings_file=Path(f"{SETTINGS_DIR}/RepeatMission.json"),
)

logging.info(f"Repeat Mission Loaded: {__version__}, {__version_info__}")
