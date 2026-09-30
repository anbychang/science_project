"""Summarize one continuous UTC 10-minute POD bin."""

MICROSECONDS_PER_SECOND = 1_000_000
TEN_MINUTE_BIN_US = 10 * 60 * MICROSECONDS_PER_SECOND


def ten_minute_bin_start_time_us(time_us):
    """Input: UTC Unix time_us
    Output: start time_us of its 10-minute bin"""
    return time_us - time_us % TEN_MINUTE_BIN_US


def summarize_single_interval_ten_minute_bin(observations):
    """Input: ordered [{time_us, interval_id}, ...] from one UTC bin
    Output: {time_us, pod_count, first_pod_time_us, last_pod_time_us, max_pod_gap_s, interval_id}"""
    if not observations:
        return None

    first_observation = observations[0]
    bin_start_time_us = ten_minute_bin_start_time_us(first_observation["time_us"])
    interval_id = first_observation["interval_id"]
    previous_time_us = None
    max_gap_us = 0

    for observation in observations:
        time_us = observation["time_us"]
        if ten_minute_bin_start_time_us(time_us) != bin_start_time_us:
            raise ValueError("POD observations cross a UTC 10-minute bin boundary.")
        if observation["interval_id"] != interval_id:
            raise ValueError("POD observations cross an interval boundary.")
        if previous_time_us is not None:
            if time_us <= previous_time_us:
                raise ValueError("POD observations must be strictly time increasing.")
            max_gap_us = max(max_gap_us, time_us - previous_time_us)
        previous_time_us = time_us

    return {
        "time_us": bin_start_time_us,
        "pod_count": len(observations),
        "first_pod_time_us": first_observation["time_us"],
        "last_pod_time_us": observations[-1]["time_us"],
        "max_pod_gap_s": max_gap_us / MICROSECONDS_PER_SECOND,
        "interval_id": interval_id,
    }
