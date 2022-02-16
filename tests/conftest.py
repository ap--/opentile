import platform
from os import getenv
from pathlib import Path

import pytest


# --- CONFIGURATION ---
JPEGTURBO_PATH = Path("C:/libjpeg-turbo64/bin/turbojpeg.dll")
OPEN_TILER_TESTDIR = getenv("OPEN_TILER_TESTDIR", "C:/temp/opentile/")


@pytest.fixture(scope="session")
def open_tiler_testdir():
    p = Path(OPEN_TILER_TESTDIR)
    if not p.is_dir():
        pytest.skip("OPEN_TILER_TESTDIR not a directory")
    yield p


@pytest.fixture(scope="session")
def svs_file_path(open_tiler_testdir):
    """yields the svs test image path if available"""
    svs_file_path = open_tiler_testdir / "svs" / "CMU-1" / "CMU-1.svs"
    if not svs_file_path.is_file():
        pytest.skip(reason="svs image not found")
    yield svs_file_path


@pytest.fixture(scope="session")
def ndpi_file_path(open_tiler_testdir):
    """yields the ndpi test image path if available"""
    ndpi_file_path = open_tiler_testdir / "ndpi" / "CMU-1" / "CMU-1.ndpi"
    if not ndpi_file_path.is_file():
        pytest.skip(reason="ndpi image not found")
    yield ndpi_file_path


@pytest.fixture(scope="session")
def philips_file_path(open_tiler_testdir):
    """yields the philips test image path if available"""
    philips_file_path = open_tiler_testdir / "philips_tiff" / "philips1" / "input.tif"
    if not philips_file_path.is_file():
        pytest.skip(reason="philips image not found")
    yield philips_file_path


@pytest.fixture(scope="session")
def jpegturbo_path():
    """yields the path to jpeg-turbo or None if auto-detected"""
    from opentile.jpeg import Jpeg

    if platform.system() == "Windows" and JPEGTURBO_PATH.is_file():
        pth = JPEGTURBO_PATH
    else:
        pth = None
    try:
        Jpeg(pth)  # this tests if jpeg-turbo can be found
    except RuntimeError:
        raise pytest.skip(reason="jpeg-turbo not found")
    yield pth
