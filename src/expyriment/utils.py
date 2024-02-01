import tkinter as tk
import toml
import yaml
from expyriment import stimuli


def load_configuration(file_path):
    """Load configuration from a TOML file."""
    with open(file_path, "r", encoding="utf8") as file:
        return toml.load(file)


def load_script(file_path):
    """Load script from a YAML file."""
    with open(file_path, "r", encoding="utf8") as file:
        return yaml.safe_load(file)


def prepare_stimuli(script, box_size, text_size):
    """Convert script strings to TextBox stimuli and preload them."""
    for key, value in script.items():
        script[key] = stimuli.TextBox(
            text=value, size=box_size, position=[0, 0], text_size=text_size
        )
        script[key].preload()


def warn_signal():
    """Play a warn signal."""
    stimuli.Tone(duration=500, frequency=440).play()


def center_tk_window(window: tk.Tk):
    """Center a window on the primary screen."""
    window.update_idletasks()
    width = window.winfo_width()
    height = window.winfo_height()
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    center_x = int(screen_width / 2 - width / 2)
    center_y = int(screen_height / 2 - height / 2)
    window.geometry(f"+{center_x}+{center_y}")


def scale_ratio(screen_size, base_screen_size=(1920, 1200)):
    """
    Calculate the scale ratio based on the screen size.
    """
    scale_ratio_width = screen_size[0] / base_screen_size[0]
    scale_ratio_height = screen_size[1] / base_screen_size[1]
    # Use the smaller ratio to ensure fit
    scale_ratio = min(scale_ratio_width, scale_ratio_height)
    return scale_ratio


def scale_text_size(screen_size, base_text_size=40, base_screen_size=(1920, 1200)):
    """
    Calculate the adjusted text size based on the screen size.
    Base sizes are for reference only and can be changed to any value.

    Parameters:
    - screen_size: tuple, current screen size (width, height)
    - base_screen_size: tuple, base screen size (width, height) for scaling reference
    - base_text_size: int, base text size to scale from

    Returns:
    - scaled_text_size: int, scaled text size based on the current screen size

    """
    scale_factor = scale_ratio(screen_size, base_screen_size)
    scaled_text_size = int(base_text_size * scale_factor)
    return scaled_text_size


def scale_box_size(screen_size, base_box_size=(1500, 900), base_screen_size=(1920, 1200)):
    """
    Calculate the adjusted box size based on the screen size.

    Parameters:
    - screen_size: tuple, current screen size (width, height)
    - base_screen_size: tuple, base screen size (width, height) for scaling reference
    - base_box_size: tuple, base box size (width, height) to scale from

    Returns:
    - scaled_box_size: tuple, scaled box size based on the current screen size
    """
    scale_factor = scale_ratio(screen_size, base_screen_size)
    scaled_box_width = int(base_box_size[0] * scale_factor)
    scaled_box_height = int(base_box_size[1] * scale_factor)
    return (scaled_box_width, scaled_box_height)


if __name__ == "__main__":
    """Cheap test for the text scaling functions."""
    from expyriment import control, design

    # Example screen sizes
    size_a = (800, 600)
    size_b = (1024, 768)
    size_c = (1900, 1200)

    # Set the window size for the experiment
    control.defaults.window_size = size_c
    control.set_develop_mode(True)

    # Initialize the experiment
    exp = design.Experiment("Text Scaling Example")
    control.initialize(exp)

    # Determine the current screen size
    screen_size = exp.screen.size

    # Calculate the scaled font size
    scaled_font_size = scale_text_size(screen_size)

    # Calculate the scaled box size
    scaled_box_size = scale_box_size(screen_size)

    # Create a text stimulus with the adjusted font size and box size
    text_stimulus = stimuli.TextBox(
        "Scaled\nText",
        size=scaled_box_size,
        position=(0, 0),
        text_size=scaled_font_size,
        background_colour=(255, 255, 255),
    )

    text_stimulus.preload()
    text_stimulus.present()

    # Keep the window open until a key is pressed
    exp.keyboard.wait()
