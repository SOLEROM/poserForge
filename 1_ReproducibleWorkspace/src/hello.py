"""Simple demo module — proves Python toolchain is functional."""

import sys
import platform


def greet(name: str) -> str:
    return f"Hello from Python {sys.version_info.major}.{sys.version_info.minor}, {name}!"


def env_info() -> dict:
    return {
        "python": sys.version,
        "platform": platform.system(),
        "arch": platform.machine(),
    }


if __name__ == "__main__":
    print(greet("poserForge"))
    for key, val in env_info().items():
        print(f"  {key}: {val}")
