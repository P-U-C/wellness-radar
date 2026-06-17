from __future__ import annotations

from setuptools import find_packages, setup

setup(
    name="wellness-radar",
    version="0.1.0",
    description="Vancouver wellness market-intelligence console",
    packages=find_packages(include=["apps*", "packages*", "db*"]),
    python_requires=">=3.10",
    install_requires=[
        "fastapi>=0.135.0",
        "httpx>=0.28.0",
        "psycopg[binary]>=3.2.0",
        "pydantic>=2.12.0",
        "pydantic-settings>=2.13.0",
        "uvicorn>=0.44.0",
    ],
    extras_require={
        "dev": [
            "mypy>=2.1.0",
            "pytest>=9.0.0",
            "ruff>=0.15.0",
        ]
    },
)
