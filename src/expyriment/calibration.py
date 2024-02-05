# TODO
# fix argesparse
# fix formatting in script
# maybe add error that calibration failed in the experiment slides

import argparse
import logging
import random
import sys
from datetime import datetime
from pathlib import Path

from expyriment import control, design, io, stimuli
from expyriment.misc.constants import C_DARKGREY, K_SPACE, K_n, K_y

from src.expyriment.estimator import BayesianEstimatorVAS
from src.expyriment.participant_data import add_participant_info, ask_for_participant_info
from src.expyriment.thermoino import Thermoino
from src.expyriment.thermoino_dummy import ThermoinoDummy
from src.expyriment.utils import (
    load_configuration,
    load_script,
    prepare_script,
    scale_1d_value,
    scale_2d_tuple,
    warn_signal,
)
from src.log_config import close_root_logging, configure_logging

# Check if the script is run from the command line
if len(sys.argv) > 1:
    parser = argparse.ArgumentParser(description="Run the pain-calibration experiment.")
    parser.add_argument("--dummy", action="store_true", help="Run in development mode.")
    args = parser.parse_args()
    DEVELOP_MODE = args.dummy
else:
    DEVELOP_MODE = True


# Constants
NAME = "calibration"
EXP_NAME = f"pain-{NAME}"
CONFIG_PATH = Path(f"src/expyriment/{NAME}_config.toml")
SCRIPT_PATH = Path(f"src/expyriment/{NAME}_script.yaml")
LOG_DIR = Path(f"runs/expyriment/{NAME}/")
PARTICIPANTS_EXCEL_PATH = LOG_DIR.parent / "participants.xlsx"
VAS_PICTURE_PATH = Path("src/expyriment/vas_picture.png").as_posix()


# Configure logging
log_file = LOG_DIR / datetime.now().strftime("%Y_%m_%d__%H_%M_%S.log")
configure_logging(stream_level=logging.DEBUG, file_path=log_file)

# Load configurations and script
config = load_configuration(CONFIG_PATH)
SCRIPT = load_script(SCRIPT_PATH)
THERMOINO = config["thermoino"]
EXPERIMENT = config["experiment"]
ESTIMATOR = config["estimator"]
STIMULUS = config["stimulus"]
JITTER = random.randint(0, STIMULUS["iti_max_jitter"]) if not DEVELOP_MODE else 0

# Expyriment defaults
design.defaults.experiment_background_colour = C_DARKGREY
stimuli.defaults.textline_text_colour = EXPERIMENT["element_color"]
stimuli.defaults.textbox_text_colour = EXPERIMENT["element_color"]
io.defaults.eventfile_directory = (LOG_DIR / "events").as_posix()
io.defaults.datafile_directory = (LOG_DIR / "data").as_posix()
io.defaults.outputfile_time_stamp = True
io.defaults.mouse_show_cursor = False

# Development mode settings
if DEVELOP_MODE:
    Thermoino = ThermoinoDummy
    control.defaults.window_size = (800, 600)
    control.set_develop_mode(True)
    STIMULUS["iti_duration"] = 300
    STIMULUS["stimulus_duration"] = 200
    participant_info = config["dummy_participant"]
else:
    #Thermoino = ThermoinoDummy  # NOTE REMOVE THIS
    participant_info = ask_for_participant_info()
    STIMULUS["iti_duration"] = 300  # NOTE REMOVE THIS
    STIMULUS["stimulus_duration"] = 200  # NOTE REMOVE THIS

# Experiment setup
exp = design.Experiment(name=EXP_NAME)
control.initialize(exp)
screen_size = exp.screen.size

# Prepare stimuli
prepare_script(
    SCRIPT,
    text_size=scale_1d_value(EXPERIMENT["text_size"], screen_size),
    text_box_size=scale_2d_tuple(EXPERIMENT["text_box_size"], screen_size),
)

cross = {}
for name, color in zip(
    ["idle", "pain"], [EXPERIMENT["element_color"], EXPERIMENT["cross_pain_color"]]
):
    cross[name] = stimuli.FixCross(
        size=scale_2d_tuple(EXPERIMENT["cross_size"], screen_size),
        line_width=scale_1d_value(EXPERIMENT["cross_line_width"], screen_size),
        colour=color,
    )
    cross[name].preload()


# Load VAS picture, move it a bit up and scale it (empirically determined)
vas_picture = stimuli.Picture(VAS_PICTURE_PATH, position=(0, scale_1d_value(100, screen_size)))
vas_picture.scale(scale_1d_value(0.72, screen_size))
vas_picture.preload()

# Initialize Thermoino
thermoino = Thermoino(
    port=THERMOINO["port"],
    mms_baseline=THERMOINO["mms_baseline"],
    mms_rate_of_rise=THERMOINO["mms_rate_of_rise"],
)
thermoino.connect()


# Trial functions
def run_preexposure_trials():
    """Run pre-exposure trials with different temperatures."""
    for idx, temp in enumerate(STIMULUS["preexposure_temperatures"]):
        cross["idle"].present()
        iti_duration = STIMULUS["iti_duration"] if idx != 0 else STIMULUS["iti_duration_short"]
        exp.clock.wait(iti_duration + JITTER)
        thermoino.trigger()
        time_for_ramp_up, _ = thermoino.set_temp(temp)
        cross["pain"].present()
        exp.clock.wait(STIMULUS["stimulus_duration"] + time_for_ramp_up)
        time_for_ramp_down, _ = thermoino.set_temp(THERMOINO["mms_baseline"])
        cross["idle"].present()
        exp.clock.wait(time_for_ramp_down)


def run_estimation_trials(estimator: BayesianEstimatorVAS):
    """Run estimation trials and return the final estimate."""
    for trial in range(estimator.trials):
        cross["idle"].present()
        exp.clock.wait(STIMULUS["iti_duration"] + JITTER)
        thermoino.trigger()
        time_for_ramp_up, _ = thermoino.set_temp(estimator.get_estimate())
        cross["pain"].present()
        exp.clock.wait(STIMULUS["stimulus_duration"] + time_for_ramp_up)
        time_for_ramp_down, _ = thermoino.set_temp(THERMOINO["mms_baseline"])
        cross["idle"].present()
        exp.clock.wait(time_for_ramp_down)

        SCRIPT[f"question_vas{estimator.vas_value}"].present()
        found, _ = exp.keyboard.wait(keys=[K_y, K_n])
        if found == K_y:
            estimator.conduct_trial(response="y", trial=trial)
            SCRIPT["answer_yes"].present()
        elif found == K_n:
            estimator.conduct_trial(response="n", trial=trial)
            SCRIPT["answer_no"].present()
        exp.clock.wait(1000)
    # Only returns a false if all steps were in the same direction
    return estimator.validate_steps()


# Experiment procedure
def main():
    # Start experiment
    control.start(skip_ready_screen=True)

    # Introduction
    for text in SCRIPT["welcome"].values():
        text.present()
        exp.keyboard.wait(K_SPACE)

    # Pre-exposure Trials
    run_preexposure_trials()

    # Pre-exposure Feedback
    SCRIPT["question_preexposure"].present()
    found, _ = exp.keyboard.wait(keys=[K_y, K_n])
    if found == K_y:
        ESTIMATOR["temp_start_vas70"] -= STIMULUS["preexposure_correction"]
        SCRIPT["answer_yes"].present()
        logging.info("Preexposure was painful.")
    elif found == K_n:
        SCRIPT["answer_no"].present()
        logging.info("Preexposure was not painful.")
    exp.clock.wait(1000)

    # VAS 70 estimation TODO restructe script
    SCRIPT["info_vas70"][1].present()
    exp.keyboard.wait(K_SPACE)
    vas_picture.present(clear=True, update=False)
    SCRIPT["info_vas70"][2].present(clear=False, update=True)
    exp.keyboard.wait(K_SPACE)
    SCRIPT["info_vas70"][3].present()
    exp.keyboard.wait(K_SPACE)

    estimator_vas70 = BayesianEstimatorVAS(
        vas_value=70,
        temp_start=ESTIMATOR["temp_start_vas70"],
        temp_std=ESTIMATOR["temp_std_vas70"],
        trials=ESTIMATOR["trials_vas70"],
    )
    success = run_estimation_trials(estimator=estimator_vas70)
    if not success:
        warn_signal()
        pass  # TODO
    participant_info["vas70"] = estimator_vas70.get_estimate()

    # Pain threshold (VAS 0) estimation
    SCRIPT["info_vas0"].present()
    estimator_vas0 = BayesianEstimatorVAS(
        vas_value=0,
        temp_start=estimator_vas70.get_estimate() - ESTIMATOR["temp_start_vas0_offset"],
        temp_std=ESTIMATOR["temp_std_vas0"],
        trials=ESTIMATOR["trials_vas0"],
    )
    success = run_estimation_trials(estimator=estimator_vas0)
    if not success:
        warn_signal()
        pass  # TODO
    participant_info["vas0"] = estimator_vas0.get_estimate()

    if participant_info["vas70"] - participant_info["vas0"] < 1:
        logging.warning("VAS 70 and VAS 0 are too close together.")
        warn_signal()
        pass

    # End of Experiment
    SCRIPT["bye"].present()
    exp.keyboard.wait(K_SPACE)

    # Close and clean up
    control.end()
    thermoino.close()
    add_participant_info(PARTICIPANTS_EXCEL_PATH, participant_info)
    close_root_logging()


if __name__ == "__main__":
    main()
