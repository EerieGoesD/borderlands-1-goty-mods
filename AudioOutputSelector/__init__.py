import ctypes
import json
from ctypes import wintypes
from pathlib import Path

import unrealsdk  # type: ignore
from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import SETTINGS_DIR, build_mod, hook
from mods_base.options import ButtonOption, SliderOption, SpinnerOption

LABEL = "Audio Output Selector"
SETTINGS = Path(f"{SETTINGS_DIR}/AudioOutputSelector.json")
GROUP_NAME = "Audio Output Device"
DEVICE_NAME = "Device"

# Shown until the game's sound is up and the devices can be listed.
SEARCHING = "Searching..."

POINTER = ctypes.sizeof(ctypes.c_void_p)
FMOD_OK = 0

# How far past the game's audio object to look for its link to the sound library.
LOOK_PAST = 0x200


def sound_library():
    """The game's sound library and the few calls this mod uses, or None."""
    try:
        if POINTER == 4:
            dll = ctypes.WinDLL("fmodex.dll")

            def call(name: str, arg_bytes: int):
                return dll[f"_{name}@{arg_bytes}"]
        else:
            dll = ctypes.WinDLL("fmodex64.dll")

            def call(name: str, arg_bytes: int):
                return dll[name]

        calls = {
            "version": (call("FMOD_System_GetVersion", 8), [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint)]),
            "count": (call("FMOD_System_GetNumDrivers", 8), [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]),
            "current": (call("FMOD_System_GetDriver", 8), [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]),
            "pick": (call("FMOD_System_SetDriver", 8), [ctypes.c_void_p, ctypes.c_int]),
            "info": (
                call("FMOD_System_GetDriverInfo", 20),
                [ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p],
            ),
            "master": (
                call("FMOD_System_GetMasterChannelGroup", 8),
                [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)],
            ),
            "volume": (call("FMOD_ChannelGroup_SetVolume", 8), [ctypes.c_void_p, ctypes.c_float]),
        }
        for function, args in calls.values():
            function.argtypes = args
            function.restype = ctypes.c_int
        return {name: function for name, (function, _args) in calls.items()}, dll._handle
    except Exception as ex:
        logging.dev_warning(f"[{LABEL}] could not reach the sound library ({ex})")
        return None


library = sound_library()

kernel = ctypes.WinDLL("kernel32")
kernel.GetCurrentProcess.restype = wintypes.HANDLE
kernel.ReadProcessMemory.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]
kernel.ReadProcessMemory.restype = wintypes.BOOL
psapi = ctypes.WinDLL("psapi")


class ModuleInfo(ctypes.Structure):
    _fields_ = [("base", ctypes.c_void_p), ("size", wintypes.DWORD), ("entry", ctypes.c_void_p)]


def library_range() -> tuple[int, int] | None:
    """Where the sound library sits in memory."""
    if library is None:
        return None
    info = ModuleInfo()
    if not psapi.GetModuleInformation(
        kernel.GetCurrentProcess(),
        ctypes.c_void_p(library[1]),
        ctypes.byref(info),
        ctypes.sizeof(info),
    ):
        return None
    return (info.base, info.base + info.size)


def read_pointer(address: int) -> int | None:
    """Reads one pointer. A bad address gives None rather than taking the game down."""
    value = ctypes.c_void_p(0)
    got = ctypes.c_size_t(0)
    ok = kernel.ReadProcessMemory(
        kernel.GetCurrentProcess(),
        ctypes.c_void_p(address),
        ctypes.byref(value),
        POINTER,
        ctypes.byref(got),
    )
    if not ok or got.value != POINTER:
        return None
    return value.value or 0


def sound_system() -> int | None:
    """The game's own sound system, found fresh each time and never kept."""
    if library is None:
        return None
    where = library_range()
    if where is None:
        return None

    device = None
    for found in unrealsdk.find_all("FMODAudioDevice"):
        if not str(found.Name).startswith("Default__"):
            device = found
            break
    if device is None:
        return None

    base = device._get_address()
    end = int(device.Class.PropertySize) + LOOK_PAST
    calls = library[0]

    # The device holds a few of the library's objects. The sound system is the one
    # the library itself answers to.
    for offset in range(0, end, POINTER):
        candidate = read_pointer(base + offset)
        if not candidate:
            continue
        first = read_pointer(candidate)
        if first is None or not (where[0] <= first < where[1]):
            continue
        version = ctypes.c_uint(0)
        if calls["version"](candidate, ctypes.byref(version)) == FMOD_OK:
            return candidate
    return None


def device_names(system: int) -> list[str]:
    """Every output device, in the library's own order."""
    calls = library[0]
    count = ctypes.c_int(0)
    if calls["count"](system, ctypes.byref(count)) != FMOD_OK:
        return []

    names: list[str] = []
    for index in range(count.value):
        raw = ctypes.create_string_buffer(256)
        if calls["info"](system, index, raw, 256, None) != FMOD_OK:
            name = f"Device {index + 1}"
        else:
            name = raw.value.decode("utf-8", "replace") or f"Device {index + 1}"
        # Two devices with the same name still need telling apart.
        if name in names:
            name = f"{name} ({names.count(name) + 1})"
        names.append(name)
    return names


def current_device(system: int) -> int:
    current = ctypes.c_int(-1)
    if library[0]["current"](system, ctypes.byref(current)) != FMOD_OK:
        return -1
    return current.value


def switch_to(name: str) -> None:
    """Moves the game's sound to the named device."""
    system = sound_system()
    if system is None:
        return
    names = device_names(system)
    if name not in names:
        return
    index = names.index(name)
    if index == current_device(system):
        return
    result = library[0]["pick"](system, index)
    if result != FMOD_OK:
        logging.dev_warning(f"[{LABEL}] could not switch to {name} (error {result})")
        return
    set_volume(Volume.value)


def set_volume(percent: float) -> None:
    """Sets the volume of everything the game plays."""
    system = sound_system()
    if system is None:
        return
    calls = library[0]
    master = ctypes.c_void_p(0)
    if calls["master"](system, ctypes.byref(master)) != FMOD_OK or not master.value:
        return
    result = calls["volume"](master, ctypes.c_float(max(0.0, min(100.0, float(percent))) / 100.0))
    if result != FMOD_OK:
        logging.dev_warning(f"[{LABEL}] could not set the volume (error {result})")


def saved_device() -> str | None:
    """The device picked last time, read straight from the settings file."""
    try:
        options = json.loads(SETTINGS.read_text(encoding="utf-8")).get("options", {})
        value = options.get(DEVICE_NAME)
        # Saved by the first test build, which kept the device inside a group.
        group = options.get(GROUP_NAME)
        if not value and isinstance(group, dict):
            value = group.get(DEVICE_NAME)
        return str(value) if value else None
    except Exception:
        return None


# Set while the list is being filled in, so filling it does not count as a pick.
filling = False

# How many frames to keep looking for the game's sound before giving up.
LOOKS = 600
looks = 0


def fill_list(system: int) -> list[str]:
    """Puts the devices in the list, keeping the picked one when it is still there."""
    global filling

    names = device_names(system)
    if not names:
        return names

    pick = Device.value
    if pick not in names:
        # Nothing saved, or that device is gone, so the list starts on the one in use.
        current = current_device(system)
        pick = names[current] if 0 <= current < len(names) else names[0]

    filling = True
    try:
        Device.choices = names
        Device.value = pick
    finally:
        filling = False
    return names


def on_apply(option: ButtonOption) -> None:
    if Device.value != SEARCHING:
        switch_to(Device.value)


def on_scan(option: ButtonOption) -> None:
    system = sound_system()
    if system is not None:
        fill_list(system)


wanted = saved_device()

# The heading on one row and the device on the row below it, so a long device name
# has the whole row to itself. The heading is a row that does nothing when pressed.
Heading = ButtonOption(GROUP_NAME)
Device = SpinnerOption(
    DEVICE_NAME,
    wanted or SEARCHING,
    [wanted or SEARCHING],
    wrap_enabled=True,
    display_name="",
)
Apply = ButtonOption("Apply", on_press=on_apply)
Scan = ButtonOption("Scan Devices", on_press=on_scan)


def on_volume(option: SliderOption, percent: float) -> None:
    set_volume(percent)


Volume = SliderOption("Master Volume", 100, 0, 100, 1, True, on_change_anytime=on_volume)


@hook(hook_func="Engine.GameViewportClient:PostRender", hook_type=Type.POST)
def on_render(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    """Once the game's sound is up, lists the devices and moves to the saved one."""
    global looks

    looks += 1
    system = sound_system()
    if system is None:
        if looks >= LOOKS:
            logging.dev_warning(f"[{LABEL}] could not find the game's sound")
            on_render.disable()
        return

    saved = Device.value
    names = fill_list(system)
    if not names:
        return

    set_volume(Volume.value)
    if saved in names:
        switch_to(saved)

    # Done for this session.
    try:
        on_render.disable()
    except Exception as ex:
        logging.dev_warning(f"[{LABEL}] could not stop looking ({ex})")


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

build_mod(
    options=[Heading, Device, Apply, Scan, Volume],
    keybinds=[],
    hooks=[on_render],
    commands=[],
    settings_file=SETTINGS,
)

logging.info(f"Audio Output Selector Loaded: {__version__}, {__version_info__}")
