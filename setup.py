"""Setuptools shim so `pip install -e .` works with older pip versions."""

from setuptools import setup

if __name__ == "__main__":
    setup()
