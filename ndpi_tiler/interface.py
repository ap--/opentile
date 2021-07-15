from collections import defaultdict
import io
import struct
import threading
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from struct import unpack
from typing import DefaultDict, Dict, Generator, List, Optional, Tuple

from PIL import Image
from tifffile import FileHandle, TiffPage
from tifffile.tifffile import TiffPageSeries
from turbojpeg import TurboJPEG


@dataclass
class Size:
    width: int
    height: int

    def __str__(self):
        return f'{self.width}x{self.height}'

    def __add__(self, value):
        if isinstance(value, int):
            return Size(self.width + value, self.height + value)
        return NotImplemented

    def __mul__(self, factor):
        if isinstance(factor, (int, float)):
            return Size(int(factor*self.width), int(factor*self.height))
        elif isinstance(factor, Size):
            return Size(factor.width*self.width, factor.height*self.height)
        elif isinstance(factor, Point):
            return Size(factor.x*self.width, factor.y*self.height)
        return NotImplemented

    def __floordiv__(self, divider):
        if isinstance(divider, Size):
            return Size(
                int(self.width/divider.width),
                int(self.height/divider.height)
            )
        return NotImplemented

    def __truediv__(self, divider):
        if isinstance(divider, Size):
            return Size(
                self.width/divider.width,
                self.height/divider.height
            )
        return NotImplemented

    @staticmethod
    def max(size_1: 'Size', size_2: 'Size'):
        return Size(
            width=max(size_1.width, size_2.width),
            height=max(size_1.height, size_2.height)
        )


@dataclass
class Point:
    x: int
    y: int

    def __str__(self):
        return f'{self.x},{self.y}'

    def __hash__(self) -> int:
        return hash((self.x, self.y))

    def __add__(self, value):
        if isinstance(value, Size):
            return Point(self.x + value.width, self.y + value.height)
        elif isinstance(value, Point):
            return Point(self.x + value.x, self.y + value.y)
        return NotImplemented

    def __sub__(self, value):
        if isinstance(value, Point):
            return Point(self.x - value.x, self.y - value.y)
        return NotImplemented

    def __mul__(self, factor):
        if isinstance(factor, (int, float)):
            return Point(int(factor*self.x), int(factor*self.y))
        elif isinstance(factor, Size):
            return Point(factor.width*self.x, factor.height*self.y)
        elif isinstance(factor, Point):
            return Point(factor.x*self.x, factor.y*self.y)
        return NotImplemented

    def __floordiv__(self, divider):
        if isinstance(divider, Point):
            return Point(int(self.x/divider.x), int(self.y/divider.y))
        elif isinstance(divider, Size):
            return Point(int(self.x/divider.width), int(self.y/divider.height))
        return NotImplemented

    def __mod__(self, divider):
        if isinstance(divider, Size):
            return Point(
                int(self.x % divider.width),
                int(self.y % divider.height)
            )
        elif isinstance(divider, Point):
            return Point(
                int(self.x % divider.x),
                int(self.y % divider.y)
            )
        return NotImplemented


@dataclass
class Region:
    position: Point
    size: Size

    def __str__(self):
        return f'from {self.start} to {self.end}'

    @property
    def start(self) -> Point:
        return self.position

    @property
    def end(self) -> Point:
        end: Point = self.position + self.size
        return end

    def iterate_all(self, include_end=False) -> Generator[Point, None, None]:
        offset = 1 if include_end else 0
        return (
            Point(x, y)
            for y in range(self.start.y, self.end.y + offset)
            for x in range(self.start.x, self.end.x + offset)
        )


class Tags:
    TAG = 0xFF
    TAGS = {
        'start of image': 0xD8,
        'application default header': 0xE0,
        'quantization table': 0xDB,
        'start of frame': 0xC0,
        'huffman table': 0xC4,
        'start of scan': 0xDA,
        'end of image': 0xD9,
        'restart interval': 0xDD,
        'restart mark': 0xD0
    }

    @classmethod
    def start_of_frame(cls) -> bytes:
        """Return bytes representing a start of frame tag."""
        return bytes([cls.TAG, cls.TAGS['start of frame']])

    @classmethod
    def end_of_image(cls) -> bytes:
        """Return bytes representing a end of image tag."""
        return bytes([cls.TAG, cls.TAGS['end of image']])

    @classmethod
    def restart_mark(cls, index: int) -> bytes:
        """Return bytes representing a restart marker of index (0-7), without
        the prefixing tag (0xFF)."""
        return bytes([cls.TAGS['restart mark'] + index % 8])


class NdpiFileHandle:
    """A lockable file handle for reading stripes."""
    def __init__(self, fh: FileHandle):
        self._fh = fh
        self._lock = threading.Lock()

    def read(self, offset: int, bytecount: int) -> bytes:
        """Return bytes.

        Parameters
        ----------
        offset: int
            Offset in bytes.
        bytecount: int
            Length in bytes.

        Returns
        ----------
        bytes
            Requested bytes.
        """
        with self._lock:
            self._fh.seek(offset)
            data = self._fh.read(bytecount)
        return data


class NdpiLevel(metaclass=ABCMeta):
    """Metaclass for a ndpi level."""
    def __init__(
        self,
        page: TiffPage,
        fh: NdpiFileHandle,
        tile_size: Size,
        frame_size: Size,
    ):
        self._page = page
        self._fh = fh
        self._tile_size = tile_size
        self._frame_size = frame_size
        self._framed_size = Size(page.chunked[1], page.chunked[0])
        level_size = self.frame_size * self.framed_size
        self._tiled_size = level_size // tile_size
        self.tiles: Dict[Point, bytes] = {}
        self._tiles_per_frame = Size.max(
            self.frame_size // self.tile_size,
            Size(1, 1)
        )

    @property
    def frame_size(self) -> Size:
        """The size of the stripes in the level."""
        return self._frame_size

    @property
    def framed_size(self) -> Size:
        """The level size when striped (columns and rows of stripes)."""
        return self._framed_size

    @property
    def tiled_size(self) -> Size:
        """The level size when tiled (coluns and rows of tiles)."""
        return self._tiled_size

    @property
    def tile_size(self) -> Size:
        """The size of the tiles to generate."""
        return self._tile_size

    @property
    def tiles_per_frame(self) -> Size:
        """The number of tiles created when parsing one frame."""
        return Size.max(
            self.frame_size // self.tile_size,
            Size(1, 1)
        )

    def get_tile(
        self,
        tile_point: Point
    ) -> bytes:
        """Return tile for tile position x and y. If stripes for the tile
        is not cached, read them from disk and parse the jpeg data.

        Parameters
        ----------
        tile_point: Point
            Position of tile to get.

        Returns
        ----------
        bytes
            Produced tile at position, wrapped in header.
        """
        # Check if tile not in cached
        if tile_point not in self.tiles.keys():
            # Empty cache
            self.tiles = {}
            # Create tiles and add to tile cache
            self.tiles.update(self._create_tiles(tile_point))

        return self.tiles[tile_point]

    @abstractmethod
    def _create_tiles(
        self,
        requested_tile: Point
    ) -> Dict[Point, bytes]:
        raise NotImplementedError

    def _read(self, index: int) -> bytes:
        """Read bytes for frame at index.

        Parameters
        ----------
        index: int
            Index of frame to read.

        Returns
        ----------
        bytes
            Frame bytes.
        """
        offset = self._page.dataoffsets[index]
        bytecount = self._page.databytecounts[index]
        return self._fh.read(offset, bytecount)

    def _map_tile_to_image(self, tile_coordinate: Point) -> Point:
        """Map a tile coorindate to image coorindate.

        Parameters
        ----------
        tile_coordinate: Point
            Tile coordinate that should be map to image coordinate.

        Returns
        ----------
        Point
            Image coordiante for tile.
        """
        return tile_coordinate * self.tile_size

    def _get_origin_tile(self, tile: Point) -> Point:
        ratio = self.frame_size / self.tile_size
        return tile - (tile % ratio)

    def _create_tile_jobs(
        self,
        tile_coordinates: List[Point]
    ) -> List[List[Point]]:
        # Key is origin (upper left) point for the tiles that can be created
        # for a frame
        tile_jobs: DefaultDict[Point, List[Point]] = defaultdict(list)
        for tile in tile_coordinates:
            origin_tile = self._get_origin_tile(tile)
            tile_jobs[origin_tile].append(tile)
        return list(tile_jobs.values())


class NdpiOneFrameLevel(NdpiLevel):
    # For non tiled levels there is only one frame that could be of any size
    # (smaller or larger than the wanted tile size). Make a new frame that is
    # padded to be a even multiple of tile size, and then crop it to create
    # tiles. Can this be done lossless?
    def __init__(
        self,
        page: TiffPage,
        fh: NdpiFileHandle,
        tile_size: Size
    ):
        original_size = Size(page.shape[1], page.shape[0])
        frame_size = (
            (original_size // tile_size + 1) * tile_size
        )
        super().__init__(
            page,
            fh,
            tile_size,
            frame_size,
        )

    def _create_tiles(self, requested_tile: Point) -> Dict[Point, bytes]:
        """Return tiles created...

        Parameters
        ----------
        requested_tile: Point
            Coordinate of requested tile that should be created.

        Returns
        ----------
        Dict[Point, bytes]:
            Created tiles ordered by tile coordiante.
        """
        frame = self._read(0)
        frame_image = Image.open(io.BytesIO(frame))
        padded_frame = Image.new(
            'RGB',
            (self.frame_size.width, self.frame_size.height),
            (255, 255, 255)
        )
        padded_frame.paste(frame_image, (0, 0))

        # crop to tiles
        tile_region = Region(
            Point(0, 0),
            Size.max(self.frame_size // self.tile_size, Size(1, 1))
        )
        tiles: Dict[Point, bytes] = {}
        for tile in tile_region.iterate_all():
            left = self._map_tile_to_image(tile).x % self.frame_size.width
            upper = self._map_tile_to_image(tile).y % self.frame_size.height
            rigth = left + self.tile_size.width
            lower = upper + self.tile_size.height
            tile_image = padded_frame.crop((left, upper, rigth, lower))
            with io.BytesIO() as buffer:
                tile_image.save(buffer, format='jpeg')
                tiles[tile] = buffer.getvalue()

        return tiles


class NdpiStripedLevel(NdpiLevel):
    def __init__(
        self,
        page: TiffPage,
        fh: NdpiFileHandle,
        tile_size: Size,
        jpeg: TurboJPEG
    ):
        self._jpeg = jpeg

        (
            frame_width,
            frame_height, _, _
        ) = self._jpeg.decode_header(page.jpegheader)
        frame_size = Size(frame_width, frame_height)
        super().__init__(
            page,
            fh,
            tile_size,
            frame_size,
        )

        read_size = Size.max(
            self._tile_size,
            self._frame_size
            )
        self._header = self._update_header(self._page.jpegheader, read_size)

    @staticmethod
    def _find_tag(
        header: bytes,
        tag: bytes
    ) -> Tuple[Optional[int], Optional[int]]:
        """Return first index and length of payload of tag in header.

        Parameters
        ----------
        heaer: bytes
            Header to search.
        tag: bytes
            Tag to search for.

        Returns
        ----------
        Tuple[Optional[int], Optional[int]]:
            Position of tag in header and length of payload.
        """
        index = header.find(tag)
        if index != -1:
            (length, ) = unpack('>H', header[index+2:index+4])
            return index, length
        return None, None

    @classmethod
    def _update_header(
        cls,
        header: bytes,
        size: Size,
    ) -> bytes:
        """Return manipulated header with changed pixel size (width, height).

        Parameters
        ----------
        heaer: bytes
            Header to manipulate.
        size: Size
            Pixel size to insert into header.

        Returns
        ----------
        bytes:
            Manupulated header.
        """
        header = bytearray(header)
        start_of_frame_index, length = cls._find_tag(
            header, Tags.start_of_frame()
        )
        if start_of_frame_index is None:
            raise ValueError("Start of scan tag not found in header")
        size_index = start_of_frame_index+5
        header[size_index:size_index+2] = struct.pack(">H", size.height)
        header[size_index+2:size_index+4] = struct.pack(">H", size.width)

        return bytes(header)

    def _stripe_coordinate_to_index(self, coordinate: Point) -> int:
        """Return stripe index from coordinate.

        Parameters
        ----------
        coordinate: Point
            Coordinate of stripe to get index for.

        Returns
        ----------
        int
            Stripe index.
        """
        return coordinate.x + coordinate.y * self.framed_size.width

    def _get_stripe(self, coordinate: Point) -> bytes:
        """Return stripe bytes for stripe at point.

        Parameters
        ----------
        coordinate: Point
            Coordinate of stripe to get.

        Returns
        ----------
        bytes
            Stripe as bytes.
        """
        index = self._stripe_coordinate_to_index(coordinate)
        return self._read(index)

    def _get_stitched_image(self, tile_coordinate: Point) -> bytes:
        """Return stitched image covering tile coorindate as valid jpeg bytes.
        Includes header with the correct image size. Original restart markers
        are updated to get the proper incrementation. End of image tag is
        appended end.

        Parameters
        ----------
        tile_coordinate: Point
            Tile coordinate that should be covered by the stripe region.

        Returns
        ----------
        bytes
            Stitched image as jpeg bytes.
        """
        jpeg_data = self._header
        restart_marker_index = 0
        stripe_region = Region(
            (tile_coordinate * self.tile_size) // self.frame_size,
            Size.max(self.tile_size // self.frame_size, Size(1, 1))
        )
        for stripe_coordiante in stripe_region.iterate_all():
            jpeg_data += self._get_stripe(stripe_coordiante)[:-1]
            jpeg_data += Tags.restart_mark(restart_marker_index)
            restart_marker_index += 1
        jpeg_data += Tags.end_of_image()
        return jpeg_data

    def _create_tiles(
        self,
        requested_tile: Point
    ) -> Dict[Point, bytes]:
        """Return tiles created by parsing jpeg data. Additional tiles than the
        requested tile may be created if the stripes span multiple tiles.

        Parameters
        ----------
        requested_tile: Point
            Coordinate of requested tile that should be created.

        Returns
        ----------
        Dict[Point, bytes]:
            Created tiles ordered by tile coordiante.
        """

        # Starting tile should be at stripe border
        origin_tile = self._get_origin_tile(requested_tile)

        # Create jpeg data from stripes
        jpeg_data = self._get_stitched_image(origin_tile)

        return self._crop_to_tiles(origin_tile, jpeg_data)

    def _crop_to_tiles(
        self,
        starting_tile: Point,
        jpeg_data: bytes
    ) -> Dict[Point, bytes]:
        """Crop jpeg data to tiles.

        Parameters
        ----------
        start_tile: Point
            Coordinate of first tile that should be created.
        jpeg_data: bytes
            Data to crop from.

        Returns
        ----------
        Dict[Point, bytes]:
            Created tiles ordered by tile coordiante.
        """
        tile_region = Region(starting_tile, self.tiles_per_frame)

        return {
            tile: self._jpeg.crop(
                jpeg_data,
                self._map_tile_to_image(tile).x % self.frame_size.width,
                self._map_tile_to_image(tile).y % self.frame_size.height,
                self.tile_size.width,
                self.tile_size.height
            )
            for tile in tile_region.iterate_all()
        }


class NdpiTiler:
    def __init__(
        self,
        tiff_series: TiffPageSeries,
        fh: NdpiFileHandle,
        tile_size: Tuple[int, int],
        turbo_path: Path = None
    ):
        """Cache for ndpi stripes, with functions to produce tiles of specified
        size.

        Parameters
        ----------
        tif: TiffFile
            Tiff file
        fh: NdpiFileHandle
            File handle to stripe data.
        series: int
            Series in tiff file
        tile_size: Tuple[int, int]
            Tile size to cache and produce. Must be multiple of 8.
        turbo_path: Path
            Path to turbojpeg (dll or so).

        """

        self._fh = fh
        self._tile_size = Size(*tile_size)
        self._tiff_series: TiffPageSeries = tiff_series
        if self.tile_size.width % 8 != 0 or self.tile_size.height % 8 != 0:
            raise ValueError(f"Tile size {self.tile_size} not divisable by 8")

        self.jpeg = TurboJPEG(turbo_path)
        self._levels: Dict[int, NdpiLevel] = {}

    @property
    def tile_size(self) -> Size:
        """The size of the tiles to generate."""
        return self._tile_size

    def get_tile(
        self,
        level: int,
        tile_position: Tuple[int, int]
    ) -> bytes:
        """Return tile for tile position x and y. If stripes for the tile
        is not cached, read them from disk and parse the jpeg data.

        Parameters
        ----------
        level: int
            Level of tile to get.
        tile_position: Tuple[int, int]
            Position of tile to get.

        Returns
        ----------
        bytes
            Produced tile at position, wrapped in header.
        """
        try:
            ndpi_level = self._levels[level]
        except KeyError:
            ndpi_level = self._create_level(level)
            self._levels[level] = ndpi_level

        tile_point = Point(*tile_position)
        return ndpi_level.get_tile(tile_point)

    def _create_level(self, level: int) -> NdpiLevel:
        """Create a new level.

        Parameters
        ----------
        level: int
            Level to add

        Returns
        ----------
        NdpiLevel
            Created level.
        """
        page: TiffPage = self._tiff_series.levels[level].pages[0]
        if page.is_tiled:
            return NdpiStripedLevel(page, self._fh, self.tile_size, self.jpeg)
        return NdpiOneFrameLevel(page, self._fh, self.tile_size)
