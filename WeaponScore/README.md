# Gear Score

Rates every weapon by DPS and shield by Shield Power according to in-game formula, on item cards wherever you see it.

The number shows on item cards in your backpack, in vending machines, on mission rewards
and on loot lying on the ground. Page Up and Page Down in the backpack reach a DPS page,
listing everything you carry best first.

Weapons: `shots x damage x pellets / (shots x fire interval + reload)`, where shots is
the magazine divided by the ammo each shot costs. Shields:
`capacity + recharge rate x (60 - recharge delay)`. Every number comes off the item
itself, unrounded, so it can differ slightly from the card.

## Settings

- **Disregard Accuracy**: Assumes every bullet hits. Turn it off and the DPS is scaled by the gun's accuracy.
- **Disregard Critical**: Ignores critical hits. Turn it off and the DPS is multiplied by the gun's own critical bonus, as if every shot were a critical.
- **Disregard Elements**: Ignores burn, shock and corrosion. Turn it off and the extra damage an elemental gun throws is added, scaled by its x1 to x4 rating.
- **Score font size**: How big the number is printed on the card.

## Install

Copy the mod's folder into `Borderlands\sdk_mods`, then start the game. It appears in
the SDK Mod Manager on the main menu.

Needs the [BL1 PythonSDK](https://github.com/bl-sdk/willow1-mod-manager).

## Contact

Questions or feedback: eeriegoesd@gmail.com or [eeriegoesd.com](https://eeriegoesd.com)

## Support

If you'd like to support my mods, feel free to [buy me a coffee](https://buymeacoffee.com/eeriegoesd).
