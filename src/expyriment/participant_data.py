import logging
import platform
import tkinter as tk
import tkinter.messagebox as messagebox
import warnings
from datetime import datetime
from tkinter import ttk

from src.expyriment.utils import center_tk_window

warnings.filterwarnings("ignore", "\nPyarrow", DeprecationWarning)
import pandas as pd

logger = logging.getLogger(__name__.rsplit(".", maxsplit=1)[-1])


COLUMN_HEADERS = [
    "time_stamp",
    "id",
    "age",
    "gender",
    "vas0",
    "vas70",
    "baseline_temp",
    "temp_range",
]


class ParticipantDataApp:
    """
    A simple GUI for entering participant data. Programmed as a class to allow for easy access to the participant_info dict.
    """

    def __init__(self, master):
        self.master = master
        self.participant_info = {}
        self.setup_ui()

    def setup_ui(self):
        self.master.title("Participant Data Input")
        # Configure grid layout
        self.master.columnconfigure(0, weight=1)
        self.master.columnconfigure(1, weight=3)

        fields = ["ID", "Age", "Gender"]
        entries = []

        # Create entries for ID and Age
        for i, field in enumerate(fields[:-1]):  # exclude Gender from this loop
            label = ttk.Label(self.master, text=f"{field}:")
            label.grid(column=0, row=i, sticky=tk.W, padx=5, pady=5)
            entry = ttk.Entry(self.master)
            entry.grid(column=1, row=i, sticky=tk.EW, padx=5, pady=5)
            entries.append(entry)

        # Unpack entries to individual variables for easy access
        self.id_entry, self.age_entry = entries

        # Create gender combobox
        gender_label = ttk.Label(self.master, text="Gender:")
        gender_label.grid(column=0, row=2, sticky=tk.W, padx=5, pady=5)
        self.gender_combobox = ttk.Combobox(
            self.master, values=["Male", "Female"], state="readonly"
        )
        self.gender_combobox.grid(column=1, row=2, sticky=tk.EW, padx=5, pady=5)

        # Create submit button
        submit_button = ttk.Button(self.master, text="Submit", command=self.submit_data)
        submit_button.grid(column=0, row=3, columnspan=2, sticky=tk.EW, padx=5, pady=5)

    def submit_data(self):
        # Initial check for empty fields
        if not self.id_entry.get().strip():
            messagebox.showwarning("Missing Information", "ID is required.")
            return
        if not self.age_entry.get().strip():
            messagebox.showwarning("Missing Information", "Age is required.")
            return
        if not self.gender_combobox.get().strip():
            messagebox.showwarning("Missing Information", "Gender is required.")
            return

        # Get participant info from fields
        self.participant_info["id"] = self.id_entry.get().strip()
        try:
            self.participant_info["age"] = int(self.age_entry.get())
        except ValueError:
            messagebox.showwarning("Invalid Input", "Age must be a number.")
            return
        self.participant_info["gender"] = self.gender_combobox.get()

        logger.info(f"Participant ID: {self.participant_info['id']}")
        logger.info(f"Participant Age: {self.participant_info['age']}")
        logger.info(f"Participant Gender: {self.participant_info['gender']}")
        self.master.destroy()


def ask_for_participant_info() -> dict:
    root = tk.Tk()
    root.withdraw()  # Hide window initially
    app = ParticipantDataApp(root)
    center_tk_window(root)
    root.deiconify()  # Show window when ready
    root.mainloop()
    return app.participant_info


def init_excel_file(file_path):
    if not file_path.exists():
        df = pd.DataFrame(columns=COLUMN_HEADERS)
        df.to_excel(file_path, index=False)


def complete_participant_info(participant_info: dict) -> dict:
    """
    Add additional information to the participant_info dict:
    - time_stamp
    - baseline_temp
    - temp_range

    Note that the participant_info dict must contain the following keys:
    - id
    - age
    - gender
    - vas0
    - vas70.
    """
    participant_info["time_stamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    participant_info["baseline_temp"] = round(
        (participant_info["vas0"] + participant_info["vas70"]) / 2, 1
    )
    participant_info["temp_range"] = round(participant_info["vas70"] - participant_info["vas0"], 1)
    return participant_info


def add_participant_info(file_path, participant_info: dict) -> dict:
    """
    Adds a participant to the participants.xlsx file.

    Example usage:
    -------
    ```python
    from participants import add_participant

    add_participant(file_path, participant_info)
    ```
    """
    # Add additional information to the participant_info dict
    if "time_stamp" not in participant_info:
        participant_info = complete_participant_info(participant_info)

    # Create a dataframe with the same order as the participants.xlsx file
    participant_info_df = pd.DataFrame([participant_info], columns=COLUMN_HEADERS)

    # Append participant info to the participants.xlsx file
    participants_xlsx = pd.read_excel(file_path)
    if participants_xlsx.empty or participants_xlsx.isna().all().all():
        participants_xlsx = participant_info_df
    else:
        # Check if the last participant is the same as the one you want to add
        last_participant = participants_xlsx.iloc[-1]["id"]
        if last_participant == participant_info["id"]:
            logger.critical(
                f"Participant {participant_info['id']} already exists as the last entry."
            )
        participants_xlsx = pd.concat([participants_xlsx, participant_info_df], ignore_index=True)
    # Save the updated participants.xlsx file
    participants_xlsx.to_excel(file_path, index=False)
    logger.info(f"Added participant {participant_info['id']} to {file_path}")

    return participant_info


def read_last_participant(file_path) -> dict:
    """
    Returns information about the last participant from the participants.xlsx file.

    Example for usage in psychopy:
    -------
    ```python
    from participants import read_last_participant

    participant_info = read_last_participant()
    ```
    """
    last_row = pd.read_excel(file_path).iloc[-1]
    participant_info = last_row.to_dict()

    # Check if the participant data is from today
    today = datetime.now().strftime("%Y-%m-%d")
    if today not in participant_info["time_stamp"]:
        logger.warning(
            f"Participant data from {participant_info['id']} ({participant_info['time_stamp']}) is not from today."
        )

    logger.info(
        f"Participant data from {participant_info['id']} ({participant_info['time_stamp']}) loaded."
    )

    return participant_info


if __name__ == "__main__":
    ask_for_participant_info()
    print("Done.")
