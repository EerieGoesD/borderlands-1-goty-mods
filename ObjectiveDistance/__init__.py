from pathlib import Path

import unrealsdk  # type: ignore
from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Type  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import SETTINGS_DIR, build_mod, get_pc, hook
from mods_base.options import BoolOption, SpinnerOption

FONT = "ui_fonts.font_willowbody_18pt"

# The game measures in its own units. Fifty of them make a metre.
UNITS_PER_METRE = 50.0
FEET_PER_METRE = 3.28084

TEXT_SCALE = 1.0
COLOUR = (255, 210, 0)

# Frames between recalculations.
REFRESH_FRAMES = 30

ShowDistance = BoolOption("Show Distance", True, "On", "Off")
ShowRoute = BoolOption("Show Route Line", True, "On", "Off")
Units = SpinnerOption("Units", value="Metres", choices=["Metres", "Feet"], wrap_enabled=True)
Position = SpinnerOption(
    "Position",
    value="Compass",
    choices=["Compass", "Top of screen"],
    wrap_enabled=True,
)
RouteColour = SpinnerOption(
    "Route Colour",
    value="Green",
    choices=["Green", "Blue", "Red", "Yellow", "Orange"],
    wrap_enabled=True,
)

# The bright core and the halo around it, for each choice.
ROUTE_COLOURS = {
    "Green": ((120, 255, 140), (0, 200, 40)),
    "Blue": ((140, 200, 255), (0, 90, 230)),
    "Red": ((255, 140, 140), (210, 0, 0)),
    "Yellow": ((255, 250, 150), (230, 200, 0)),
    "Orange": ((255, 200, 130), (240, 120, 0)),
}

# The compass bar, measured as a share of the screen.
COMPASS_CENTRE = 0.5
COMPASS_HALF_WIDTH = 0.143
COMPASS_TOP = 0.833
COMPASS_ARC = 45.0

# How far above the compass bar the reading sits.
COMPASS_LIFT = 40

# Where the top of screen reading sits.
TOP_HEIGHT = 90

# The route line.
ROUTE_MAX_POINTS = 45
ROUTE_LIFT = 12.0
ROUTE_SKIP = 250.0

# How far apart the line is sampled, and how far it looks for the floor.
ROUTE_STEP = 160.0
GROUND_REACH = 600.0

# How far you walk before the route is worked out again.
REBUILD_AFTER = 600.0

# Mission still being worked on, as opposed to done and waiting to be handed in.
STATUS_ACTIVE = 1

# How many nearby spots to try before giving up on finding one in plain sight,
# and how high off the floor to look from.
SIGHT_TRIES = 8
EYE_LIFT = 60.0

# Walking ground that leaves you this share of the distance away counts as a dead end.
DEAD_END_SHARE = 0.7

frames = REFRESH_FRAMES
cached_text = ""
cached_target = None


def loaded_levels() -> set[UObject]:
    """The levels the game currently has in play.

    Maps you visited earlier linger in memory with their own copies of the same waypoints,
    and those must not count.
    """
    levels: set[UObject] = set()
    try:
        info = get_pc().WorldInfo
    except Exception:
        return levels

    for attr in ("PersistentLevel",):
        level = getattr(info, attr, None)
        if level is not None:
            levels.add(level)

    try:
        for streaming in info.StreamingLevels:
            if streaming.bIsVisible is True and streaming.LoadedLevel is not None:
                levels.add(streaming.LoadedLevel)
    except Exception:
        pass

    return levels


def bearing_to(here, there) -> float:
    """How far left or right of where you are looking the target sits, in degrees."""
    import math

    try:
        angle = math.degrees(
            math.atan2(float(there.Y) - float(here.Y), float(there.X) - float(here.X)),
        )
        facing = float(get_pc().Rotation.Yaw) * 360.0 / 65536.0
    except Exception:
        return 0.0

    offset = (angle - facing + 180.0) % 360.0 - 180.0
    return offset


def distance_to(here, there) -> float | None:
    try:
        dx = float(here.X) - float(there.X)
        dy = float(here.Y) - float(there.Y)
        dz = float(here.Z) - float(there.Z)
    except Exception:
        return None
    return (dx * dx + dy * dy + dz * dz) ** 0.5


candidates: list[UObject] = []
turn_ins: list[UObject] = []
exits: list[UObject] = []
givers: list[UObject] = []
candidate_mission: UObject | None = None
candidate_levels: frozenset = frozenset()
candidate_targets: tuple = ()


def still_doing(mission: UObject) -> bool:
    """True while the objectives are still open, False once it is ready to hand in."""
    try:
        return get_pc().IsMissionInStatus(mission, STATUS_ACTIVE) is True
    except Exception:
        return True


def mission_targets(mission: UObject) -> tuple:
    """The waypoints the mission is pointing at right now."""
    found = [
        getattr(mission, field, None)
        for field in ("TargetWaypointDefinition", "TurnInWaypointDefinition")
    ]
    return tuple(definition for definition in found if definition is not None)


def collect_waypoints(mission: UObject, live: frozenset, targets: tuple) -> None:
    """The mission's own waypoints, which the game swaps out as objectives change."""
    global candidates, turn_ins

    candidates = []
    turn_ins = []

    hand_in = getattr(mission, "TurnInWaypointDefinition", None)

    for waypoint in unrealsdk.find_all("WillowWaypoint"):
        try:
            definition = waypoint.WaypointDefinition
            if definition not in targets:
                continue
            if live and waypoint.Outer not in live:
                continue
        except Exception:
            continue
        if definition is hand_in:
            turn_ins.append(waypoint)
        else:
            candidates.append(waypoint)


def collect_exits(mission: UObject, live: frozenset, targets: tuple) -> None:
    """The ways out of this area, which only change when the area does."""
    global exits, candidate_mission, candidate_levels, candidate_targets

    global givers

    exits = []
    givers = []
    candidate_mission = mission
    candidate_levels = live
    candidate_targets = targets

    for thing in unrealsdk.find_all("WillowInteractiveObject"):
        try:
            definition = str(thing.InteractiveObjectDefinition)
            if live and thing.Outer not in live:
                continue
        except Exception:
            continue
        if "MapChanger" in definition:
            exits.append(thing)
        elif "MissionDirector" in definition:
            givers.append(thing)


# Rebuilding the map's markers is not cheap, so the answer is kept between checks.
map_spot = None
map_for: tuple = ()


def map_waypoint(live: frozenset):
    """Where the map screen puts the waypoint marker.

    This is the game's own answer, and it covers the case where the objective sits in
    another area, since the map then marks the way through.
    """
    global map_spot, map_for

    found = None
    pc = get_pc()

    # Only worth rebuilding when the mission moved on or you changed area. With no
    # marker in hand it keeps asking, since a fresh area has none until the game
    # builds them.
    try:
        mission = list(unrealsdk.find_all("MissionTracker"))[-1].ActiveMission
        mark = (
            mission,
            getattr(mission, "TargetWaypointDefinition", None),
            getattr(mission, "TurnInWaypointDefinition", None),
            live,
        )
        if map_spot is not None and mark == map_for:
            return map_spot
        map_for = mark
    except Exception:
        return map_spot

    for helper in unrealsdk.find_all("WillowGFxHelperMap"):
        try:
            # Areas you have left keep their own copy, holding the waypoint they had
            # at the time. Only the one anchored in an area still in play counts.
            if helper.PlayerOwner is not pc:
                continue

            # Some areas give the map no anchor at all, so it only counts against a
            # helper when there is one to check.
            anchor = helper.Anchor
            if anchor is not None and live and anchor.Outer not in live:
                continue

            # Its list is only built when the map screen opens, and it keeps whatever
            # it held last time, so it gets asked for a fresh one every time.
            helper.FindObjects()
            things = list(helper.MapObjects)
        except Exception:
            continue

        for thing in things:
            try:
                if thing.bWaypoint is not True:
                    continue
                spot = thing.CustomObjectLoc
                if float(spot.X) == 0.0 and float(spot.Y) == 0.0:
                    continue
            except Exception:
                continue
            found = spot

    map_spot = found
    return found



def hand_in_spots(mission: UObject) -> list[UObject]:
    """The mission givers that match where this mission is handed in."""
    hand_in = getattr(mission, "TurnInWaypointDefinition", None)
    if hand_in is None:
        return []

    # WaypointDefinition'Z0_MissionData.Waypoints.WP_BountyBoard' becomes BountyBoard.
    word = str(hand_in).rsplit(".", 1)[-1].strip("'")
    if word.lower().startswith("wp_"):
        word = word[3:]
    if not word:
        return []

    return [
        giver
        for giver in givers
        if word.lower() in str(giver.InteractiveObjectDefinition).lower()
    ]


def waypoint_distance() -> float | None:
    """Distance to whatever the compass is pointing at, in game units.

    While the objective sits in another area the compass points at the way out, so the
    nearest of the mission's own waypoint and the exit is the one that counts.
    """
    global cached_target

    try:
        mission = list(unrealsdk.find_all("MissionTracker"))[-1].ActiveMission
        here = get_pc().Pawn.Location
    except Exception:
        return None

    # The route needs the walking network whichever way the target is found.
    live = frozenset(loaded_levels())
    if live != graph_levels:
        build_graph(live)

    # The map screen's own waypoint marker is the answer whenever it has one.
    spot = map_waypoint(live)

    if spot is not None:
        cached_target = spot
        return distance_to(here, spot)

    if mission is None:
        return None

    targets = mission_targets(mission)

    # The game swaps waypoints out as you go, so these get looked up every time.
    collect_waypoints(mission, live, targets)

    # Exits only change with the area.
    if (
        mission is not candidate_mission
        or live != candidate_levels
        or targets != candidate_targets
    ):
        collect_exits(mission, live, targets)

    # Once the objectives are done the compass points at the hand in, not at them.
    # The old objective markers stay in the world, so they are dropped entirely.
    order = (candidates, turn_ins, exits)
    if not still_doing(mission):
        # Ways out carry nothing about where they lead, so when the hand in is in
        # another area there is nothing honest to point at.
        order = (turn_ins, hand_in_spots(mission))

    best = None
    best_spot = None
    for group in order:
        for actor in group:
            try:
                # Parts of the objective you have already done stay in the world.
                if getattr(actor, "bCompleted", False) is True:
                    continue
                spot = actor.Location
                distance = distance_to(here, spot)
            except Exception:
                continue
            if distance is not None and (best is None or distance < best):
                best = distance
                best_spot = spot
        if best_spot is not None:
            break

    if best_spot is None:
        # Nothing valid left to point at, so stop pointing at the last one.
        cached_target = None
        return None

    cached_target = best_spot
    return best


graph_levels: frozenset = frozenset()
graph_pos: list[tuple[float, float, float]] = []
graph_links: list[list[tuple[int, float]]] = []
graph_back: list[list[tuple[int, float]]] = []

cached_route: list = []
route_from: tuple[float, float, float] | None = None
route_goal: tuple[float, float, float] | None = None


def build_graph(live: frozenset) -> None:
    """The walkable network the game's characters use, read once per area."""
    global graph_levels, graph_pos, graph_links, graph_back, cached_route, route_from

    graph_levels = live
    graph_pos = []
    graph_links = []
    graph_back = []
    cached_route = []
    route_from = None
    index: dict = {}
    nodes: list = []

    for node in unrealsdk.find_all("NavigationPoint", False):
        try:
            if live and node.Outer not in live:
                continue
            spot = node.Location
            here = (float(spot.X), float(spot.Y), float(spot.Z))
        except Exception:
            continue
        index[node] = len(nodes)
        nodes.append(node)
        graph_pos.append(here)

    for i, node in enumerate(nodes):
        links: list[tuple[int, float]] = []
        try:
            specs = node.PathList
        except Exception:
            specs = []
        for spec in specs:
            try:
                other = index.get(spec.End.Actor)
                if other is None or other == i:
                    continue
                cost = float(spec.Distance)
            except Exception:
                continue
            if cost <= 0:
                ax, ay, az = graph_pos[i]
                bx, by, bz = graph_pos[other]
                cost = ((ax - bx) ** 2 + (ay - by) ** 2 + (az - bz) ** 2) ** 0.5
            links.append((other, cost))
        graph_links.append(links)

    graph_back = [[] for _ in graph_pos]
    for i, links in enumerate(graph_links):
        for other, cost in links:
            graph_back[other].append((i, cost))


def nearest_node(point: tuple[float, float, float]) -> int:
    px, py, pz = point
    best = -1
    best_distance = 0.0
    for i, (x, y, z) in enumerate(graph_pos):
        gap = (x - px) ** 2 + (y - py) ** 2 + (z - pz) ** 2
        if best < 0 or gap < best_distance:
            best = i
            best_distance = gap
    return best


def nearest_nodes(point: tuple[float, float, float], count: int = 3) -> list[int]:
    """The closest few nodes, so a walled off one does not sink the search."""
    import heapq

    px, py, pz = point
    return heapq.nsmallest(
        count,
        range(len(graph_pos)),
        key=lambda i: (graph_pos[i][0] - px) ** 2
        + (graph_pos[i][1] - py) ** 2
        + (graph_pos[i][2] - pz) ** 2,
    )


def walk_towards(
    from_point: tuple[float, float, float],
    goal_point: tuple[float, float, float],
) -> list[tuple[float, float, float]]:
    """The walk from where you stand that gets you closest to the target."""
    import heapq

    start = nearest_node(from_point)
    if start < 0:
        return []

    queue = [(0.0, start)]
    came: dict[int, int] = {}
    best: dict[int, float] = {start: 0.0}

    while queue:
        _, current = heapq.heappop(queue)
        for step, cost in graph_links[current]:
            total = best[current] + cost
            if step in best and best[step] <= total:
                continue
            best[step] = total
            came[step] = current
            heapq.heappush(queue, (total, step))

    gx, gy, gz = goal_point
    finish = min(
        best,
        key=lambda node: (graph_pos[node][0] - gx) ** 2
        + (graph_pos[node][1] - gy) ** 2
        + (graph_pos[node][2] - gz) ** 2,
    )

    # If following this ground barely gets you any closer, it is a dead end and
    # showing it would send you the wrong way.
    yours = (
        (from_point[0] - gx) ** 2
        + (from_point[1] - gy) ** 2
        + (from_point[2] - gz) ** 2
    ) ** 0.5
    theirs = (
        (graph_pos[finish][0] - gx) ** 2
        + (graph_pos[finish][1] - gy) ** 2
        + (graph_pos[finish][2] - gz) ** 2
    ) ** 0.5
    if theirs > yours * DEAD_END_SHARE:
        return []

    path = [finish]
    while path[-1] != start:
        path.append(came[path[-1]])
    path.reverse()
    return [graph_pos[i] for i in path]


# The last worked out way to a target, kept so it is not redone every few steps.
search_goal = -1
search_best: dict[int, float] = {}
search_onward: dict[int, int] = {}
search_levels: frozenset = frozenset()


def set_search_levels() -> None:
    global search_levels
    search_levels = graph_levels


def find_route(
    from_point: tuple[float, float, float],
    goal: int,
) -> list[tuple[float, float, float]]:
    """Works out from the target across the whole network, then joins you to it.

    Starting at your end fails whenever you stand somewhere the game's characters
    cannot walk, such as a ledge you are meant to jump off.
    """
    import heapq

    global search_goal, search_best, search_onward

    if goal < 0:
        return []

    # The way there from every spot only depends on the target, so it is worked out
    # once and kept until the target changes.
    if goal != search_goal or search_levels != graph_levels:
        onward: dict[int, int] = {}
        best: dict[int, float] = {goal: 0.0}
        queue = [(0.0, goal)]

        while queue:
            _, current = heapq.heappop(queue)
            for step, cost in graph_back[current]:
                total = best[current] + cost
                if step in best and best[step] <= total:
                    continue
                best[step] = total
                onward[step] = current
                heapq.heappush(queue, (total, step))

        search_goal = goal
        search_best = best
        search_onward = onward
        set_search_levels()

    best = search_best
    onward = search_onward

    px, py, pz = from_point
    reachable = sorted(
        best,
        key=lambda node: (graph_pos[node][0] - px) ** 2
        + (graph_pos[node][1] - py) ** 2
        + (graph_pos[node][2] - pz) ** 2,
    )

    if not reachable:
        return []

    start = reachable[0]

    # The spot you are actually standing on comes first, so the whole line is ground
    # the game's own characters walk.
    mine = nearest_node(from_point)
    if mine in best:
        start = mine
    else:
        # Join to the nearest spot you can actually see, so the line never cuts
        # through a rock to reach the path.
        for node in reachable[:SIGHT_TRIES]:
            if in_sight(from_point, graph_pos[node]):
                start = node
                break

    # The ground near you may be a stretch of its own with no link to the target.
    # Then walk it as far as it goes in the target's direction.
    if mine not in best:
        walk = walk_towards(from_point, graph_pos[goal])
        if walk:
            return walk

        # Nowhere to walk from here, so point straight at the target for now
        # rather than showing nothing.
        start = reachable[0]

    path = [start]
    while path[-1] != goal:
        path.append(onward[path[-1]])
    return [graph_pos[i] for i in path]


def in_sight(
    here: tuple[float, float, float],
    there: tuple[float, float, float],
) -> bool:
    """Whether the two spots can see each other, with no wall in between."""
    try:
        pawn = get_pc().Pawn
        hit = pawn.Trace(
            unrealsdk.make_struct("Vector"),
            unrealsdk.make_struct("Vector"),
            unrealsdk.make_struct("Vector", X=there[0], Y=there[1], Z=there[2] + EYE_LIFT),
            unrealsdk.make_struct("Vector", X=here[0], Y=here[1], Z=here[2] + EYE_LIFT),
            False,
            unrealsdk.make_struct("Vector"),
        )
    except Exception:
        return True

    try:
        return hit[0] is None
    except Exception:
        return True


def ground_at(x: float, y: float, z: float) -> float:
    """The height of the floor under a spot, so the line hugs the terrain."""
    pc = get_pc()
    try:
        pawn = pc.Pawn
        hit = pawn.Trace(
            unrealsdk.make_struct("Vector"),
            unrealsdk.make_struct("Vector"),
            unrealsdk.make_struct("Vector", X=x, Y=y, Z=z - GROUND_REACH),
            unrealsdk.make_struct("Vector", X=x, Y=y, Z=z + GROUND_REACH),
            False,
            unrealsdk.make_struct("Vector"),
        )
    except Exception:
        return z

    try:
        if hit[0] is None:
            return z
        return float(hit[1].Z)
    except Exception:
        return z


def follow_ground(
    route: list[tuple[float, float, float]],
) -> list[tuple[float, float, float]]:
    """Fills in the gaps between waypoints and drops each one onto the floor."""
    if len(route) < 2:
        return route

    dense: list[tuple[float, float, float]] = []
    full = True

    for index in range(len(route) - 1):
        ax, ay, az = route[index]
        bx, by, bz = route[index + 1]
        span = ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5
        steps = max(int(span / ROUTE_STEP), 1)
        for part in range(steps):
            share = part / steps
            x = ax + (bx - ax) * share
            y = ay + (by - ay) * share
            z = az + (bz - az) * share
            dense.append((x, y, ground_at(x, y, z)))
        if len(dense) >= ROUTE_MAX_POINTS:
            full = False
            break

    # Only join up to the target when the whole way there fits. Otherwise the last
    # step would be one long straight jump hanging over the scenery.
    if full:
        endx, endy, endz = route[-1]
        dense.append((endx, endy, ground_at(endx, endy, endz)))

    return dense[:ROUTE_MAX_POINTS]


def refresh_route(here) -> None:
    """Works out the way to the target, only when something has actually moved on."""
    global cached_route, route_from, route_goal

    if cached_target is None or not graph_pos:
        cached_route = []
        return

    try:
        start_point = (float(here.X), float(here.Y), float(here.Z))
        goal_point = (
            float(cached_target.X),
            float(cached_target.Y),
            float(cached_target.Z),
        )
    except Exception:
        cached_route = []
        return

    # Rebuilding only pays off once you have actually walked a stretch.
    if (
        goal_point == route_goal
        and route_from is not None
    ):
        moved = (
            (start_point[0] - route_from[0]) ** 2
            + (start_point[1] - route_from[1]) ** 2
            + (start_point[2] - route_from[2]) ** 2
        ) ** 0.5
        if moved < REBUILD_AFTER:
            return

    route_from = start_point
    route_goal = goal_point

    route = []
    for last in nearest_nodes(goal_point, 3):
        route = find_route(start_point, last)
        if route:
            break

    # Show nothing when there is no way there on foot.
    if not route:
        cached_route = []
        return

    # Begin where you stand, so the first stretch follows the ground under your feet
    # instead of jumping to wherever the walking network starts. Only when the way
    # there is clear, otherwise that first leg would cut through the scenery.
    route = route[: ROUTE_MAX_POINTS - 2]
    if in_sight(start_point, route[0]):
        route = [start_point] + route

    # Always finish on the waypoint itself, not the walkable spot beside it.
    route.append(goal_point)

    cached_route = follow_ground(route)

    if DEBUG:
        logging.info(
            f" nodes={len(graph_pos)} route={len(cached_route)}"
            f" you={[round(v) for v in start_point]}"
            f" first={[round(v) for v in cached_route[0]] if cached_route else None}"
            f" second={[round(v) for v in cached_route[1]] if len(cached_route) > 1 else None}",
        )


green = None
glow = None
colour_name = ""
reported = 0

# Temporary: logs what the route finder came up with.
DEBUG = False


def draw_route(canvas, here) -> None:
    global green

    if not cached_route:
        return

    global glow, colour_name

    if green is None or colour_name != RouteColour.value:
        colour_name = RouteColour.value
        core, halo = ROUTE_COLOURS.get(colour_name, ROUTE_COLOURS["Green"])
        green = unrealsdk.make_struct("Color", R=core[0], G=core[1], B=core[2], A=255)
        glow = unrealsdk.make_struct("Color", R=halo[0], G=halo[1], B=halo[2], A=70)

    import math

    pc = get_pc()
    try:
        pawn = pc.Pawn
        eye = (
            float(pawn.Location.X),
            float(pawn.Location.Y),
            float(pawn.Location.Z) + float(pawn.EyeHeight),
        )
        rotation = pc.Rotation
        yaw = float(rotation.Yaw) * math.tau / 65536.0
        pitch = float(rotation.Pitch) * math.tau / 65536.0
        fov = float(pc.GetFOVAngle())
        width = float(canvas.SizeX)
        height = float(canvas.SizeY)
    except Exception:
        return

    forward = (
        math.cos(pitch) * math.cos(yaw),
        math.cos(pitch) * math.sin(yaw),
        math.sin(pitch),
    )
    right = (-math.sin(yaw), math.cos(yaw), 0.0)
    up = (
        -math.sin(pitch) * math.cos(yaw),
        -math.sin(pitch) * math.sin(yaw),
        math.cos(pitch),
    )
    focal = (width / 2.0) / math.tan(math.radians(fov) / 2.0)

    # The line always starts at your feet, so steps you have already walked past drop off.
    feet = (
        float(pawn.Location.X),
        float(pawn.Location.Y),
        float(pawn.Location.Z) - ROUTE_LIFT,
    )
    ahead_of_you = [
        (x, y, z)
        for x, y, z in cached_route
        if ((x - feet[0]) ** 2 + (y - feet[1]) ** 2) ** 0.5 > ROUTE_SKIP
    ]
    rest = ahead_of_you if ahead_of_you else cached_route[-1:]
    if not rest:
        return

    # Start a short step in front of you rather than under the camera.
    step = rest[0]
    span = (
        (step[0] - feet[0]) ** 2 + (step[1] - feet[1]) ** 2 + (step[2] - feet[2]) ** 2
    ) ** 0.5
    share = min(100.0 / span, 1.0) if span > 0 else 1.0
    start = (
        feet[0] + (step[0] - feet[0]) * share,
        feet[1] + (step[1] - feet[1]) * share,
        feet[2] + (step[2] - feet[2]) * share,
    )
    points = [start] + rest

    def to_screen(x, y, z):
        """Where a spot in the world lands on the screen, or nothing if it is behind you."""
        dx = x - eye[0]
        dy = y - eye[1]
        dz = z + ROUTE_LIFT - eye[2]

        ahead = dx * forward[0] + dy * forward[1] + dz * forward[2]
        if ahead <= 20.0:
            return None

        across = dx * right[0] + dy * right[1] + dz * right[2]
        above = dx * up[0] + dy * up[1] + dz * up[2]
        return (
            int(width / 2.0 + across * focal / ahead),
            int(height / 2.0 - above * focal / ahead),
        )

    def stroke(a, b):
        """One edge of a mark, with a soft halo under the bright core."""
        if a is None or b is None:
            return
        if (a[0] < 0 and b[0] < 0) or (a[0] > width and b[0] > width):
            return
        if (a[1] < 0 and b[1] < 0) or (a[1] > height and b[1] > height):
            return

        canvas.Draw2DLine(a[0], a[1] - 2, b[0], b[1] - 2, glow)
        canvas.Draw2DLine(a[0], a[1] + 3, b[0], b[1] + 3, glow)
        canvas.Draw2DLine(a[0], a[1], b[0], b[1], green)
        canvas.Draw2DLine(a[0], a[1] + 1, b[0], b[1] + 1, green)

    last = None
    for x, y, z in points:
        point = to_screen(x, y, z)
        if point is None:
            last = None
            continue
        stroke(last, point)
        last = point



def build_text() -> str:
    distance = waypoint_distance()
    if distance is None:
        return ""

    metres = distance / UNITS_PER_METRE

    if Units.value == "Feet":
        return f"{round(metres * FEET_PER_METRE)} ft"
    return f"{round(metres)} m"


font = None
black = None
white = None


def draw_outlined(canvas, x: float, y: float, text: str) -> None:
    """White text with a black edge, so it stays readable over any background."""
    global font, black, white

    if font is None:
        font = unrealsdk.find_object("Font", FONT)
        black = unrealsdk.make_struct("Color", R=0, G=0, B=0, A=255)
        white = unrealsdk.make_struct("Color", R=255, G=255, B=255, A=255)

    canvas.Font = font

    canvas.DrawColor = black
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        canvas.SetPos(x + dx, y + dy)
        canvas.DrawText(text, False, TEXT_SCALE, TEXT_SCALE)

    canvas.DrawColor = white
    canvas.SetPos(x, y)
    canvas.DrawText(text, False, TEXT_SCALE, TEXT_SCALE)


@hook(hook_func="Engine.GameViewportClient:PostRender", hook_type=Type.POST)
def on_render(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    if ShowDistance.value is False and ShowRoute.value is False:
        return

    pc = get_pc()
    if pc is None or pc.myHUD is None or pc.Pawn is None:
        return

    # Nothing of ours draws while a menu is up.
    if pc.bStatusMenuOpen is True or pc.WorldInfo.Pauser is not None:
        return

    canvas = __args.Canvas
    if canvas is None:
        return

    global frames, cached_text

    frames += 1
    if frames >= REFRESH_FRAMES:
        frames = 0
        cached_text = build_text()
        if ShowRoute.value is True:
            refresh_route(pc.Pawn.Location)

    if ShowRoute.value is True:
        try:
            draw_route(canvas, pc.Pawn.Location)
        except Exception as ex:
            logging.info(f"[Objective Distance] could not draw route ({ex})")

    if ShowDistance.value is False or not cached_text:
        return

    try:
        if Position.value == "Compass":
            bearing = 0.0
            if cached_target is not None:
                bearing = bearing_to(pc.Pawn.Location, cached_target)
            offset = max(-COMPASS_ARC, min(COMPASS_ARC, bearing))
            x = canvas.SizeX * (
                COMPASS_CENTRE + COMPASS_HALF_WIDTH * offset / COMPASS_ARC
            ) - len(cached_text) * 5.5
            y = canvas.SizeY * COMPASS_TOP - COMPASS_LIFT
            text = cached_text
        else:
            x = canvas.SizeX / 2 - 60
            y = TOP_HEIGHT
            text = f"Objective  {cached_text}"

        draw_outlined(canvas, x, y, text)
    except Exception as ex:
        logging.dev_warning(f"[Objective Distance] could not draw ({ex})")


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

build_mod(
    options=[ShowDistance, ShowRoute, Units, Position, RouteColour],
    keybinds=[],
    hooks=[on_render],
    commands=[],
    settings_file=Path(f"{SETTINGS_DIR}/ObjectiveDistance.json"),
)

logging.info(f"Objective Distance Loaded: {__version__}, {__version_info__}")
