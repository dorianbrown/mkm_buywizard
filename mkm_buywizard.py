#!/usr/bin/env python

import argparse

from buywizard_app import BuywizardApp


def main():
    parser = argparse.ArgumentParser(description="mkm_buywizard command line interface.")
    parser = parser.add_argument("--config", default="config.json", help="Location of config.json")

    app = BuywizardApp()
    app.start()


if __name__ == "__main__":
    main()
