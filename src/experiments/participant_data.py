import argparse
import csv
import logging
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk

from src.helpers import center_tk_window
from src.log_config import close_root_logging, configure_logging

logger = logging.getLogger(__name__.rsplit(".", maxsplit=1)[-1])

PARTICIPANTS_FILE = Path("runs/experiments/participants.csv")  # main participants file


def add_participant_info(
    participant_info: dict,
    file_path: Path = PARTICIPANTS_FILE,
) -> None:
    """
    Add a participant to the participants file with a timestamp.
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)
    # Check if the file exists and has content; if not, write headers
    file_exists = file_path.exists()
    # Add timestamp to participant_info as the first key
    participant_info_dict = {"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    participant_info_dict.update(participant_info)
    with open(file_path, mode="a+", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=participant_info_dict.keys())

        if not file_exists:
            writer.writeheader()

        writer.writerow(participant_info_dict)
        logger.debug(f"Added participant {participant_info_dict['id']} to {file_path}.")


def read_last_participant(
    file_path: Path = PARTICIPANTS_FILE,
) -> dict:
    """
    Return information about the last participant from the participants file without the timestamp.
    """
    last_participant_info = {}
    with open(file_path, mode="r", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            last_participant_info = row

    if not last_participant_info:
        logger.warning(f"No participants found in the file {file_path}.")
        return dict()

    last_participant_info["id"] = int(last_participant_info["id"])
    logger.debug(
        f"Participant {last_participant_info['id']} ({last_participant_info['timestamp']}) loaded from {file_path}."
    )

    # Check if the participant data is from today
    today = datetime.now().strftime("%Y-%m-%d")
    if today not in last_participant_info["timestamp"]:
        logger.warning("Participant ID is not from today.")

    last_participant_info.pop(
        "timestamp"
    )  # new timestamp is added when the participant is added
    return last_participant_info


def ask_for_participant_info(
    file_path: Path = PARTICIPANTS_FILE,
) -> dict:
    """
    Ask for basic participant information using a simple GUI.
    """
    root = tk.Tk()
    root.withdraw()
    app = ParticipantDataApp(root)
    center_tk_window(root)
    root.deiconify()
    root.mainloop()

    if app.participant_info:
        participant_info = app.participant_info
        _participant_exists(participant_info["id"], file_path)
        logger.info(f"Participant ID: {participant_info['id']}")
        logger.info(f"Participant Age: {participant_info['age']}")
        logger.info(f"Participant Gender: {participant_info['gender']}")
        return participant_info
    logger.warning("No participant information entered.")
    return dict()


def _participant_exists(
    participant_id: str,
    file_path: Path,
) -> bool:
    """
    Check if a participant with the given ID already exists in the CSV file.
    """
    if not file_path.exists():
        return False
    with open(file_path, mode="r", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            if int(row["id"]) == int(participant_id):
                logger.warning(
                    f"Participant with ID {participant_id} ({row['timestamp']}) already exists in {file_path}."
                )
        return True
    return False


class ParticipantDataApp:
    """
    A simple GUI for entering participant data. It allows easy access to the participant_info dictionary
    for further processing or validation of participant information.
    """

    def __init__(self, root):
        self.root = root
        self.participant_info = {}
        self.setup_ui()

    def setup_ui(self):
        """Configures the main UI components including window, data fields, and submit button."""
        # Window configuration
        self.root.title("Participant Data Input")
        self.root.columnconfigure(0, weight=1)
        self.root.columnconfigure(1, weight=3)

        # Data fields creation
        fields = ["ID", "Age", "Gender"]
        self.entries = {}
        for i, field in enumerate(fields):
            label = ttk.Label(self.root, text=f"{field}:")
            label.grid(column=0, row=i, sticky=tk.W, padx=5, pady=5)
            if field == "Gender":
                entry = ttk.Combobox(
                    self.root, values=["Male", "Female"], state="readonly"
                )
            else:
                entry = ttk.Entry(self.root)
            entry.grid(column=1, row=i, sticky=tk.EW, padx=5, pady=5)
            self.entries[field] = entry

        # Submit button creation
        submit_button = ttk.Button(self.root, text="Submit", command=self.submit_data)
        submit_button.grid(
            column=0, row=len(self.entries), columnspan=2, sticky=tk.EW, padx=5, pady=5
        )

    def submit_data(self):
        """Handles data submission, including validation and extraction."""
        # Data validation
        valid = True
        for field, entry in self.entries.items():
            value = entry.get().strip()
            if not value:
                messagebox.showwarning("Missing Information", f"{field} is required.")
                valid = False
                break  # Exit the loop early on validation failure
            if field in ["ID", "Age"] and not value.isdigit():
                messagebox.showwarning("Invalid Input", f"{field} must be a number.")
                valid = False
                break

        # Data extraction
        if valid:
            gender_full = self.entries["Gender"].get()
            self.participant_info = {
                "id": int(self.entries["ID"].get().strip()),
                "age": int(self.entries["Age"].get()),
                "gender": "m" if gender_full == "Male" else "f",
            }
            self.root.destroy()


def parse_args():
    """
    Parse command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Add a participant to the main participants file."
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Enable debug mode. Data will not be saved.",
    )
    return parser.parse_args()


def main(args):
    """
    Add a participant to the main participants.csv file.
    """
    if args.debug:
        logger.debug("Debug mode is enabled. Data will not be saved.")

    participant_info = ask_for_participant_info()
    if participant_info and not args.debug:
        add_participant_info(participant_info)


if __name__ == "__main__":
    args = parse_args()
    configure_logging(stream_level=logging.INFO if not args.debug else logging.DEBUG)

    main(args)
    close_root_logging()
