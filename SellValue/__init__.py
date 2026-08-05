import re
from pathlib import Path

from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import SETTINGS_DIR, build_mod, hook
from mods_base.options import SliderOption

FLASH_CARD = "topLevel_mc.card"
PICKUP_CARD = "inventory.card1"

LABEL = "Sells For"
COLOUR = "#ff4040"

TAGS = re.compile(r"<[^>]+>")

# One paragraph of the card's text. The game rewrites whatever we put there into its
# own wrapping, so a whole paragraph is taken at a time and read without its tags.
BLOCK = re.compile(r"<TEXTFORMAT.*?</TEXTFORMAT>|<font.*?</font>", re.IGNORECASE | re.DOTALL)


def without_ours(text: str) -> str:
    """The card's text with our own line taken out, however the game has written it."""

    def drop(match: re.Match[str]) -> str:
        plain = TAGS.sub("", match.group(0)).strip()
        return "" if plain.startswith(LABEL) else match.group(0)

    return "\n".join(line for line in BLOCK.sub(drop, text).split("\n") if line.strip())

FontSize = SliderOption("Sell value font size", 9, 0, 24, 1, True)

# The item you started a comparison from.
comparing_item: UObject | None = None


def get_string(movie: UObject, path: str) -> str:
    try:
        return str(movie.GetVariableString(path))
    except Exception:
        return ""


def can_be_sold(item: UObject) -> bool:
    """Ammo and storage upgrades are used the moment you buy them, so they never
    reach your bag and there is nothing to sell back."""
    try:
        name = str(item.DefinitionData.ItemDefinition.Name)
    except Exception:
        # Weapons keep their definition elsewhere, and every weapon can be sold.
        return True

    return not name.startswith(("AmmoDrop_", "AmmoShop_", "INV_SDU_"))


def sell_price(item: UObject | None) -> int | None:
    """What a shop hands over for it. That is the item's own worth."""
    if item is None or not can_be_sold(item):
        return None
    try:
        return int(item.CashValue)
    except Exception:
        return None


def apply_line(movie: UObject, card: str, item: UObject | None) -> None:
    path = f"{card}.funstats.htmlText"
    text = without_ours(get_string(movie, path))

    price = sell_price(item)
    if price is not None:
        line = f'<font size="{FontSize.value}" color="{COLOUR}">{LABEL} ${price:,}</font>'
        text = f"{line}\n{text}" if text else line

    try:
        movie.SetVariableString(path, text)
    except Exception as ex:
        logging.dev_warning(f"[Sell Value] could not write the card ({ex})")


def highlighted_item(movie: UObject) -> UObject | None:
    """The backpack tracks the highlighted item itself, shops keep it in a list."""
    try:
        return movie.GetCurrentHighlightedObject()
    except AttributeError:
        pass

    try:
        if movie.bOnItemOfTheDay is True:
            return movie.ItemOfTheDayData.Item
        return movie.ActiveTextList.GetHighlightedObject()
    except Exception:
        return None


def update_cards(movie: UObject) -> None:
    item = highlighted_item(movie)
    if item is None:
        return

    try:
        comparing = movie.IsComparing() is True
    except Exception:
        comparing = False

    if comparing:
        # Card 1 is what you started comparing from, card 2 is the highlighted item.
        if comparing_item is not None:
            apply_line(movie, f"{FLASH_CARD}1", comparing_item)
        apply_line(movie, f"{FLASH_CARD}2", item)
    else:
        apply_line(movie, f"{FLASH_CARD}1", item)


@hook(
    hook_func="WillowGame.StatusMenuExGFxMovie:UpdateCardPanelWithCurrentCell",
    hook_type=Type.POST,
)
def on_card_key(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    update_cards(obj)


@hook(
    hook_func="WillowGame.StatusMenuExGFxMovie:UpdateCardPanelWithCurrentActiveListEntry",
    hook_type=Type.POST,
)
def on_card_mouse(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    update_cards(obj)


@hook(
    hook_func="WillowGame.StatusMenuExGFxMovie:extSetMouseOverCell",
    hook_type=Type.POST,
)
def on_card_hover(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    update_cards(obj)


@hook(
    hook_func="WillowGame.StatusMenuExGFxMovie:extCompare",
    hook_type=Type.PRE,
)
def on_compare_start(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    global comparing_item
    comparing_item = highlighted_item(obj)


@hook(
    hook_func="WillowGame.StatusMenuExGFxMovie:extCard2Visible",
    hook_type=Type.POST,
)
def on_compare(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    update_cards(obj)


@hook(
    hook_func="WillowGame.VendingMachineGFxMovie:UpdateCardPanelWithItemOfTheDay",
    hook_type=Type.POST,
)
def on_vendor_daily(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    update_cards(obj)


@hook(
    hook_func="WillowGame.VendingMachineGFxMovie:UpdateCardPanelWithCurrentActiveListEntry",
    hook_type=Type.POST,
)
def on_vendor_item(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    update_cards(obj)


@hook(
    hook_func="WillowGame.VendingMachineGFxMovie:extSetMouseOverCell",
    hook_type=Type.POST,
)
def on_vendor_hover(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    update_cards(obj)


@hook(
    hook_func="WillowGame.VendingMachineGFxMovie:extCompare",
    hook_type=Type.PRE,
)
def on_vendor_compare_start(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    global comparing_item
    comparing_item = highlighted_item(obj)


@hook(
    hook_func="WillowGame.VendingMachineGFxMovie:extCard2Visible",
    hook_type=Type.POST,
)
def on_vendor_compare(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    update_cards(obj)


@hook(
    hook_func="WillowGame.ItemPickupGFxMovie:UpdateCompareAgainstThing",
    hook_type=Type.POST,
)
def on_pickup_card(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    """The card the game shows over loot on the ground."""
    try:
        ground_item = obj.MyHUDOwner.ItemComparison[0]
    except Exception:
        return

    apply_line(obj, PICKUP_CARD, ground_item)


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

build_mod(
    options=[FontSize],
    keybinds=[],
    hooks=[
        on_card_key,
        on_card_mouse,
        on_card_hover,
        on_compare_start,
        on_compare,
        on_vendor_daily,
        on_vendor_item,
        on_vendor_hover,
        on_vendor_compare_start,
        on_vendor_compare,
        on_pickup_card,
    ],
    commands=[],
    settings_file=Path(f"{SETTINGS_DIR}/SellValue.json"),
)

logging.info(f"Sell Value Loaded: {__version__}, {__version_info__}")
