"""The Borderlands mission flow.

Each entry is a main story mission followed by the side missions that open up alongside it.
Order matches the flow on the Borderlands wiki.
"""

BASE_FLOW: list[tuple[str, list[str]]] = [
    ("Fresh Off The Bus", []),
    ("The Doctor Is In", []),
    ("Claptrap Rescue", []),
    ("Skags At The Gate", []),
    ("Fix'er Upper", []),
    ("Blinding Nine-Toes", []),
    ("Nine-Toes: Meet T.K. Baha", []),
    ("Nine-Toes: T.K.'s Food", []),
    ("Got Grenades?", []),
    ("Nine-Toes: Take Him Down", []),
    ("Nine-Toes: Time To Collect", []),
    (
        "Job Hunting",
        [
            "T.K. Has More Work",
            "Why Are They Here?",
            "T.K.'s Life And Limb",
            "By The Seeds Of Your Pants",
        ],
    ),
    ("Catch-A-Ride", []),
    ("Bone Head's Theft", ["Get A Little Blood On The Tires"]),
    (
        "The Piss Wash Hurdle",
        [
            "Hidden Journal: The Arid Badlands",
            "Claptrap Rescue: The Lost Cave",
            "Shock Crystal Harvest",
        ],
    ),
    ("Return To Zed", []),
    ("Sledge: Meet Shep", ["Braking Wind", "Get The Flock Outta Here"]),
    (
        "Sledge: The Mine Key",
        [
            "Scavenger: Sniper Rifle",
            "The Legend Of Moe and Marley",
            "Circle Of Death: Meat And Greet",
            "Circle Of Death: Round 1",
            "Circle Of Death: Round 2",
            "Circle Of Death: Final Round",
        ],
    ),
    (
        "Sledge: To The Safe House",
        [
            "Claptrap Rescue: Safe House",
            "Scavenger: Combat Rifle",
            "What Hit The Fan",
        ],
    ),
    (
        "Sledge: Battle For The Badlands",
        [
            "Find Bruce McClane",
            "Product Recall",
            "Insult To Injury",
            "Schemin' That Sabotage",
        ],
    ),
    ("Leaving Fyrestone", ["Big Game Hunter"]),
    ("Getting Lucky", []),
    (
        "Powering The Fast Travel Network",
        [
            "Scavenger: Revolver",
            "Fuel Feud",
            "Death Race Pandora",
            "Ghosts Of The Vault",
            "Well There's Your Problem Right There",
        ],
    ),
    ("Road Warriors: Hot Shots", []),
    (
        "Road Warriors: Bandit Apocalypse",
        [
            "Claptrap Rescue: New Haven",
            "King Tossing",
            "Corrosive Crystal Harvest",
            "Claptrap Rescue: Tetanus Warren",
            "Like A Moth To Flame",
            "Is T.K. O.K.?",
        ],
    ),
    (
        "Power To The People",
        [
            "Scooter's Used Car Parts",
            "Up To Our Ears",
            "Firepower: All Sales Are Final",
            "Firepower: Market Correction",
            "Firepower: Plight Of The Middle Man",
            "Jack's Other Eye",
            "Scavenger: Submachine Gun",
            "Hidden Journal: Rust Commons West",
        ],
    ),
    ("Seek Out Tannis", []),
    (
        "Meet 'Crazy' Earl",
        ["Today's Lesson: High Explosives", "Claptrap Rescue: Scrapyard"],
    ),
    ("Get Off My Lawn!", []),
    (
        "Hair Of The Dog",
        [
            "Missing Persons",
            "Two Wrongs Make A Right",
            "Middle Of Nowhere No More: Investigate",
            "Middle Of Nowhere No More: Fuses? Really?",
            "Middle Of Nowhere No More: Small Favor",
            "Middle Of Nowhere No More: Scoot On Back",
            "Altar Ego: Burning Heresy",
            "Scavenger: Shotgun",
            "Hidden Journal: Rust Commons East",
            "Circle Of Slaughter: Meat and Greet",
            "Circle Of Slaughter: Round 1",
            "Circle Of Slaughter: Round 2",
            "Circle Of Slaughter: Final Round",
            "Earl Needs Food...Badly",
            "Claptrap Rescue: Krom's Canyon",
        ],
    ),
    ("The Next Piece", []),
    (
        "Jaynistown: Secret Rendezvous",
        [
            "Relight The Beacons",
            "A Bug Problem",
            "Altar Ego: The New Religion",
            "Altar Ego: Godless Monsters",
            "Smoke Signals: Investigate Old Haven",
            "Smoke Signals: Shut Them Down",
            "Bandit Treasure: Three Corpses, Three Keys",
            "Bandit Treasure: X Marks The Spot",
            "Green Thumb",
        ],
    ),
    ("Jaynistown: A Brother's Love", []),
    ("Jaynistown: Spread The Word", ["Dumpster Diving For Great Justice"]),
    (
        "Jaynistown: Getting What's Coming To You",
        ["Wanted: Fresh Fish", "I've Got A Sinking Feeling..."],
    ),
    ("Jaynistown: Unintended Consequences", []),
    (
        "Jaynistown: Cleaning Up Your Mess",
        [
            "Claptrap Rescue: Trash Coast",
            "Bait And Switch",
            "Earl's Best Friend",
            "House Hunting",
        ],
    ),
    ("Another Piece Of The Puzzle", []),
    ("Not Without My Claptrap", ["Claptrap Rescue: Old Haven"]),
    (
        "The Final Piece",
        [
            "Claptrap Rescue: The Salt Flats",
            "Scavenger: Machine Gun",
            "Claptrap Rescue: Crimson Fastness",
        ],
    ),
    ("Get Some Answers", []),
    ("Find the ECHO Command Console", []),
    ("Reactivate the ECHO Comm System", []),
    ("Find Steele", []),
    ("Destroy The Destroyer", []),
    ("Bring The Vault Key To Tannis", []),
]

NED_FLOW: list[tuple[str, list[str]]] = [
    ("Welcoming Committee", []),
    (
        "Is The Doctor In?",
        [
            "Eggcellent Opportunity!",
            "Pumpkinhead",
            "Missing: Hank Reiss",
            "TK Lives!",
            "Brains",
            "Braaains",
            "Braaaaains",
            "Braaaaaaaaaaaains",
            "Braaaaaaaaaaaaaaaaains",
        ],
    ),
    ("House of the Ned", ["Leave It To The Professionals"]),
    ("There May Be Some Side Effects...", ["It's Alive!", "The Pack"]),
    ("Secrets and Mysteries", []),
    ("Jakobs Fodder", ["Upsale"]),
    ("Hitching A Ride", ["Here We Go Again"]),
    ("A Bridge Too Ned", ["Claptrap Rescue: The Lumber Yard"]),
    ("Night of the Living Ned", []),
    ("Ned's undead, baby, Ned's undead", []),
]

MOXXI_FLOW: list[tuple[str, list[str]]] = [
    ("Prove Yourself.", []),
]

KNOXX_FLOW: list[tuple[str, list[str]]] = [
    (
        "Scooter?  But I Don't Even Know Her.",
        ["Big Crimson Brother is Watching", "Wanted: Dead!"],
    ),
    ("Boost the Monster", ["Core Collection"]),
    ("Greasemonkey", []),
    ("You've Got Moxxi: Roadblock", []),
    ("You've Got Moxxi: Moxxi's Red Light", []),
    (
        "Prison Break: Road Warrior",
        [
            "Road Rage",
            "Power Leech",
            "OMG APC",
            "Purple Juice!",
            "Little People, Big Experiments",
        ],
    ),
    ("Prison Break: Over the Wall", ["Claptrap Rescue: Lockdown Palace"]),
    ("Prison Break: Try Not to Get Shanked", []),
    (
        "Rendezvous",
        ["This Bitch is Payback", "This Bitch is Payback, pt. 2"],
    ),
    ("Code Breaker: Analysis", []),
    ("Code Breaker: Time is Bullets", []),
    (
        "Athena Set Up Us The Bomb",
        ["Drifter Lifter", "Knoxxed Out", "Thrown for a Loop"],
    ),
    ("Bridging the Gap", ["Bugged", "Stain Removal", "Lost Lewts"]),
    ("Armory Assault", []),
    (
        "Loot Larceny",
        [
            "You. Will. Die.",
            "Mop Up",
            "Super-Marcus Sweep",
            "Local Trouble",
            "It's Like Christmas!",
            "Circle of Duty: New Recruit",
            "Circle of Duty: Cadet",
            "Circle of Duty: Private",
            "Circle of Duty: Corporal",
            "Circle of Duty: Sergeant",
            "Circle of Duty: Medal of Duty",
        ],
    ),
]

CLAPTRAP_FLOW: list[tuple[str, list[str]]] = [
    (
        "Are You From These Parts?",
        [
            "Fight For Your Right To Part-E",
            "Parts Is Parts",
            "We All Have Our Part To Play",
            "A Part Of Something Larger Than Yourself",
        ],
    ),
    (
        "New Contact",
        [
            "Like Shootin' Rakk In A Barrel",
            "Spa Vs. Spa",
            "Burnin' Rubber",
        ],
    ),
    (
        "Operation Trap Claptrap Trap, Phase One",
        ["One-UpmanPipp", "It's A Trap... Clap", "Finger Lickin' Bad!"],
    ),
    (
        "Operation Trap Claptrap Trap, Phase Two: Industrial Revolution",
        ["Taking Stock"],
    ),
    (
        "Operation Trap Claptrap Trap, Phase Three: TripWIRED",
        ["Not My Fault", "Old Spicy", "Eleven Rakk And Spices"],
    ),
    ("Operation Trap Claptrap Trap, Phase Four: Reboot", []),
    ("Helping Is Its Own Reward... Wait No It Isn't!", []),
]

DLC_FLOW: list[tuple[str, list[str]]] = (
    NED_FLOW + MOXXI_FLOW + KNOXX_FLOW + CLAPTRAP_FLOW
)


# Each mission's level on playthrough 1 and playthrough 2, from the Borderlands wiki.
# A mission the wiki gives no second level for keeps its first.
LEVELS: dict[str, tuple[int, int]] = {
    "Fresh Off The Bus": (2, 34),
    "The Doctor Is In": (2, 34),
    "Claptrap Rescue": (2, 34),
    "Skags At The Gate": (2, 34),
    "Fix'er Upper": (2, 34),
    "Blinding Nine-Toes": (2, 34),
    "Nine-Toes: Meet T.K. Baha": (3, 37),
    "Nine-Toes: T.K.'s Food": (2, 34),
    "Got Grenades?": (2, 34),
    "Nine-Toes: Take Him Down": (4, 34),
    "Nine-Toes: Time To Collect": (7, 35),
    "Job Hunting": (7, 35),
    "T.K. Has More Work": (10, 36),
    "Why Are They Here?": (7, 35),
    "T.K.'s Life And Limb": (7, 35),
    "By The Seeds Of Your Pants": (9, 36),
    "Catch-A-Ride": (7, 35),
    "Bone Head's Theft": (10, 36),
    "Get A Little Blood On The Tires": (10, 36),
    "The Piss Wash Hurdle": (10, 36),
    "Hidden Journal: The Arid Badlands": (13, 38),
    "Claptrap Rescue: The Lost Cave": (15, 38),
    "Shock Crystal Harvest": (15, 38),
    "Return To Zed": (10, 36),
    "Sledge: Meet Shep": (10, 36),
    "Braking Wind": (10, 36),
    "Get The Flock Outta Here": (10, 36),
    "Sledge: The Mine Key": (10, 36),
    "Scavenger: Sniper Rifle": (12, 37),
    "The Legend Of Moe and Marley": (15, 39),
    "Circle Of Death: Meat And Greet": (12, 37),
    "Circle Of Death: Round 1": (12, 37),
    "Circle Of Death: Round 2": (15, 39),
    "Circle Of Death: Final Round": (18, 40),
    "Sledge: To The Safe House": (14, 37),
    "Claptrap Rescue: Safe House": (14, 37),
    "Scavenger: Combat Rifle": (15, 39),
    "What Hit The Fan": (13, 38),
    "Sledge: Battle For The Badlands": (17, 39),
    "Find Bruce McClane": (15, 39),
    "Product Recall": (15, 39),
    "Insult To Injury": (15, 39),
    "Schemin' That Sabotage": (18, 40),
    "Leaving Fyrestone": (18, 40),
    "Big Game Hunter": (20, 41),
    "Getting Lucky": (18, 40),
    "Powering The Fast Travel Network": (20, 41),
    "Scavenger: Revolver": (20, 41),
    "Fuel Feud": (18, 40),
    "Death Race Pandora": (20, 41),
    "Ghosts Of The Vault": (20, 41),
    "Well There's Your Problem Right There": (18, 40),
    "Road Warriors: Hot Shots": (18, 40),
    "Road Warriors: Bandit Apocalypse": (20, 41),
    "Claptrap Rescue: New Haven": (21, 42),
    "King Tossing": (21, 42),
    "Corrosive Crystal Harvest": (21, 42),
    "Claptrap Rescue: Tetanus Warren": (21, 42),
    "Like A Moth To Flame": (21, 42),
    "Is T.K. O.K.?": (21, 42),
    "Power To The People": (20, 41),
    "Scooter's Used Car Parts": (21, 42),
    "Up To Our Ears": (21, 42),
    "Firepower: All Sales Are Final": (21, 42),
    "Firepower: Market Correction": (21, 42),
    "Firepower: Plight Of The Middle Man": (23, 43),
    "Jack's Other Eye": (23, 43),
    "Scavenger: Submachine Gun": (23, 43),
    "Hidden Journal: Rust Commons West": (23, 43),
    "Seek Out Tannis": (21, 42),
    "Meet 'Crazy' Earl": (22, 42),
    "Today's Lesson: High Explosives": (22, 42),
    "Claptrap Rescue: Scrapyard": (22, 42),
    "Get Off My Lawn!": (22, 42),
    "Hair Of The Dog": (23, 43),
    "Missing Persons": (24, 44),
    "Two Wrongs Make A Right": (25, 44),
    "Middle Of Nowhere No More: Investigate": (24, 44),
    "Middle Of Nowhere No More: Fuses? Really?": (24, 44),
    "Middle Of Nowhere No More: Small Favor": (24, 44),
    "Middle Of Nowhere No More: Scoot On Back": (24, 44),
    "Altar Ego: Burning Heresy": (24, 44),
    "Scavenger: Shotgun": (24, 44),
    "Hidden Journal: Rust Commons East": (26, 45),
    "Circle Of Slaughter: Meat and Greet": (26, 45),
    "Circle Of Slaughter: Round 1": (26, 45),
    "Circle Of Slaughter: Round 2": (29, 47),
    "Circle Of Slaughter: Final Round": (28, 48),
    "Earl Needs Food...Badly": (25, 44),
    "Claptrap Rescue: Krom's Canyon": (25, 44),
    "The Next Piece": (25, 44),
    "Jaynistown: Secret Rendezvous": (27, 46),
    "Relight The Beacons": (27, 46),
    "A Bug Problem": (27, 46),
    "Altar Ego: The New Religion": (27, 46),
    "Altar Ego: Godless Monsters": (29, 47),
    "Smoke Signals: Investigate Old Haven": (28, 48),
    "Smoke Signals: Shut Them Down": (28, 48),
    "Bandit Treasure: Three Corpses, Three Keys": (28, 48),
    "Bandit Treasure: X Marks The Spot": (28, 48),
    "Green Thumb": (29, 47),
    "Jaynistown: A Brother's Love": (27, 46),
    "Jaynistown: Spread The Word": (27, 46),
    "Dumpster Diving For Great Justice": (27, 46),
    "Jaynistown: Getting What's Coming To You": (27, 46),
    "Wanted: Fresh Fish": (27, 46),
    "I've Got A Sinking Feeling...": (27, 46),
    "Jaynistown: Unintended Consequences": (27, 46),
    "Jaynistown: Cleaning Up Your Mess": (29, 47),
    "Claptrap Rescue: Trash Coast": (27, 46),
    "Bait And Switch": (27, 46),
    "Earl's Best Friend": (27, 46),
    "House Hunting": (27, 46),
    "Another Piece Of The Puzzle": (27, 47),
    "Not Without My Claptrap": (28, 48),
    "Claptrap Rescue: Old Haven": (28, 48),
    "The Final Piece": (30, 49),
    "Claptrap Rescue: The Salt Flats": (29, 48),
    "Scavenger: Machine Gun": (30, 49),
    "Claptrap Rescue: Crimson Fastness": (30, 49),
    "Get Some Answers": (30, 49),
    "Find the ECHO Command Console": (31, 49),
    "Reactivate the ECHO Comm System": (31, 49),
    "Find Steele": (32, 50),
    "Destroy The Destroyer": (32, 50),
    "Bring The Vault Key To Tannis": (32, 50),
    "Welcoming Committee": (10, 42),
    "Is The Doctor In?": (20, 42),
    "Eggcellent Opportunity!": (10, 42),
    "Pumpkinhead": (20, 42),
    "Missing: Hank Reiss": (10, 42),
    "TK Lives!": (20, 42),
    "Brains": (35, 42),
    "Braaains": (20, 42),
    "Braaaaains": (20, 42),
    "Braaaaaaaaaaaains": (20, 42),
    "Braaaaaaaaaaaaaaaaains": (25, 42),
    "House of the Ned": (10, 42),
    "Leave It To The Professionals": (21, 43),
    "There May Be Some Side Effects...": (21, 43),
    "It's Alive!": (26, 43),
    "The Pack": (26, 43),
    "Secrets and Mysteries": (26, 43),
    "Jakobs Fodder": (26, 43),
    "Upsale": (25, 42),
    "Hitching A Ride": (26, 43),
    "Here We Go Again": (27, 44),
    "A Bridge Too Ned": (27, 44),
    "Claptrap Rescue: The Lumber Yard": (37, 44),
    "Night of the Living Ned": (27, 44),
    "Ned's undead, baby, Ned's undead": (27, 44),
    "Prove Yourself.": (15, 15),
    "Scooter?  But I Don't Even Know Her.": (35, 51),
    "Big Crimson Brother is Watching": (35, 51),
    "Wanted: Dead!": (35, 51),
    "Boost the Monster": (35, 51),
    "Core Collection": (35, 51),
    "Greasemonkey": (35, 51),
    "You've Got Moxxi: Roadblock": (35, 51),
    "You've Got Moxxi: Moxxi's Red Light": (35, 51),
    "Prison Break: Road Warrior": (37, 53),
    "Road Rage": (37, 53),
    "Power Leech": (37, 53),
    "OMG APC": (37, 53),
    "Purple Juice!": (37, 53),
    "Little People, Big Experiments": (37, 53),
    "Prison Break: Over the Wall": (37, 53),
    "Claptrap Rescue: Lockdown Palace": (37, 53),
    "Prison Break: Try Not to Get Shanked": (37, 53),
    "Rendezvous": (37, 53),
    "This Bitch is Payback": (37, 53),
    "This Bitch is Payback, pt. 2": (38, 55),
    "Code Breaker: Analysis": (37, 53),
    "Code Breaker: Time is Bullets": (37, 53),
    "Athena Set Up Us The Bomb": (38, 55),
    "Drifter Lifter": (38, 55),
    "Knoxxed Out": (38, 55),
    "Thrown for a Loop": (38, 55),
    "Bridging the Gap": (38, 55),
    "Bugged": (38, 55),
    "Stain Removal": (38, 55),
    "Lost Lewts": (37, 53),
    "Armory Assault": (38, 55),
    "Loot Larceny": (38, 55),
    "You. Will. Die.": (61, 61),
    "Mop Up": (38, 61),
    "Super-Marcus Sweep": (38, 61),
    "Local Trouble": (38, 60),
    "It's Like Christmas!": (38, 38),
    "Circle of Duty: New Recruit": (38, 61),
    "Circle of Duty: Cadet": (38, 38),
    "Circle of Duty: Private": (38, 38),
    "Circle of Duty: Corporal": (38, 38),
    "Circle of Duty: Sergeant": (38, 38),
    "Circle of Duty: Medal of Duty": (38, 38),
    "Are You From These Parts?": (37, 42),
    "Fight For Your Right To Part-E": (37, 42),
    "Parts Is Parts": (38, 43),
    "We All Have Our Part To Play": (40, 44),
    "A Part Of Something Larger Than Yourself": (40, 44),
    "New Contact": (37, 42),
    "Like Shootin' Rakk In A Barrel": (38, 43),
    "Spa Vs. Spa": (37, 42),
    "Burnin' Rubber": (38, 43),
    "Operation Trap Claptrap Trap, Phase One": (38, 43),
    "One-UpmanPipp": (38, 43),
    "It's A Trap... Clap": (38, 43),
    "Finger Lickin' Bad!": (38, 43),
    "Operation Trap Claptrap Trap, Phase Two: Industrial Revolution": (38, 43),
    "Taking Stock": (38, 43),
    "Operation Trap Claptrap Trap, Phase Three: TripWIRED": (40, 44),
    "Not My Fault": (38, 43),
    "Old Spicy": (40, 44),
    "Eleven Rakk And Spices": (38, 43),
    "Operation Trap Claptrap Trap, Phase Four: Reboot": (40, 44),
    "Helping Is Its Own Reward... Wait No It Isn't!": (40, 44),
}


class Flow:
    """The mission order, flattened and indexed, with or without the DLC and sides.

    Given a playthrough, the order is by that playthrough's level instead, with the
    flow deciding between missions that share a level.
    """

    def __init__(
        self,
        include_dlc: bool,
        include_sides: bool = True,
        by_level: int | None = None,
    ) -> None:
        flow = BASE_FLOW + (DLC_FLOW if include_dlc else [])
        if not include_sides:
            flow = [(main, []) for main, _ in flow]

        self.main: list[str] = [name for name, _ in flow]
        self.flat: list[str] = [
            name for main, sides in flow for name in (main, *sides)
        ]
        self.kind: dict[str, str] = {}
        for main, sides in flow:
            self.kind[main] = "Main"
            for side in sides:
                self.kind[side] = "Side"

        if by_level is not None:
            flow_place = {name: index for index, name in enumerate(self.flat)}

            def key(name: str) -> tuple[int, int]:
                return (level_of(name, by_level), flow_place[name])

            self.main = sorted(self.main, key=key)
            self.flat = sorted(self.flat, key=key)

        self.position: dict[str, int] = {
            name: index for index, name in enumerate(self.flat)
        }


def level_of(name: str, playthrough: int) -> int:
    """The level a mission is pitched at on the given playthrough, 0 for the first."""
    first, second = LEVELS.get(name, (0, 0))
    return second if playthrough >= 1 else first


flows: dict[tuple[bool, bool, int | None], Flow] = {}


def flow_for(include_dlc: bool, include_sides: bool, by_level: int | None) -> Flow:
    """The flow for these settings, built once and kept."""
    want = (include_dlc, include_sides, by_level)
    found = flows.get(want)
    if found is None:
        found = Flow(include_dlc, include_sides, by_level)
        flows[want] = found
    return found


BASE_ONLY = Flow(False)
WITH_DLC = Flow(True)

# The same two again with the side missions left out.
BASE_ONLY_MAIN = Flow(False, False)
WITH_DLC_MAIN = Flow(True, False)

ALL_MISSIONS: list[str] = WITH_DLC.flat
