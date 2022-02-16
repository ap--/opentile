#    Copyright 2021 SECTRA AB
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

import unittest
from contextlib import closing
from hashlib import md5

import pytest
from opentile.philips_tiff_tiler import PhilipsTiffTiler


@pytest.fixture(scope="class")
def _philips_tiff_tiler(request, philips_file_path, jpegturbo_path):
    tiler = PhilipsTiffTiler(
        philips_file_path,
        jpegturbo_path
    )
    request.cls.tiler = tiler
    request.cls.level = tiler.get_level(0)
    with closing(tiler):
        yield


@pytest.mark.unittest
@pytest.mark.usefixtures("_philips_tiff_tiler")
class PhilipsTiffTilerTest(unittest.TestCase):
    tiler: PhilipsTiffTiler

    def test_get_tile(self):
        tile = self.level.get_tile((0, 0))
        self.assertEqual(
            '570d069f9de5d2716fb0d7167bc79195',
            md5(tile).hexdigest()
        )
        tile = self.level.get_tile((20, 20))
        self.assertEqual(
            'db28efb73a72ef7e2780fc72c624d7ae',
            md5(tile).hexdigest()
        )
