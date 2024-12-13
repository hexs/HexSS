import os
import signal


def kill():
    """
    Sends a SIGINT signal to the current process, effectively terminating it.
    Useful for simulating process termination during development or testing.

    Raises:
        OSError: If the signal sending fails due to permission or process issues.
    """
    try:
        # Send SIGINT to current process
        os.kill(os.getpid(), signal.SIGINT)
    except OSError as e:
        print(f"Error: Could not terminate the process. Details: {e}")
