"""BirdPi physical routing; explicit topology, never infer from active IPs."""
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class Route:
    mode: str
    bird_count: int
    role: str
    physical_bird: str
    controller: str

class RoutingError(ValueError):
    pass

LAYOUTS = {
  1: {'polly': 'main'},
  4: {'polly': 'main', 'jose': 'main', 'michael': 'michael', 'fritz': 'fritz', 'pierre': 'pierre'},
  5: {'polly': 'polly', 'jose': 'jose', 'michael': 'michael', 'fritz': 'fritz', 'pierre': 'pierre'},
}


def route(bird_count: int, role: str, action: str) -> Route:
    if bird_count not in LAYOUTS:
        raise RoutingError('Supported bird counts are 1, 4, and 5; configure explicitly')
    if role not in ('polly', 'jose'):
        raise RoutingError('Only Polly comedy and José singing are exposed by this interface')
    if action not in ('comedy', 'sing'):
        raise RoutingError('action must be comedy or sing')
    if action == 'comedy' and role != 'polly':
        raise RoutingError('Only Polly may perform jokes and roasts')
    if action == 'sing' and role != 'jose':
        raise RoutingError('Only José may sing')
    if role not in LAYOUTS[bird_count]:
        raise RoutingError('Role unavailable in this topology')
    if bird_count == 1 and action == 'sing':
        raise RoutingError('Single-bird mode has no singing')
    return Route(
        mode={1:'solo_polly',4:'shared_jose_polly',5:'separate_polly'}[bird_count],
        bird_count=bird_count, role=role,
        physical_bird=LAYOUTS[bird_count][role],
        controller='pi5' if role == 'polly' else 'birdpi_main',
    )


def validate_comedy(chirp: dict, bird_count: int) -> Route:
    """Hard stop for all historical non-Polly jokes and multi-bird banter."""
    if chirp.get('speaker') != 'polly':
        raise RoutingError('Comedic audio must use speaker polly only')
    if chirp.get('dialogue'):
        raise RoutingError('No multi-bird comedic dialogue is permitted')
    if chirp.get('type') not in ('joke','roast','comeback','greeting','farewell','idle','question','compliment'):
        raise RoutingError('Unsupported comedy type')
    if chirp.get('audience') != 'adults' or 'adult_mode' not in chirp.get('required_tags', []):
        raise RoutingError('Polly jokes must be adults-only and operator-enabled')
    return route(bird_count,'polly','comedy')
