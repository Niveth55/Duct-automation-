from setuptools import setup, find_packages

setup(
    name="duct-automation",
    version="1.0.0",
    description="AutoCAD duct layout generator and PP-BOM exporter",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "openpyxl>=3.1.0",
        "PyYAML>=6.0",
    ],
    extras_require={
        "autocad": ["pywin32>=306"],
    },
    entry_points={
        "console_scripts": [
            "duct-automation=duct_automation.cli:main",
        ],
    },
)
