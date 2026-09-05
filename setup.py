"""Minimal setup.py wrapper for backward-compatibility with editable installs."""

from setuptools import setup

setup(
    install_requires=[
        "requests>=2.31.0",
        "tqdm>=4.66.0",
        "ameva-runtime>=2.0.0",
    ]
)
