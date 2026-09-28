"""Align raw feature observations to one analysis timestamp."""

MICROSECONDS_PER_SECOND = 1_000_000
SECONDS_PER_MINUTE = 60
MINUTES_PER_HOUR = 60
HOURS_PER_DAY = 24
HOURS_PER_AP_BLOCK = 3
MICROSECONDS_PER_MINUTE = MICROSECONDS_PER_SECOND * SECONDS_PER_MINUTE
MICROSECONDS_PER_DAY = (
    MICROSECONDS_PER_MINUTE * MINUTES_PER_HOUR * HOURS_PER_DAY
)
MICROSECONDS_PER_AP_BLOCK = MICROSECONDS_PER_MINUTE * MINUTES_PER_HOUR * HOURS_PER_AP_BLOCK
MAX_SYM_H_INTERPOLATION_GAP_US = 2 * MICROSECONDS_PER_MINUTE


def align_sym_h(time_us, observations):
    """Input: target time_us and ordered [{time_us, sym_h_nt}, ...]
    Output: {sym_h_nt, sym_h_left_time_us, sym_h_right_time_us} or None"""
    previous_observation = None

    for observation in observations:
        if observation["sym_h_nt"] is None:
            continue

        observation_time_us = observation["time_us"]
        if observation_time_us == time_us:
            return {
                "sym_h_nt": observation["sym_h_nt"],
                "sym_h_left_time_us": time_us,
                "sym_h_right_time_us": time_us,
            }
        if observation_time_us > time_us:
            if previous_observation is None:
                return None
            return interpolate_sym_h(time_us, previous_observation, observation)

        previous_observation = observation

    return None


def interpolate_sym_h(time_us, left_observation, right_observation):
    """Input: target time_us and two ordered SYM-H observations
    Output: interpolated {sym_h_nt, sym_h_left_time_us, sym_h_right_time_us} or None"""
    left_time_us = left_observation["time_us"]
    right_time_us = right_observation["time_us"]
    source_gap_us = right_time_us - left_time_us

    if source_gap_us > MAX_SYM_H_INTERPOLATION_GAP_US:
        return None

    fraction = (time_us - left_time_us) / source_gap_us
    left_value_nt = left_observation["sym_h_nt"]
    right_value_nt = right_observation["sym_h_nt"]
    return {
        "sym_h_nt": left_value_nt + fraction * (right_value_nt - left_value_nt),
        "sym_h_left_time_us": left_time_us,
        "sym_h_right_time_us": right_time_us,
    }


def align_space_weather(time_us, weather_by_time):
    """Input: target time_us and {3-hour block time_us: weather row}
    Output: {Ap, F10.7, F10.7A values and source times} or None"""
    ap_source_time_us = ap_block_start_time_us(time_us)
    current_weather_row = weather_by_time.get(ap_source_time_us)
    f107a_source_time_us = day_start_time_us(time_us) - MICROSECONDS_PER_DAY
    previous_day_row = weather_by_time.get(f107a_source_time_us)
    if current_weather_row is None or previous_day_row is None:
        return None

    return {
        "ap_now": current_weather_row["ap_now"],
        "ap_source_time_us": ap_source_time_us,
        "f107_sfu": current_weather_row["f107_sfu"],
        "f107_source_time_us": f107a_source_time_us,
        "f107a_sfu": previous_day_row["f107a_last81_sfu"],
        "f107a_source_time_us": f107a_source_time_us,
        "f107_data_type": current_weather_row["f107_data_type"],
    }


def ap_block_start_time_us(time_us):
    """Input: UTC Unix time_us
    Output: start of its official three-hour Ap block"""
    return time_us - time_us % MICROSECONDS_PER_AP_BLOCK


def day_start_time_us(time_us):
    """Input: UTC Unix time_us
    Output: start of its UTC day"""
    return time_us - time_us % MICROSECONDS_PER_DAY
