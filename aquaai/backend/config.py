"""Household + billing constants, shared across modules."""

# San Jose, CA is used as the default — swap for any California ZIP's
# real coordinates and tiered-rate schedule.
LATITUDE, LONGITUDE = 37.3382, -121.8863

TIER_1_LIMIT_GAL = 4500       # monthly gallons before Tier 2 pricing kicks in
TIER_1_RATE = 0.0035          # $ per gallon, Tier 1
TIER_2_RATE = 0.0070          # $ per gallon, Tier 2 (roughly double)
DAYS_IN_MONTH = 30
INTERVALS_PER_DAY = 96        # 24h * 4 (15-minute intervals)

RNG_SEED = 42
