from setuptools import setup, find_packages

setup(
    name="pydeps",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "watchdog",
    ],
    entry_points={
        "console_scripts": [
            "pydeps=pydeps.cli:main",
        ],
    },
)  