import logging
import math
import time
from enum import Enum

import numpy as np
import pandas as pd
import serial
import serial.tools.list_ports

logger = logging.getLogger(__name__.rsplit(".", maxsplit=1)[-1])


def list_com_ports():
    """List all serial ports."""
    ports = serial.tools.list_ports.comports()
    output = []
    if len(ports) == 0:
        output.append("No serial ports found.")
    for port, desc, hwid in sorted(ports):
        output.append(f"{port}: {desc} [{hwid}]")
    return "\n".join(output)


class ErrorCodes(Enum):
    """Error codes as defined in the Thermoino code (Thermode_PWM.ino)"""

    ERR_NULL = 0
    ERR_NO_PARAM = -1
    ERR_CMD_NOT_FOUND = -2
    ERR_CTC_BIN_WIDTH = -3
    ERR_CTC_PULSE_WIDTH = -4
    ERR_CTC_NOT_INIT = -5
    ERR_CTC_FULL = -6
    ERR_CTC_EMPTY = -7
    ERR_SHOCK_RANGE = -8
    ERR_SHOCK_ISI = -9
    ERR_BUSY = -10
    ERR_DEBUG_RANGE = -11


class OkCodes(Enum):
    """OK codes as defined in the Thermoino code (Thermode_PWM.ino)"""

    OK_NULL = 0
    OK = 1
    OK_READY = 2
    OK_MOVE_SLOW = 3
    OK_MOVE_PREC = 4


class DummySerial:
    """For testing purposes without a Thermoino device."""

    def __init__(self, *args, **kwargs):
        self.response = None

    def write(self, command):
        command = command.decode()
        if "START" in command:
            self.response = "2"
        elif "MOVE" in command:
            self.response = "3"
        elif "INITCTC" in command:
            self.response = "1"
        elif "LOADCTC" in command:
            self.response = "1"
        elif "QUERYCTC" in command:
            self.response = "1"
        elif "EXECCTC" in command:
            self.response = "1"
        elif "FLUSHCTC" in command:
            self.response = "1"
        else:
            self.response = "0"

    def readline(self, *args, **kwargs):
        return self.response.encode()

    def close(self, *args, **kwargs):
        pass


class Thermoino:
    """
    The `Thermoino` class facilitates communication with the Thermoino device (Arduino to control a thermode).

    The class provides methods to initialize the device and set target temperatures.

    Attributes
    ----------
    PORT : `str`
        The serial port that the Thermoino is connected to.
    BAUD_RATE : `int`
        The baud rate for the serial communication. Default is 115200.
    ser : `serial.Serial or DummySerial`
        Serial object for communication with the Thermoino.
    temp : `int`
        Current (calculated) temperature [°C]. Starts at the baseline temperature.
    mms_baseline : `int`
        Baseline temperature [°C].
        It has to be the same as in the Medoc Main Station (MMS) program.
    mms_rate_of_rise : `int`
        Rate of rise of temperature [°C/s].
        It has to be the same as in the MMS program.

    Methods
    -------
    connect():
        Connect to the Thermoino via serial connection.
    close():
        Close the serial connection.
    diag():
        Get basic diagnostic information from the Thermoino.
    trigger():
        Trigger MMS to get ready for action.
    set_temp(temp_target):
        Set a target temperature on the Thermoino.
    sleep(duration):
        Sleep for a given duration in seconds (using time.sleep).

    New stuff
    -----------
    - renamed init() from the original MATLAB script to connect() to be consistent with python naming conventions

    Examples
    --------
    ```python
    from thermoino import Thermoino, list_com_ports

    # List all available serial ports
    list_com_ports()
    port = "COM7"

    # Set up thermoino
    thermoino = Thermoino(
        port=port,
        mms_baseline=28,  # has to be the same as in MMS
        mms_rate_of_rise=10,  # has to be the same as in MMS
    )

    # Use thermoino to set temperatures:
    thermoino.connect()
    thermoino.trigger()
    time_to_ramp_up, _ = thermoino.set_temp(42)
    thermoino.sleep(duration=time_to_ramp_up)
    # 4 s plateau of 42°C
    thermoino.sleep(4)
    # always update the temperature in the thermoino object
    time_to_ramp_down, _ = thermoino.set_temp(28)
    thermoino.sleep(time_to_ramp_down)
    thermoino.close()
    ```
    """

    BAUD_RATE = 115200

    def __init__(self, port, mms_baseline, mms_rate_of_rise, dummy=False):
        """
        Constructs a Thermoino object.

        Parameters
        ----------
        port : `str`
            The serial port to which the Thermoino device is connected.
        mms_baseline : `int`, optional
            Baseline temperature in °C. It has to be the same as in the MMS program.
        mms_rate_of_rise : `int`
            Rate of rise of temperature in °C/s. It has to be the same as in the MMS program.
            For a Pathways thermode 10 is standard. For TAS 2 it is 13. For CHEPS something over 50 (ask Björn).
            For normal temperature plateaus a higher rate of rise is recommended (faster);
            for complex temperature courses a lower rate of rise is recommended (more precise).
        dummy : `bool`, optional
            If True, the class will run in dummy mode. Default is False.
        """
        self.PORT = port
        self.ser = None  # will be set to the serial object in connect()
        self.mms_baseline = mms_baseline
        self.temp = mms_baseline  # will get continuous class-internal updates to match the temperature of the Thermode
        self.mms_rate_of_rise = mms_rate_of_rise
        self.dummy = dummy
        if self.dummy:
            logger.debug("Running in dummy mode.")

    def connect(self):
        """
        Connect to the Thermoino device.

        Establish a serial connection to the device and waits for it (1 s) to boot up.
        """
        try:
            self.ser = (
                serial.Serial(self.PORT, self.BAUD_RATE)
                if not self.dummy
                else DummySerial()
            )
            logger.debug("Connection established.")
            time.sleep(1)
        except serial.SerialException:
            logger.error("Connection failed @ %s.", self.PORT)
            logger.info(f"Available serial ports are:\n{list_com_ports()}")
            raise serial.SerialException(f"Thermoino connection failed @ {self.PORT}.")

    def close(self):
        """
        Close the serial connection.

        This method should be called manually to close the connection when it's no
        longer needed.
        """
        self.ser.close()
        logger.debug("Connection closed.")
        time.sleep(1)

    def _send_command(self, command, get_response=True):
        """
        Send a command to the Thermoino, read the response, decode it, and then pass
        the numeric response code to the _handle_response function.
        """
        self.ser.write(command.encode())  # encode to bytes
        if get_response:
            response = self.ser.readline()
            try:
                decoded_response = response.decode("ascii").strip()
            except UnicodeDecodeError:
                logger.error("Thermoino response could not be decoded: %s", response)
                decoded_response = None
            return self._handle_response(decoded_response)
        return None

    def _handle_response(self, decoded_response):
        """T
        ake the decoded response from _send_command, determine if it's an error or
        success code based on whether it's less than 0, and convert it to the
        corresponding enum value.
        """

        def _is_integer(s):
            """Check if a string is an integer, .isdigit() does not work for negative
            numbers."""
            try:
                int(s)
                return True
            except ValueError:
                return False

        if not _is_integer(decoded_response):
            return decoded_response  # e.g. when using diag

        decoded_response = int(decoded_response)
        if decoded_response < 0:
            response = ErrorCodes(decoded_response).name
        else:
            response = OkCodes(decoded_response).name
        return response

    def diag(self):
        """Send a 'DIAG' command to the Thermoino to get basic diagnostic
        information."""
        output = self._send_command("DIAG\n")
        logger.info("Diagnostic information: %s.", output)

    def trigger(self):
        """Trigger MMS to get ready for action."""
        output = self._send_command("START\n")
        if output in OkCodes.__members__:
            logger.debug("Triggered.")
        elif output in ErrorCodes.__members__:
            logger.error("Triggering failed: %s.", output)

    def set_temp(self, temp_target):
        """
        Set a target temperature on the Thermoino device.

        Notes
        -----
        The command MOVE does a ramp up (positive numbers) or down (negative numbers) for x microseconds (move_time_us).

        Returns
        -------
        tuple
            (float, bool) - float for the duration [s] for the temperature change, bool for success
        """
        move_time_us = round(((temp_target - self.temp) / self.mms_rate_of_rise) * 1e6)
        output = self._send_command(f"MOVE;{move_time_us}\n")
        duration = math.ceil(abs(move_time_us / 1e6) * 1000) / 1000
        if output in OkCodes.__members__:
            # Update the current temperature
            self.temp = temp_target
            success = True
            logger.info(
                "Change temperature to %s°C in %s s: %s.",
                temp_target,
                round(duration, 2),
                output,
            )
        elif output in ErrorCodes.__members__:
            success = False
            logger.error("Setting temperature to %s°C failed: %s.", temp_target, output)
        return (duration, success)

    def sleep(self, duration):
        """
        Sleep for a given duration in seconds. This function delays the execution in
        Python for a given number of seconds.

        NOTE:
        This function should not be called in a time-critical experiment (e.g. for continuous ratings) as it blocks the execution
        of anything else in the same thread.
        """
        logger.warning("Sleeping for %s s using time.sleep.", float(round(duration, 2)))
        time.sleep(duration)


class ThermoinoComplexTimeCourses(Thermoino):
    """
    The `ThermoinoComplexTimeCourses` class facilitates communication with the
    Thermoino for complex temperature courses (CTC).

    It provides methods to initialize the device, set target temperatures,
    create and load complex temperature courses (CTC) on the Thermoino, and execute these courses.

    NOTE: The resulting temperature course won't be millisecond-precise due to the resampling and binning.
    Account for some delay at the end of the complex time course for the Thermoino to be ready to receive new commands (0.5 s is recommended).

    Attributes
    ----------
    PORT : `str`
        The serial port that the Thermoino is connected to.
    BAUD_RATE : `int`
        The baud rate for the serial communication. Default is 115200.
    ser : `serial.Serial`
        Serial object for communication with the Thermoino.
    temp : `int`
        Current (calculated) temperature [°C]. Starts at the MMS baseline temperature.
    mms_baseline : `int`
        Baseline temperature [°C].
        It has to be the same as in the MMS program.
    mms_rate_of_rise : `int`
        Rate of rise of temperature [°C/s]. It has to be the same as in the MMS program.
        For Pathways 10 is standard. For TAS 2 it is 13. For CHEPS something over 50 (ask Björn).
        For normal temperature plateaus a higher rate of rise is recommended (faster);
        for complex temperature courses a lower rate of rise is recommended (more precise).
    dummy : `bool`
        If True, the class will run in dummy mode. Default is False.
    bin_size_ms : `int`
        Bin size in milliseconds for the complex temperature course.
    temp_course_duration : `int`
        Duration of the temperature course [s].
    temp_course_start : `int`
        Starting temperature of the temperature course [°C].
    temp_course_end : `int`
        Ending temperature of the temperature course [°C].
    ctc : `numpy.array`
        The resampled, differentiated, binned temperature course to be loaded into the Thermoino.

    Methods
    -------
    connect():
        Connect to the Thermoino via serial connection.
    close():
        Close the serial connection.
    diag():
        Get basic diagnostic information from the Thermoino.
    trigger():
        Trigger MMS to get ready for action.
    set_temp(temp_target):
        Set a target temperature on the Thermoino.
    sleep(duration):
        sleep for a given duration in seconds (using time.sleep).
    init_ctc(bin_size_ms):
        Initialize a complex temperature course (CTC) on the Thermoino by sending the bin size (and nothing else).
    create_ctc(temp_course, sample_rate):
        Create a CTC based on the provided temperature course and the sample rate.
    load_ctc(debug = False):
        Load the created CTC into the Thermoino.
    query_ctc(queryLvl, statAbort):
        Query the Thermoino for information about the CTC.
    prep_ctc():
        Prepare the starting temperature of the CTC.
    exec_ctc():
        Execute the loaded CTC on the Thermoino.
    flush_ctc()
        Reset CTC information on the Thermoino. This has to be done before loading a new CTC.

    New stuff
    -----------
    - renamed init() to connect() to be consistent with python naming conventions
    - create_ctc(), where you load your temperature course with sampling rate and it creates the CTC (a resampled, differentiated, binned temperature course)
    - prep_ctc() to prepare the starting temperature for execution of the CTC

    Examples
    --------
    ````python
    import time
    from thermoino import ThermoinoComplexTimeCourses, list_com_ports

    # List all available serial ports
    list_com_ports()
    port = "COM7"

    # Set up thermoino
    thermoino = ThermoinoComplexTimeCourses(
        port=port,
        mms_baseline=28,  # has to be the same as in MMS
        mms_rate_of_rise=10,  # has to be the same as in MMS
    )

    # Use thermoino for complex temperature courses:
    thermoino.connect()
    thermoino.flush_ctc()  # to be sure that no old CTC is loaded
    thermoino.init_ctc(bin_size_ms=500)
    thermoino.create_ctc(temp_course=stimulus.wave, sample_rate=stimulus.sample_rate)
    thermoino.load_ctc()
    thermoino.trigger()
    time_to_ramp_up = thermoino.prep_ctc()
    thermoino.sleep(duration_ms=time_to_ramp_up)
    time_to_exec_ctc = thermoino.exec_ctc()
    thermoino.sleep(time_to_exec_ctc)
    # Account for some delay at the end of the complex time course
    time.sleep(0.5)
    time_to_ramp_down, _ = thermoino.set_temp(32)
    thermoino.flush_ctc()
    thermoino.close()

    # Use thermoino to set temperatures:
    thermoino.connect()
    thermoino.trigger()
    time_to_ramp_up, _ = thermoino.set_temp(42)
    thermoino.sleep(duration=time_to_ramp_up)
    # 4 s plateau of 42°C
    thermoino.sleep(4)
    time_to_ramp_down, _ = thermoino.set_temp(28)
    thermoino.sleep(time_to_ramp_down)
    thermoino.close()
    ````
    """

    def __init__(self, port, mms_baseline, mms_rate_of_rise, dummy=False):
        super().__init__(port, mms_baseline, mms_rate_of_rise, dummy)
        self.bin_size_ms = None
        self.temp_course_duration = None
        self.temp_course_start = None
        self.temp_course_end = None
        self.ctc = None

    def init_ctc(self, bin_size_ms):
        """
        Initialize a complex temperature course (CTC) on the Thermoino device.

        In this first step, the bin size [ms] is defined. This has to be done before
        loading the CTC into the Thermoino (load_ctc).
        """
        output = self._send_command(f"INITCTC;{bin_size_ms}\n")
        if output in OkCodes.__members__:
            logger.debug("Complex temperature course (CTC) initialized.")
            self.bin_size_ms = bin_size_ms
        elif output in ErrorCodes.__members__:
            logger.error(
                "Initializing complex temperature course (CTC) failed: %s.", output
            )

    def create_ctc(self, temp_course, sample_rate):
        """
        Create a complex temperature course (CTC) based on the temperature course and
        sample rate.

        A CTC is a differentiated, binned temperature course.
        On the x-axis, the time course is defined in bin_size_ms.
        On the y-axis, the amount of time for opening the thermode in a bin is defined in ms.

        Note that the mms_rate_of_rise must be sufficiently high to allow for the temperature to be reached in the given time.

        Parameters
        ----------
        temp_course : `numpy.ndarray`
            The temperature course to be used for the CTC.
        sample_rate : `int`
            Sample rate of the temperature course [Hz].

        Side effects
        ------------
        Creates / modifies the following attributes (self.):\n
        `temp_course_duration` : `int`
            Duration of the temperature course [s].
        `temp_course_start` : `int`
            Starting temperature of the temperature course [°C].
        `temp_course_end` : `int`
            Ending temperature of the temperature course [°C].
        `ctc` : `numpy.array`
            The created CTC.
        """
        self.temp_course_duration = temp_course.shape[0] / sample_rate
        # Resample the temperature course to the bin size using pandas (reliable way to resample time series data)
        temp_course_resampled = (
            pd.DataFrame(
                {"temp": temp_course},
                index=pd.to_timedelta(
                    np.arange(len(temp_course)) / sample_rate, unit="s"
                ),
            )
            .resample(f"{self.bin_size_ms}ms", closed="right")
            .ffill()
            .to_numpy()
            .flatten()
        )
        self.temp_course_start = temp_course_resampled[0]
        self.temp_course_end = temp_course_resampled[-1]
        temp_course_resampled_diff = np.diff(temp_course_resampled)
        mms_rate_of_rise_ms = self.mms_rate_of_rise / 1e3
        # scale to mms_rate_of_rise (in milliseconds)
        temp_course_resampled_diff_binned = (
            temp_course_resampled_diff / mms_rate_of_rise_ms
        )
        # Thermoino only accepts integers
        temp_course_resampled_diff_binned = np.round(
            temp_course_resampled_diff_binned
        ).astype(int)
        self.ctc = temp_course_resampled_diff_binned
        logger.debug(
            "Complex temperature course (CTC) created with %s bins of %s ms.",
            len(self.ctc),
            self.bin_size_ms,
        )

    def load_ctc(self, debug=False):
        """
        Load the created CTC into the Thermoino device by sending single bins in a
        for-loop to the Thermoino.

        The maximum length to store on the Thermoino is 2500. If you want longer stimuli, you could use a larger bin size.
        (The max bin size is 500 ms, also keep in mind the 10 min limit of MMS.)

        Parameters
        ----------
        debug : `bool`, optional
            If True, debug information for every bin. Default is False for performance.
        """
        logger.debug("Complex temperature course (CTC) loading started ...")
        for idx, i in enumerate(self.ctc):
            output = self._send_command(f"LOADCTC;{i}\n")

            if output in ErrorCodes.__members__:
                logger.error(
                    f"Error while loading bin {idx + 1} of {len(self.ctc)}. Error code: {output}"
                )
                raise ValueError(
                    f"Error while loading bin {idx + 1} of {len(self.ctc)}. Error code: {output}"
                )
            elif debug:
                logger.debug(
                    "Bin %s of %s loaded. Response: %s.", idx + 1, len(self.ctc), output
                )
        if self.dummy:
            time.sleep(1)

        logger.debug("Complex temperature course (CTC) loaded.")

    def query_ctc(self, queryLvl, statAbort):
        """
        Query information about the complex temperature course (CTC) on the Thermoino
        device. Note: not tested yet.

        This method sends a 'QUERYCTC' command to the device. Depending on the query level (`queryLvl`),
        different types of information are returned, e.g. ctcStatus, ctcBinSize,
        CTC length, the CTC itself.

        Parameters
        ----------
        queryLvl : `int`
            The query level.
            Level 1 returns only the CTC status and verbose status description.
            Level 2 returns additional information, including CTC bin size, CTC length, CTC execution flag,
            and the full CTC (which can take some time to transfer).
        statAbort : `bool`
            If True and the CTC status is 0, an error is raised and execution is stopped.

        Returns
        -------
        `str`
            The output from the Thermoino device.
        """
        output = self._send_command(f"QUERYCTC;{queryLvl};{statAbort}\n")
        logger.info(
            "Querying complex temperature course (CTC) information: %s.", output
        )

    def prep_ctc(self) -> float:
        """Prepare the CTC for the execution by setting the starting temperature.

        Returns the duration in s from the set_temp function.
        """
        logger.info(
            "Preparing the starting temperature of the complex temperature course (CTC)."
        )
        prep_duration, success = self.set_temp(self.temp_course_start)
        if not success:
            logger.error("Preparing complex temperature course (CTC) failed.")
        return prep_duration

    def exec_ctc(self):
        """
        Execute the CTC on the Thermoino device.

        Returns the duration in s of the CTC.
        """
        if self.temp != self.temp_course_start:
            logger.error(
                "Temperature is not set at the starting temperature of the temperature course. Please run prep_ctc first."
            )
            raise ValueError(
                "Temperature is not set at the starting temperature of the temperature course. Please run prep_ctc first."
            )

        exec_duration_s = self.temp_course_duration
        output = self._send_command("EXECCTC\n")
        if output in OkCodes.__members__:
            # Update the temperature to the last temperature of the CTC
            self.temp = self.temp_course_end
            logger.info("Complex temperature course (CTC) started.")
            logger.debug("This will take %s s to finish.", round(exec_duration_s, 2))
            logger.debug("Temperature after execution: %s°C.", round(self.temp, 2))
        elif output in ErrorCodes.__members__:
            logger.error(
                "Executing complex temperature course (CTC) failed: %s.", output
            )
        return exec_duration_s

    def flush_ctc(self):
        """
        Reset or delete all complex temperature course (CTC) information on the
        Thermoino device.

        Important:
        Note that before loading a new CTC, the old one has to be flushed or else it will be appended.
        """
        output = self._send_command("FLUSHCTC\n")
        if output in OkCodes.__members__:
            logger.debug("Flushed complex temperature course (CTC) from memory.")
        elif output in ErrorCodes.__members__:
            logger.error(
                "Flushing complex temperature course (CTC) failed: %s.", output
            )


def main():
    """Showcase the usage of the Thermoino class in dummy mode."""
    import logging

    # Set up very basic logging
    logging.basicConfig(level=logging.DEBUG)

    # List all available serial ports
    print(list_com_ports())
    port = "COM3"

    # Set up the Thermoino in dummy mode
    thermoino = Thermoino(
        port=port,
        mms_baseline=28,  # has to be the same as in MMS
        mms_rate_of_rise=10,  # has to be the same as in MMS
        dummy=True,
    )

    # Use thermoino to set temperatures:
    thermoino.connect()
    thermoino.trigger()
    time_to_ramp_up, _ = thermoino.set_temp(42.3)
    thermoino.sleep(duration=time_to_ramp_up)
    # 4 s plateau of 42°C
    thermoino.sleep(4)
    # always update the temperature in the thermoino object
    time_to_ramp_down, _ = thermoino.set_temp(28)
    thermoino.sleep(time_to_ramp_down)
    thermoino.close()

    # Use thermoino for complex temperature courses:
    temp_course = -np.cos(np.linspace(0, 2 * np.pi, 50)) * 4 + 40
    sample_rate = 10

    thermoino = ThermoinoComplexTimeCourses(
        port=port,
        mms_baseline=28,  # has to be the same as in MMS
        mms_rate_of_rise=10,  # has to be the same as in MMS
        dummy=True,
    )

    thermoino.connect()
    thermoino.flush_ctc()  # to be sure that no old CTC is loaded
    thermoino.init_ctc(bin_size_ms=500)
    thermoino.create_ctc(temp_course=temp_course, sample_rate=sample_rate)
    thermoino.load_ctc()
    thermoino.trigger()
    time_to_ramp_up = thermoino.prep_ctc()
    thermoino.sleep(duration=time_to_ramp_up)
    time_to_exec_ctc = thermoino.exec_ctc()
    thermoino.sleep(time_to_exec_ctc)
    # Account for some delay at the end of the complex time course
    time.sleep(0.5)
    time_to_ramp_down, _ = thermoino.set_temp(28)  # back to baseline
    thermoino.sleep(time_to_ramp_down)
    thermoino.close()


if __name__ == "__main__":
    main()
