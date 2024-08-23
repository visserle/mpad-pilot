import numpy as np
import scipy.signal


def filter_butterworth(
    signal,
    sampling_rate=1000,
    lowcut=None,
    highcut=None,
    order=5,
):
    """Filter a signal using IIR Butterworth SOS (Second-Order Sections) method.

    Applies the butterworth filter twice, once forward and once backwards using
    scipy.signal.sosfiltfilt.
    """
    freqs, filter_type = _filter_sanitize(
        lowcut=lowcut,
        highcut=highcut,
        sampling_rate=sampling_rate,
    )
    sos = scipy.signal.butter(
        order,
        freqs,
        btype=filter_type,
        output="sos",
        fs=sampling_rate,
    )
    return scipy.signal.sosfiltfilt(sos, signal)


def _filter_sanitize(
    lowcut=None,
    highcut=None,
    sampling_rate=1000,
    normalize=False,
):
    """Sanitize the input for filtering.

    Normalize is False by default as there is no need to normalize if `fs` argument is
    provided to the scipy filter.

    Modified from neurokit2 (0.2.10):
    https://github.com/neuropsychology/NeuroKit/blob/master/neurokit2/signal/signal_filter.py
    """
    # Sanity checks
    nyquist_rate = sampling_rate / 2
    max_freq = max(filter(None, [lowcut, highcut]))
    if lowcut is not None or highcut is not None:
        if nyquist_rate <= max_freq:
            raise ValueError(
                "The sampling rate is too low. Sampling rate must exceed the Nyquist "
                "rate to avoid aliasing problem. In this analysis, the sampling rate "
                f"has to be higher than {2 * max_freq} Hz"
            )

    # Replace 0 by None
    lowcut = None if lowcut == 0 else lowcut
    highcut = None if highcut == 0 else highcut

    # Determine filter type and frequencies
    if lowcut is not None and highcut is not None:
        filter_type = "bandstop" if lowcut > highcut else "bandpass"
        # pass frequencies in order of lowest to highest to the scipy filter
        freqs = sorted([lowcut, highcut])
    elif lowcut is not None:
        filter_type = "highpass"
        freqs = lowcut
    elif highcut is not None:
        filter_type = "lowpass"
        freqs = highcut
    else:
        return None, None

    # Normalize frequency to Nyquist Frequency (Fs/2) if required
    # However, no need to normalize if `fs` argument is provided to the scipy filter
    if normalize:
        freqs = np.array(freqs) / nyquist_rate

    return freqs, filter_type