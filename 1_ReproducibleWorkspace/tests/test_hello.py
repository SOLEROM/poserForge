"""pytest tests for the hello module."""

import sys
import pytest

sys.path.insert(0, "/workspace/src")
from hello import greet, env_info


def test_greet_contains_name():
    result = greet("world")
    assert "world" in result


def test_greet_contains_python_version():
    result = greet("test")
    assert "Python" in result
    assert str(sys.version_info.major) in result


def test_env_info_keys():
    info = env_info()
    assert "python" in info
    assert "platform" in info
    assert "arch" in info


def test_env_info_python_version():
    info = env_info()
    # Must be Python 3.11 as pinned in Dockerfile
    assert sys.version_info >= (3, 11), f"Expected >= 3.11, got {sys.version_info}"
