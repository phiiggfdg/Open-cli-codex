from pathlib import Path
from setuptools import setup, find_packages

setup(
    name="open-cli-codex",
    version="1.0.0",
    author="Trần Tuấn Phi",
    author_email="phihhhhhhhhhh@gmail.com",
    description="Open CLI Codex — a non-commercial, open-source CLI coding agent",
    url="https://github.com/phiiggfdg/Open-cli-codex",
    py_modules=["fw"],
    packages=find_packages(),
    data_files=[
        (".fw_data/src", [str(p) for p in Path(".fw_data/src").glob("*.py")]),
    ],
    include_package_data=True,
    entry_points={
        "console_scripts": [
            "opencli=fw:main",
        ],
    },
    python_requires=">=3.10",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
)
