import polars as pl

from src.features.scaling import scale_min_max, scale_percent_to_decimal


def preprocess_stimulus(df: pl.DataFrame) -> pl.DataFrame:
    return df


def feature_stimulus(df: pl.DataFrame) -> pl.DataFrame:
    return df


# REMOVE TODO
def process_stimulus(df: pl.DataFrame) -> pl.DataFrame:
    """
    Normalize the 'Stimulus' data by scaling the 'Rating' and 'Temperature' columns to
    [0, 1].

    NOTE: This function should not be used in the ML pipeline due to data leakage of
    the 'Temperature' column. However, we don't yet if want to use 'Temperature' as a
    target, so this function is included for now. Also the data leakeage is not
    significant. TODO
    """
    df = scale_rating(df)
    df = scale_temperature(df)
    return df


def scale_rating(df: pl.DataFrame) -> pl.DataFrame:
    """Normalize the 'Rating' column to the range [0, 1] by dividing by 100."""
    return scale_percent_to_decimal(df, exclude_additional_columns=["Temperature"])


def scale_temperature(df: pl.DataFrame) -> pl.DataFrame:
    """Normalize the 'Temperature' column using min-max scaling (for each trial).

    NOTE: This function should not be used in the ML pipeline due to data leakage of
    the 'Temperature' column. However, we don't yet if want to use 'Temperature' as a
    target, so this function is included for now. Also the data leakeage is not
    significant. TODO"""
    return scale_min_max(df, exclude_additional_columns=["Rating"])
