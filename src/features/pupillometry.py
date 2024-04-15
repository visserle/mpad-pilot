# TODO:
# - distrubution of blinks vs look-aways
# - interpolation with cubic spline, resampling and low-pass filtering + sync, see matlab
# - get the mean using a kalman filter?
# - average only when len list > 1

# - check if facial expression and eeg fall into blink segments


import logging

import numpy as np
import polars as pl
import scipy.signal as signal

from src.features.transformations import map_trials
from src.helpers import ensure_list

logger = logging.getLogger(__name__.rsplit(".", maxsplit=1)[-1])


EYE_COLUMNS = ["Pupillometry_R", "Pupillometry_L"]
TIME_COLUMN = "Timestamp"
TRIAL_COLUMN = "Trial"
RESULT_COLUMN = "Pupillometry"

SAMPLE_RATE = 60
BLINK_THRESHOLD = 1.5
BLINK_PERIOD_REMOVAL = 120
CUTOFF_FREQUENCY = 0.5


@map_trials
def process_pupillometry(
    df: pl.DataFrame,
    eye_columns: str | list[str] = EYE_COLUMNS,
    sampling_rate: int = SAMPLE_RATE,
    cutoff_frequency: float = CUTOFF_FREQUENCY,
) -> pl.DataFrame:
    df = below_threshold_equals_blink(df, eye_columns)
    df = remove_periods_around_blinks(df, eye_columns)
    df = interpolate_pupillometry(df, eye_columns)
    df = low_pass_filter_pupillometry(df, eye_columns, sampling_rate, cutoff_frequency)
    df = mean_pupil_size(df, eye_columns)
    return df


def below_threshold_equals_blink(
    df: pl.DataFrame,
    eye_columns: str | list[str] = EYE_COLUMNS,
    threshold: int = BLINK_THRESHOLD,
) -> pl.DataFrame:
    for eye in ensure_list(eye_columns):
        df = df.with_columns(
            pl.when(pl.col(eye) < threshold)
            .then(-1)
            .otherwise(pl.col(eye))
            .alias(
                eye,
            )
        )
    return df


def _get_blink_segments(
    df: pl.DataFrame,
    eye_columns: str | list[str] = EYE_COLUMNS,
) -> pl.DataFrame:
    """
    This helper functions returns the start and end timestamps of blink segments in the
    given DataFrame. It returns a DataFrame to be usable in a Polars pipeline.

    Note that this function does not depend on indices but on time stamps as
    indices are not preserved by the @map_trials decorator.
    """
    blink_segments_data = []
    for eye in ensure_list(eye_columns):
        # Missing data (blink or look-away) is marked with -1
        neg_ones = df[eye] == -1

        # Skip if there are no blinks
        if neg_ones.sum() == 0:
            trial_info = (
                f" for trial {int(df[TRIAL_COLUMN].unique().item())}"
                if (TRIAL_COLUMN in df.columns) and (df[TRIAL_COLUMN].n_unique() == 1)
                else ""
            )
            logger.warning(f"No blinks found in {eye}{trial_info}.")
            continue

        # Shift the series to find the transitions
        start_conditions = neg_ones & ~neg_ones.shift(1)
        end_conditions = neg_ones & ~neg_ones.shift(-1)

        # Get the indices where the conditions are True
        start_indices = start_conditions.arg_true().to_list()
        end_indices = end_conditions.arg_true().to_list()

        # Check for edge cases where the first or last value is -1
        if df[eye][0] == -1:
            start_indices.insert(0, 0)
        if df[eye][-1] == -1:
            end_indices.append(df.height - 1)

        # Get timestamps for the blink segments
        start_timestamps = df[TIME_COLUMN][start_indices].to_list()
        end_timestamps = df[TIME_COLUMN][end_indices].to_list()

        # Add to the blink segments list
        blink_segments_data.extend(
            zip([eye] * len(start_indices), start_timestamps, end_timestamps)
        )

    # Create a DataFrame from the blink segments list
    blink_segments_df = pl.DataFrame(
        blink_segments_data, schema=["eye", "start_timestamp", "end_timestamp"]
    )

    # Add a duration column if there are any segments,
    # else create an empty DataFrame with the expected schema
    return (
        blink_segments_df.with_columns(
            (
                blink_segments_df["end_timestamp"]
                - blink_segments_df["start_timestamp"]
            ).alias("duration")
        ).sort("start_timestamp")
        if not blink_segments_df.is_empty()
        else pl.DataFrame(
            [], schema=["eye", "start_timestamp", "end_timestamp", "duration"]
        )
    )


def remove_periods_around_blinks(
    df: pl.DataFrame,
    eye_columns: str | list[str] = EYE_COLUMNS,
    period: int = BLINK_PERIOD_REMOVAL,
) -> pl.DataFrame:
    """
    Remove periods of 120 ms before and after blinks from the DataFrame.
    (Geuter 2014 used 100 ms cut-off before and after each blink)

    TODO: add a look_away detector for segments over 300 ms (?) with longer cut-off period
    """
    min_timestamp = df[TIME_COLUMN].min()
    max_timestamp = df[TIME_COLUMN].max()

    for eye in ensure_list(eye_columns):
        # Get the blink segments
        blink_segments = _get_blink_segments(df, eye)
        if blink_segments.is_empty():
            continue

        # Expand the blink segments
        blink_segments = blink_segments.with_columns(
            [
                (pl.col("start_timestamp") - period).alias("expanded_start"),
                (pl.col("end_timestamp") + period).alias("expanded_end"),
            ]
        )

        # Ensure that the blink segments are within the time range of the DataFrame
        blink_segments = blink_segments.with_columns(
            pl.when(pl.col("expanded_start") < min_timestamp)
            .then(min_timestamp)
            .otherwise(pl.col("expanded_start"))
            .alias("expanded_start"),
            pl.when(pl.col("expanded_end") > max_timestamp)
            .then(max_timestamp)
            .otherwise(pl.col("expanded_end"))
            .alias("expanded_end"),
        )

        # Initialize a mask (false just means a condition with no rows selected here)
        mask = pl.lit(False)

        # Loop over each segment and update the mask
        for start, end in zip(
            blink_segments["expanded_start"], blink_segments["expanded_end"]
        ):
            mask = mask | df[TIME_COLUMN].is_between(start, end)

        # Replace the values in the DataFrame with None
        df = df.with_columns(
            pl.when(mask)
            .then(None)
            .otherwise(df[eye])
            .alias(
                eye,
            )
        )

    return df


def interpolate_pupillometry(
    df: pl.DataFrame,
    eye_columns: str | list[str] = EYE_COLUMNS,
) -> pl.DataFrame:
    # Linearly interpolate and fill edge cases when the first or last value is null
    # NOTE: cubic spline?
    for eye in ensure_list(eye_columns):
        df = df.with_columns(
            pl.col(eye)
            .interpolate()
            .forward_fill()  # Fill remaining edge cases
            .backward_fill()
            .alias(eye)
        )

    return df


def low_pass_filter_pupillometry(
    df: pl.DataFrame,
    eye_columns: str | list[str] = EYE_COLUMNS,
    sampling_rate: int = SAMPLE_RATE,
    cutoff_frequency: float = CUTOFF_FREQUENCY,
) -> pl.DataFrame:
    for eye in ensure_list(eye_columns):
        pupil_low_pass_filtered = _low_pass_filter(
            df[eye], sampling_rate, cutoff_frequency=0.5
        )
        df = df.with_columns(pl.Series(eye, pupil_low_pass_filtered))
    return df


def _low_pass_filter(
    data: pl.Series,
    sampling_rate: int = SAMPLE_RATE,
    cutoff_frequency: float = CUTOFF_FREQUENCY,
) -> np.ndarray:
    """
    Apply a low-pass filter to smooth the data.

    - data: numpy array of pupil size measurements.
    - sampling_rate: rate at which data was sampled (Hz).
    - cutoff_frequency: frequency at which to cut off the high-frequency signal.

    Returns the filtered data as a numpy array.
    """
    # Normalize the frequency to Nyquist frequency and avoid aliasing
    normalized_cutoff = cutoff_frequency / (
        0.5 * sampling_rate
    )  # TODO: make sure this is correct

    # Create filter
    b, a = signal.butter(N=2, Wn=normalized_cutoff, btype="low", analog=False)

    # Apply filter
    filtered_data = signal.filtfilt(b, a, data)

    return filtered_data


def mean_pupil_size(
    df: pl.DataFrame,
    eye_columns: str | list[str] = EYE_COLUMNS,
    new_column: str = RESULT_COLUMN,
) -> pl.DataFrame:
    return df.with_columns(
        ((pl.col(eye_columns[0]) + pl.col(eye_columns[1])) / 2).alias(new_column)
    )
