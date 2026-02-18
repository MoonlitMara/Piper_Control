#!/usr/bin/env python3
import sys
from ui import PiperUI


def main():
    print("Starting Piper Control...")
    app = PiperUI()
    print("Running app...")
    exit_status = app.run(sys.argv)
    print("App exited with status:", exit_status)


if __name__ == "__main__":
    main()
