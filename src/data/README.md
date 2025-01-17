# Data Pipeline

The data pipeline consists of three steps (`Raw` → `Preprocess` → `Feature`) over all modalities (EEG, EDA, PPG, pupillometry, facial expressions, and rating / temperatures), with each step corresponding to a table in the duckDB database.

- `Raw`: Raw data as collected from each trial of the experiment.
- `Preprocess`: Preprocessed data with cleaned and transformed columns.
- `Feature`: Extracted features from the preprocessed data for analysis and modeling.

Furthermore, there are additional tables for the experiment metadata, calibration results, and questionnaire responses.

## Files

- `database_schema.py` defines the schema for the database.
- `database_manager.py` is for insertig data into the database and extracting data from the database.
- `data_processing.py` coordinates the data processing by creating dataframes that are ready for insertion into the database as tables. For time series data tables (Stimulus, EEG, EDA, PPG, pupillometry, facial expressions) it uses the functions from the feature module (feature modules are decoupled from the database and can be used independently on dataframes).
- `data_config.py` contains very basic configuration parameters for the data pipeline and paths to the different data sources.

## Further Details

- Invalid participants and trials can be removed at any stage of the pipeline using the `exclude_invalid_data` keyword from the `get_table` method.
- Note that iMotions' .csv output corresponds to the `Raw` table.
