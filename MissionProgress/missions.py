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
    ("Jaynistown: A Brother's Love", ["Dumpster Diving For Great Justice"]),
    ("Jaynistown: Spread The Word", []),
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
    (
        "House of the Ned",
        ["Leave It To The Professionals", "Here We Go Again"],
    ),
    ("There May Be Some Side Effects...", ["It's Alive!", "The Pack"]),
    ("Secrets and Mysteries", []),
    ("Jakobs Fodder", ["Upsale"]),
    ("Hitching A Ride", []),
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


class Flow:
    """The mission order, flattened and indexed, with or without the DLC."""

    def __init__(self, include_dlc: bool) -> None:
        flow = BASE_FLOW + (DLC_FLOW if include_dlc else [])

        self.main: list[str] = [name for name, _ in flow]
        self.flat: list[str] = [
            name for main, sides in flow for name in (main, *sides)
        ]
        self.position: dict[str, int] = {
            name: index for index, name in enumerate(self.flat)
        }
        self.kind: dict[str, str] = {}
        for main, sides in flow:
            self.kind[main] = "Main"
            for side in sides:
                self.kind[side] = "Side"


BASE_ONLY = Flow(False)
WITH_DLC = Flow(True)

ALL_MISSIONS: list[str] = WITH_DLC.flat
