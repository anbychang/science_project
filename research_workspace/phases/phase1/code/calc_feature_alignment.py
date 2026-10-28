"""Align P1.6 features without reading or writing SQLite."""


MICROSECONDS_PER_MINUTE = 60_000_000
MICROSECONDS_PER_DAY = 24 * 60 * MICROSECONDS_PER_MINUTE
AP_BLOCK_DURATION_US = 3 * 60 * MICROSECONDS_PER_MINUTE
MAXIMUM_SYM_H_INTERPOLATION_GAP_US = 2 * MICROSECONDS_PER_MINUTE


def align_sym_h(target_time_us, left_observation, right_observation):
    """Input: {target time, left/right {time_us, sym_h_nt}}
    Output: {sym_h_nt, sym_h_left_time_us, sym_h_right_time_us}"""
    exact_observation = _exact_observation(
        target_time_us,
        left_observation,
        right_observation,
    )
    if exact_observation is not None:
        return _exact_sym_h_features(exact_observation)
    if left_observation is None or right_observation is None:
        return _missing_sym_h_features()

    left_time_us = left_observation["time_us"]
    right_time_us = right_observation["time_us"]
    if (
        left_time_us >= target_time_us
        or right_time_us <= target_time_us
        or right_time_us - left_time_us > MAXIMUM_SYM_H_INTERPOLATION_GAP_US
    ):
        return _missing_sym_h_features()

    fraction = (target_time_us - left_time_us) / (right_time_us - left_time_us)
    value_nt = left_observation["sym_h_nt"] + fraction * (
        right_observation["sym_h_nt"] - left_observation["sym_h_nt"]
    )
    return {
        "sym_h_nt": value_nt,
        "sym_h_left_time_us": left_time_us,
        "sym_h_right_time_us": right_time_us,
    }


def _exact_observation(target_time_us, left_observation, right_observation):
    """Input: {target time, left/right SYM-H observations}
    Output: exact observation, or None"""
    for observation in (left_observation, right_observation):
        if observation is not None and observation["time_us"] == target_time_us:
            return observation
    return None


def _exact_sym_h_features(observation):
    """Input: exact {time_us, sym_h_nt} observation
    Output: exact-match SYM-H feature fields"""
    return {
        "sym_h_nt": observation["sym_h_nt"],
        "sym_h_left_time_us": observation["time_us"],
        "sym_h_right_time_us": observation["time_us"],
    }


def _missing_sym_h_features():
    """Input: none
    Output: missing SYM-H feature fields"""
    return {
        "sym_h_nt": None,
        "sym_h_left_time_us": None,
        "sym_h_right_time_us": None,
    }


def align_space_weather(target_time_us, weather_by_time):
    """Input: {target time, {3-hour time_us: weather row}}
    Output: causal Ap, F10.7, and F10.7A feature fields"""
    ap_time_us = target_time_us - target_time_us % AP_BLOCK_DURATION_US
    previous_day_time_us = (
        target_time_us - target_time_us % MICROSECONDS_PER_DAY - MICROSECONDS_PER_DAY
    )
    target_weather = weather_by_time.get(ap_time_us)
    previous_day_weather = weather_by_time.get(previous_day_time_us)
    if target_weather is None or previous_day_weather is None:
        return _missing_weather_features()

    return {
        "ap_now": target_weather["ap_now"],
        "ap_source_time_us": ap_time_us,
        "f107_sfu": previous_day_weather["f107_sfu"],
        "f107_source_time_us": previous_day_time_us,
        "f107a_sfu": previous_day_weather["f107a_last81_sfu"],
        "f107a_source_time_us": previous_day_time_us,
        "f107_data_type": previous_day_weather["f107_data_type"],
    }


def _missing_weather_features():
    """Input: none
    Output: missing causal weather feature fields"""
    return {
        "ap_now": None,
        "ap_source_time_us": None,
        "f107_sfu": None,
        "f107_source_time_us": None,
        "f107a_sfu": None,
        "f107a_source_time_us": None,
        "f107_data_type": None,
    }


def feature_quality_flags(sym_h_features, weather_features):
    """Input: {SYM-H fields, weather fields}
    Output: controlled P1.6 quality_flags value"""
    missing_features = []
    if sym_h_features["sym_h_nt"] is None:
        missing_features.append("missing_sym_h")
    if weather_features["ap_now"] is None:
        missing_features.append("missing_space_weather")
    return "|".join(missing_features) if missing_features else "ok"
