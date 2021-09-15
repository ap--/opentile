import os
import unittest
from hashlib import md5

import pytest
from opentile import SvsTiler, __version__
from opentile.geometry import Point, Region, Size, SizeMm
from opentile.svs_tiler import SvsTiledPage
from tifffile import TiffFile
from tifffile.tifffile import TiffFile

svs_test_data_dir = os.environ.get(
    "OPEN_TILER_TESTDIR",
    "C:/temp/opentile/svs/"
)
sub_data_path = "input.svs"
svs_file_path = svs_test_data_dir + '/' + sub_data_path


@pytest.mark.unittest
class SvsTilerTest(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tif: TiffFile
        self.tiler: SvsTiler
        self.level: SvsTiledPage

    @classmethod
    def setUpClass(cls):
        cls.tiler = SvsTiler(svs_file_path)
        cls.level: SvsTiledPage = cls.tiler.get_level(0)

    @classmethod
    def tearDownClass(cls):
        cls.tiler.close()

    def test_get_tile(self):
        tile = self.level.get_tile(Point(0, 0))
        self.assertEqual(
            'd233adca5123262394a45a2cc7d5f6cf',
            md5(tile).hexdigest()
        )
        tile = self.level.get_tile(Point(20, 20))
        self.assertEqual(
            'baab24a3fd1ef3e5b74bac00790c8480',
            md5(tile).hexdigest()
        )
