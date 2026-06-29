from setuptools import setup, find_packages

setup(
    name="depix",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "watchdog",
    ],
    entry_points={
        "console_scripts": [
            "depix=depix.cli:main",
        ],
    },
)  