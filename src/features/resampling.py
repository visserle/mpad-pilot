"""
Note that the usage of the pl.Duration data type is not fully supported in Polars yet.

https://github.com/pola-rs/polars/issues/13560
"""

import polars as pl
from polars import col

from src.features.transforming import map_participants, map_trials


@map_trials
def downsample(
    df: pl.DataFrame,
    new_sample_rate: int = 10,
) -> pl.DataFrame:
    # Find out current sampling rate
    current_sample_rate = round(
        1000
        / (
            df.filter(col("trial_id") == df.select(pl.first("trial_id")))
            .get_column("timestamp")
            .diff()
            .mean()
        )
    )
    if new_sample_rate >= current_sample_rate:
        raise ValueError(
            f"New sample rate {new_sample_rate} must be smaller than current sample "
            f"rate {current_sample_rate}"
        )

    # Add time column in µs for integer data type so that group_by_dynamic works
    df = add_timestamp_µs_column(df)
    # Downsample using group_by_dynamic
    df = df.group_by_dynamic(
        "timestamp_µs", every=f"{int((1000 / new_sample_rate)*1000)}i"
    ).agg(pl.all().mean())
    # Reverse the timestamp_µs column to timestamp in ms
    df = df.with_columns(
        (col("timestamp_µs") / 1000).alias("timestamp"),
        col("trial_id").cast(pl.UInt16),
        col(["trial_number", "participant_id"]).cast(pl.UInt8),
        # we should also cast the other columns to the correct data type TODO
    ).drop("timestamp_µs")

    return df


def add_time_column(
    df: pl.DataFrame,
    time_column: str = "timestamp",
    time_unit: str = "ms",
    new_column_name: str = "time",
) -> pl.DataFrame:
    """
    Create a new column that contains the time from Timestamp in ms.

    Note: This datatype is not fully supported in Polars and DuckDB yet.
    Use with caution.
    """
    df = df.with_columns(
        col(time_column).cast(pl.Duration(time_unit=time_unit)).alias(new_column_name)
    )
    return df


def add_timestamp_µs_column(
    df: pl.DataFrame,
) -> pl.DataFrame:
    """
    Create a new column that contains the timestamp in microseconds (µs).

    Casts the datatype to Int64 which allow group_by_dynamic operations.
    """
    return df.with_columns(
        (col("timestamp") * 1000).cast(pl.Int64).alias("timestamp_µs"),
    )
