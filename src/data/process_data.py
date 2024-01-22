# work in progress

#  TODO
# - makes a bit more sense to only display the warning for missing datasets once at loading time
# - in thw other functions we can just check if the dataset is available and skip it if not
# - based on a list of available datasets for each participant not with the convoluted if statements


"""
This is the main script for processing data obtained from the iMotions software.

The script has three main steps:
1. Load data from csv files
2. Transform data
3. Save data to csv files

"""

import os
from pathlib import Path
from functools import reduce
from dataclasses import dataclass
from typing import Dict, List, Optional
import logging

import polars as pl

from src.data.config_data import DataConfigBase
from src.data.config_data_imotions import iMotionsConfig, IMOTIONS_LIST, IMOTIONS_DICT
from src.data.config_data_raw import RawConfig, RAW_LIST
from src.data.config_participant import ParticipantConfig, PARTICIPANT_LIST

from src.log_config import configure_logging

logger = logging.getLogger(__name__.rsplit(".", maxsplit=1)[-1])


@dataclass
class Data:
    """Dataclass for a single csv files"""
    name: str
    dataset: pl.DataFrame

@dataclass
class Participant:
    """Dataclass for a single participant"""
    id: str
    datasets: Dict[str, Data]
    
    def __call__(self, attr_name):
        return getattr(self, attr_name)

    def __getattr__(self, name):
        if name in self.datasets:
           return self.datasets[name].dataset
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
    
    def __repr__(self):
        return f"Participant(id={self.id}, datasets={self.datasets.keys()})"


def load_dataset(
        participant_config: ParticipantConfig,
        data_config: DataConfigBase
        ) -> Data:

    file_path = data_config.load_dir / participant_config.id / f"{participant_config.id}_{data_config.name}.csv"
    file_start_index = 0
    # iMotions data are stored in a different format and have metadata we need to skip
    if isinstance(data_config, iMotionsConfig):
        file_path = data_config.load_dir / participant_config.id / f"{data_config.name_imotions}.csv"
        with open(file_path, 'r') as file:
            lines = file.readlines(2**16) # only read a few lines
        file_start_index = next(i for i, line in enumerate(lines) if "#DATA" in line) + 1

    # Load and process data using Polars
    dataset = pl.read_csv(
        file_path, 
        columns=data_config.load_columns,
        skip_rows=file_start_index,
        dtypes={load_column: pl.Float64 for load_column in data_config.load_columns}, # FIXME TODO dirty hack, add data schema instead
        #infer_schema_length=1000,
    )
    
    # For iMotions data we also want to rename some columns
    if isinstance(data_config, iMotionsConfig):
        if data_config.rename_columns:
            dataset = dataset.rename(data_config.rename_columns)

    logger.debug("Dataset '%s' for participant %s loaded from %s", data_config.name, participant_config.id, file_path)
    return Data(name=data_config.name, dataset=dataset)

def load_participant_datasets(
        participant_config: ParticipantConfig, 
        data_configs: List[DataConfigBase]
        ) -> Participant:

    datasets: Dict[str, Data] = {}
    for data_config in data_configs:
        if data_config.name in participant_config.not_available_data:
            logger.warning("Dataset '%s' for participant %s not available", data_config.name, participant_config.id)
            continue
        datasets[data_config.name] = load_dataset(participant_config, data_config)
    
    available_datasets = [data_config.name for data_config in data_configs if data_config.name not in participant_config.not_available_data]
    logger.info(f"Participant {participant_config.id} loaded with datasets: {available_datasets}")
    return Participant(id=participant_config.id, datasets=datasets)


def transform_dataset(
        data: Data,
        data_config: DataConfigBase
        ) -> Data:
    """
    Transform a single dataset.
    Note that we just map a list of functions to the dataset. Could be made faster probably.
    
    From the old, basic code:
    
    def apply_func_participant(func, participant):
    #TODO: use map instead, e.g.:
    # dict(zip(a, map(f, a.values())))
    # dict(map(lambda item: (item[0], f(item[1])), my_dictionary.items()
    for data in participant.datasets:
        participant.datasets[data].dataset = func(participant.datasets[data].dataset)
    return participant
    
    """
    if data_config.transformations:
        for transformation in data_config.transformations:
            data.dataset = transformation(data.dataset)
            logger.debug("Dataset '%s' transformed with %s", data_config.name, transformation.__name__)
            # TODO: add **kwargs to transformations and pass them here

def transform_participant_datasets(
        participant_config: ParticipantConfig, 
        participant_data: Participant,
        data_configs: List[DataConfigBase]
        ) -> Participant:
    """Transform all datasets for a single participant."""
    
    # Special case for imotions data: we first need to merge trial information into each dataset (via Stimuli_Seed)
    if isinstance(data_configs[0], iMotionsConfig):
        for data_config in IMOTIONS_LIST:
            if data_config.name in participant_config.not_available_data:
                continue # skip datasets that are not available, FIXME a bit convoluted, better to have a list of available datasets for each participant
            # add the stimuli seed column to all datasets of the participant except for the trial data which already has it
            if "Stimuli_Seed" not in participant_data.datasets[data_config.name].dataset.columns:
                participant_data.datasets[data_config.name].dataset = participant_data.datasets[data_config.name].dataset.join(
                    participant_data.trial,
                    on='Timestamp',
                    how='outer_coalesce',
                ).sort('Timestamp')
            assert participant_data.datasets[data_config.name].dataset['Timestamp'].is_sorted(descending=False)
        logger.debug("Participant %s datasets are now merged with trial information", participant_data.id)

    # Do the regular transformation(s) as defined in the config
    for data_config in data_configs:
        if data_config.name in participant_config.not_available_data:
            logger.warning("Dataset '%s' for participant %s not available", data_config.name, participant_data.id)
            continue
        transform_dataset(participant_data.datasets[data_config.name], data_config)
    logger.info(f"Participant {participant_data.id} datasets successfully transformed")
    return participant_data

    if isinstance(data_configs[0], DataConfigBase):
        pass # TODO: merge datasets into one big dataset at the end


def save_dataset(
        data: Data,
        participant_data: Participant,
        data_config: DataConfigBase
        ) -> None:
    """Save a single dataset to a csv file."""
    output_dir = data_config.save_dir / participant_data.id
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    file_path = output_dir / f"{participant_data.id}_{data_config.name}.csv"

    # Write the DataFrame to CSV
    # TODO: problems with saving timedelta format, but we can do without it for now
    data.dataset.write_csv(file_path)
    logger.debug("Dataset '%s' for participant %s saved to %s", data_config.name, participant_data.id, file_path)

def save_participant_datasets(
        participant_config: ParticipantConfig, 
        participant_data: Participant,
        data_configs: List[DataConfigBase]
        ) -> None:
    """Save all datasets for a single participant to csv files."""
    for data_config in data_configs:
        if data_config.name in participant_config.not_available_data:
            logger.warning("Dataset '%s' for participant %s not available", data_config.name, participant_data.id)
            continue
        save_dataset(participant_data.datasets[data_config.name], participant_data, data_config)
        
    available_datasets = [data_config.name for data_config in data_configs if data_config.name not in participant_config.not_available_data]
    logger.info(f"Participant {participant_data.id} saved with datasets: {available_datasets}")


def main():
    configure_logging(color=True, stream_level=logging.DEBUG)

    list_of_data_configs = [
        IMOTIONS_LIST,
        # RAW_LIST,
    ]

    for data_configs in list_of_data_configs:
        for participant_config in PARTICIPANT_LIST:
            participant_data = load_participant_datasets(
                participant_config,
                data_configs)
            participant_data = transform_participant_datasets(
                participant_config,
                participant_data, 
                data_configs)
            save_participant_datasets(
                participant_config,
                participant_data, 
                data_configs)

    print(participant_data.eeg)

if __name__ == "__main__":
    main()
