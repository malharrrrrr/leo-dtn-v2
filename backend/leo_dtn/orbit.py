"""Deterministic circular-orbit propagation and geometry-based contact planning.

This is a deliberately compact two-body model, not a high-fidelity ephemeris.
Satellite states are propagated in ECI then rotated into the Earth-fixed scene
frame; ground stations remain fixed to that frame.
"""

from __future__ import annotations

import math

from .model import Contact, Node, NodeKind

EARTH_RADIUS_KM = 6_371.0
EARTH_MU_KM3_S2 = 398_600.4418
EARTH_ROTATION_RAD_S = 7.2921150e-5


def position_and_velocity_ecef(node: Node, time_us: int) -> tuple[tuple[float, float, float] | None, tuple[float, float, float] | None]:
    """Return scene-frame state at integer simulated time, or static input state."""
    if node.orbit is None:
        return node.position_km, (0.0, 0.0, 0.0) if node.position_km is not None else None
    orbit = node.orbit
    radius = EARTH_RADIUS_KM + orbit.altitude_km
    inclination = math.radians(orbit.inclination_deg)
    raan = math.radians(orbit.raan_deg)
    phase = math.radians(orbit.phase_deg)
    time_s = time_us / 1_000_000
    mean_motion = math.sqrt(EARTH_MU_KM3_S2 / radius**3)
    anomaly = phase + mean_motion * time_s
    ca, sa = math.cos(anomaly), math.sin(anomaly)
    cr, sr = math.cos(raan), math.sin(raan)
    ci, si = math.cos(inclination), math.sin(inclination)

    # Position and velocity in ECI, in km and km/s.
    x_i = radius * (cr * ca - sr * sa * ci)
    y_i = radius * (sr * ca + cr * sa * ci)
    z_i = radius * sa * si
    speed = math.sqrt(EARTH_MU_KM3_S2 / radius)
    vx_i = speed * (-cr * sa - sr * ca * ci)
    vy_i = speed * (-sr * sa + cr * ca * ci)
    vz_i = speed * ca * si

    earth_angle = EARTH_ROTATION_RAD_S * time_s
    c, s = math.cos(earth_angle), math.sin(earth_angle)
    x = c * x_i + s * y_i
    y = -s * x_i + c * y_i
    # Transform inertial velocity into the rotating Earth-fixed frame.
    vx = c * vx_i + s * vy_i + EARTH_ROTATION_RAD_S * y
    vy = -s * vx_i + c * vy_i - EARTH_ROTATION_RAD_S * x
    return (x, y, z_i), (vx, vy, vz_i)


def has_line_of_sight(a: tuple[float, float, float], b: tuple[float, float, float]) -> bool:
    """Whether the segment between two points clears the spherical Earth."""
    dx, dy, dz = (b[i] - a[i] for i in range(3))
    length_sq = dx * dx + dy * dy + dz * dz
    if length_sq == 0:
        return False
    projection = max(0.0, min(1.0, -(a[0] * dx + a[1] * dy + a[2] * dz) / length_sq))
    closest_sq = sum((a[i] + projection * (b[i] - a[i])) ** 2 for i in range(3))
    return closest_sq >= (EARTH_RADIUS_KM - 1e-6) ** 2


def visible(node_a: Node, node_b: Node, time_us: int, *, minimum_elevation_deg: float = 10.0) -> bool:
    state_a = position_and_velocity_ecef(node_a, time_us)[0]
    state_b = position_and_velocity_ecef(node_b, time_us)[0]
    if state_a is None or state_b is None or not has_line_of_sight(state_a, state_b):
        return False
    # For a ground station, enforce a minimum local elevation angle.
    for station, spacecraft in ((node_a, node_b), (node_b, node_a)):
        if station.kind != NodeKind.GROUND_STATION:
            continue
        ground = position_and_velocity_ecef(station, time_us)[0]
        sat = position_and_velocity_ecef(spacecraft, time_us)[0]
        if ground is None or sat is None:
            return False
        line = tuple(sat[i] - ground[i] for i in range(3))
        line_norm = math.sqrt(sum(v * v for v in line))
        radial_norm = math.sqrt(sum(v * v for v in ground))
        sin_elevation = sum(line[i] * ground[i] for i in range(3)) / (line_norm * radial_norm)
        if sin_elevation < math.sin(math.radians(minimum_elevation_deg)):
            return False
    return True


def generate_contact_plan(
    nodes: tuple[Node, ...],
    *,
    horizon_us: int,
    sample_interval_us: int = 10_000_000,
    rate_bits_per_second: int = 100_000_000,
    minimum_elevation_deg: float = 10.0,
) -> tuple[Contact, ...]:
    """Build conservative sampled visibility windows, refined to microseconds.

    The sample interval bounds detection of short contacts. Geometry crossings
    are bisected to microsecond resolution once a state change is detected.
    """
    if horizon_us <= 0 or sample_interval_us <= 0 or rate_bits_per_second <= 0:
        raise ValueError("contact planner horizon, interval, and rate must be positive")
    eligible = tuple(sorted((n for n in nodes if n.orbit is not None or n.position_km is not None), key=lambda n: n.node_id))
    contacts: list[Contact] = []
    pair_index = 0
    for i, a in enumerate(eligible):
        for b in eligible[i + 1:]:
            if a.kind == b.kind == NodeKind.GROUND_STATION:
                continue
            pair_index += 1
            def is_visible(t: int) -> bool:
                return visible(a, b, t, minimum_elevation_deg=minimum_elevation_deg)

            prev_t = 0
            prev = is_visible(0)
            start: int | None = 0 if prev else None
            t = min(sample_interval_us, horizon_us)
            while True:
                current = is_visible(t)
                if current != prev:
                    low, high = prev_t, t
                    while high - low > 1:
                        mid = (low + high) // 2
                        if is_visible(mid) == prev:
                            low = mid
                        else:
                            high = mid
                    boundary = high
                    if current:
                        start = boundary
                    elif start is not None:
                        if start < boundary:
                            _append_directions(contacts, a, b, start, boundary, pair_index, rate_bits_per_second)
                        start = None
                if t == horizon_us:
                    break
                prev_t, prev = t, current
                t = min(t + sample_interval_us, horizon_us)
            if start is not None and start < horizon_us:
                _append_directions(contacts, a, b, start, horizon_us, pair_index, rate_bits_per_second)
    return tuple(contacts)


def _append_directions(contacts: list[Contact], a: Node, b: Node, start: int, end: int, pair: int, rate: int) -> None:
    window = sum(1 for item in contacts if item.from_node == a.node_id and item.to_node == b.node_id)
    base = f"AUTO-{pair:04d}-{window:03d}"
    for contact_id, source, target in ((f"{base}-AB", a.node_id, b.node_id), (f"{base}-BA", b.node_id, a.node_id)):
        contacts.append(Contact(contact_id, source, target, start, end, rate))
