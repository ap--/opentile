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

import math
from dataclasses import dataclass
from typing import Generator, Tuple, Union, Sequence


@dataclass
class SizeMm:
    width: float
    height: float

    def __str__(self) -> str:
        return f'{self.width}x{self.height}'

    def __mul__(self, factor: Union[int, float, 'Size', 'Point']) -> 'SizeMm':
        if isinstance(factor, (int, float)):
            return SizeMm(factor*self.width, factor*self.height)
        elif isinstance(factor, Size):
            return SizeMm(factor.width*self.width, factor.height*self.height)
        elif isinstance(factor, Point):
            return SizeMm(factor.x*self.width, factor.y*self.height)
        return NotImplemented

    def __truediv__(self, divider: Union[int, float, 'SizeMm']) -> 'SizeMm':
        """Return divided SizeMm without rounding."""
        if isinstance(divider, (int, float)):
            return SizeMm(self.width/divider, self.height/divider)
        elif isinstance(divider, SizeMm):
            return SizeMm(
                self.width/divider.width,
                self.height/divider.height
            )
        return NotImplemented

    def __floordiv__(self, divider: Union[int, float, 'SizeMm']) -> 'SizeMm':
        """Return divided SizeMm rounded down to closest integer width and
        height.
        """
        if isinstance(divider, (int, float)):
            return SizeMm(int(self.width/divider), int(self.height/divider))
        if isinstance(divider, SizeMm):
            return SizeMm(
                int(self.width/divider.width),
                int(self.height/divider.height)
            )
        return NotImplemented

    def to_int_tuple(self) -> Tuple[int, int]:
        return int(self.width), int(self.height)

    def to_tuple(self) -> Tuple[float, float]:
        return self.width, self.height

    @classmethod
    def from_tuple(
        cls,
        input: Union[Tuple[float, float], Sequence[float]]
    ) -> 'SizeMm':
        try:
            return cls(input[0], input[1])
        except IndexError:
            raise ValueError("input did not contain two values")


@dataclass
class PointMm:
    x: float
    y: float

    def __str__(self) -> str:
        return f'{self.x},{self.y}'

    def __floordiv__(self, divider: SizeMm) -> 'Point':
        """Return divided PointMm rounded down to closest integer x and y.
        """
        if isinstance(divider, SizeMm):
            return Point(int(self.x/divider.width), int(self.y/divider.height))
        return NotImplemented

    def __add__(
        self,
        value: Union[int, float, SizeMm, 'PointMm']
    ) -> 'PointMm':
        if isinstance(value, (int, float)):
            return PointMm(self.x + value, self.y + value)
        elif isinstance(value, SizeMm):
            return PointMm(self.x + value.width, self.y + value.height)
        elif isinstance(value, PointMm):
            return PointMm(self.x + value.x, self.y + value.y)
        return NotImplemented

    @classmethod
    def from_tuple(
        cls,
        input: Union[Tuple[float, float], Sequence[float]]
    ) -> 'PointMm':
        try:
            return cls(input[0], input[1])
        except IndexError:
            raise ValueError("input did not contain two values")


@dataclass
class Size:
    width: int
    height: int

    def __str__(self) -> str:
        return f'{self.width}x{self.height}'

    def __neg__(self) -> 'Size':
        return Size(-self.width, - self.height)

    def __sub__(self, value: Union[int, 'Size', 'Point']) -> 'Size':
        if isinstance(value, int):
            return Size(self.width - value, self.height - value)
        elif isinstance(value, Size):
            return Size(self.width - value.width, self.height - value.height)
        elif isinstance(value, Point):
            return Size(self.width - value.x, self.height - value.y)
        return NotImplemented

    def __add__(self, value: Union[int, 'Size', 'Point']) -> 'Size':
        if isinstance(value, int):
            return Size(self.width + value, self.height + value)
        elif isinstance(value, Size):
            return Size(self.width + value.width, self.height + value.height)
        elif isinstance(value, Point):
            return Size(self.width + value.x, self.height + value.y)
        return NotImplemented

    def __mul__(self, factor: Union[int, float, 'Size', 'Point']) -> 'Size':
        if isinstance(factor, (int, float)):
            return Size(int(factor*self.width), int(factor*self.height))
        elif isinstance(factor, Size):
            return Size(factor.width*self.width, factor.height*self.height)
        elif isinstance(factor, Point):
            return Size(factor.x*self.width, factor.y*self.height)
        return NotImplemented

    def __floordiv__(
        self,
        divider: Union[int, float, 'Size', SizeMm]
    ) -> 'Size':
        """Return divided Size rounded down to closest integer width and
        height.
        """
        if isinstance(divider, (int, float)):
            return Size(int(self.width/divider), int(self.height/divider))
        elif isinstance(divider, (Size, SizeMm)):
            return Size(
                int(self.width/divider.width),
                int(self.height/divider.height)
            )
        return NotImplemented

    def ceil_div(
        self,
        divider: Union[int, float, 'Size', SizeMm]
    ) -> 'Size':
        """Return divided Size rounded up to closest integer width and height.
        """
        if isinstance(divider, (int, float)):
            return Size(
                math.ceil(self.width/divider),
                math.ceil(self.height/divider)
            )
        elif isinstance(divider, (Size, SizeMm)):
            return Size(
                math.ceil(self.width/divider.width),
                math.ceil(self.height/divider.height)
            )
        return NotImplemented

    def __hash__(self) -> int:
        return hash((self.width, self.height))

    def __lt__(self, item: 'Size') -> bool:
        if isinstance(item, Size):
            return self.width < item.width
        return NotImplemented

    @classmethod
    def from_points(cls, point_1: 'Point', point_2: 'Point') -> 'Size':
        return cls(point_2.x-point_1.x, point_2.y-point_1.y)

    def to_tuple(self) -> Tuple[int, int]:
        return (self.width, self.height)

    @classmethod
    def from_tuple(
        cls,
        input: Union[Tuple[int, int], Sequence[int]]
    ) -> 'Size':
        try:
            return cls(input[0], input[1])
        except IndexError:
            raise ValueError("input did not contain two values")

    @classmethod
    def max(cls, size_1: 'Size', size_2: 'Size') -> 'Size':
        return cls(
            width=max(size_1.width, size_2.width),
            height=max(size_1.height, size_2.height)
        )

    def ceil(self) -> 'Size':
        return Size(
            width=int(math.ceil(self.width)),
            height=int(math.ceil(self.height))
        )

    @property
    def area(self) -> int:
        return self.width * self.height


@dataclass
class Point:
    x: int
    y: int

    def __str__(self) -> str:
        return f'{self.x},{self.y}'

    def __hash__(self) -> int:
        return hash((self.x, self.y))

    def __mul__(self, factor: Union[int, float, Size, 'Point']) -> 'Point':
        if isinstance(factor, (int, float)):
            return Point(int(factor*self.x), int(factor*self.y))
        elif isinstance(factor, Size):
            return Point(factor.width*self.x, factor.height*self.y)
        elif isinstance(factor, Point):
            return Point(factor.x*self.x, factor.y*self.y)
        return NotImplemented

    def __floordiv__(
        self,
        divider: Union[int, float, Size, SizeMm, 'Point']
    ) -> 'Point':
        """Return divided Point rounded down to closest integer x and y."""
        if isinstance(divider, (int, float)):
            return Point(int(self.x/divider), int(self.y/divider))
        elif isinstance(divider, Point):
            return Point(int(self.x/divider.x), int(self.y/divider.y))
        elif isinstance(divider, (Size, SizeMm)):
            return Point(int(self.x/divider.width), int(self.y/divider.height))
        return NotImplemented

    def ceil_div(
        self,
        divider: Union[int, float, 'Point', Size, SizeMm]
    ) -> 'Point':
        """Return divided Point rounded up closest integer x and y."""
        if isinstance(divider, (int, float)):
            return Point(
                math.ceil(self.x/divider),
                math.ceil(self.y/divider)
            )
        elif isinstance(divider, Point):
            return Point(
                math.ceil(self.x/divider.x),
                math.ceil(self.y/divider.y)
            )
        elif isinstance(divider, (Size, SizeMm)):
            return Point(
                math.ceil(self.x/divider.width),
                math.ceil(self.y/divider.height)
            )
        return NotImplemented

    def __mod__(self, divider: Union[Size, 'Point']) -> 'Point':
        if isinstance(divider, Size):
            return Point(self.x % divider.width, self.y % divider.height)
        elif isinstance(divider, Point):
            return Point(self.x % divider.x, self.y % divider.y)
        return NotImplemented

    def __add__(self, value: Union[int, float, Size, 'Point']) -> 'Point':
        if isinstance(value, (int, float)):
            return Point(int(self.x + value), int(self.y + value))
        elif isinstance(value, Size):
            return Point(self.x + value.width, self.y + value.height)
        elif isinstance(value, Point):
            return Point(self.x + value.x, self.y + value.y)
        return NotImplemented

    def __sub__(self, value: Union[int, float, Size, 'Point']) -> 'Point':
        if isinstance(value, (int, float)):
            return Point(int(self.x - value), int(self.y - value))
        elif isinstance(value, Size):
            return Point(self.x - value.width, self.y - value.height)
        elif isinstance(value, Point):
            return Point(self.x - value.x, self.y - value.y)
        return NotImplemented

    @classmethod
    def max(cls, point_1: 'Point', point_2: 'Point') -> 'Point':
        return cls(x=max(point_1.x, point_2.x), y=max(point_1.y, point_2.y))

    @classmethod
    def min(cls, point_1: 'Point', point_2: 'Point') -> 'Point':
        return cls(x=min(point_1.x, point_2.x), y=min(point_1.y, point_2.y))

    def to_tuple(self) -> Tuple[int, int]:
        return (self.x, self.y)

    @classmethod
    def from_tuple(
        cls,
        input: Union[Tuple[int, int], Sequence[int]]
    ) -> 'Point':
        try:
            return cls(input[0], input[1])
        except IndexError:
            raise ValueError("input did not contain two values")


@dataclass
class Region:
    position: Point
    size: Size

    def __str__(self) -> str:
        return f'from {self.start} to {self.end}'

    @property
    def start(self) -> Point:
        return self.position

    @property
    def end(self) -> Point:
        end: Point = self.position + self.size
        return end

    def __mul__(self, value: int) -> 'Region':
        if isinstance(value, int):
            return Region(
                position=self.position * value,
                size=self.size * value
            )
        return NotImplemented

    @property
    def box(self) -> Tuple[int, int, int, int]:
        return self.start.x, self.start.y, self.end.x, self.end.y

    @property
    def box_from_origin(self) -> Tuple[int, int, int, int]:
        return 0, 0, self.size.width, self.size.height

    def iterate_all(
        self,
        include_end: bool = False
    ) -> Generator[Point, None, None]:
        offset = 1 if include_end else 0
        return (
            Point(x, y)
            for y in range(self.start.y, self.end.y + offset)
            for x in range(self.start.x, self.end.x + offset)
        )

    @classmethod
    def from_points(cls, point_1: 'Point', point_2: 'Point') -> 'Region':
        return cls(
            position=point_1,
            size=Size(
                width=point_2.x-point_1.x,
                height=point_2.y-point_1.y
            )
        )

    @classmethod
    def from_tile(cls, tile: 'Point', size: 'Size'):
        return cls(
            position=tile*size,
            size=size
        )

    def is_inside(self, test_region: 'Region') -> bool:
        return bool(
            (self.start.x >= test_region.start.x) and
            (self.start.y >= test_region.start.y) and
            (self.end.x <= test_region.end.x) and
            (self.end.y <= test_region.end.y)
        )

    def crop(self, region: 'Region') -> 'Region':
        start = Point.min(
            Point.max(region.position, self.position),
            self.end
        )
        end = Point.max(
            Point.min(region.end, self.end),
            self.position
        )
        size = Size.from_points(start, end)
        return Region(position=start, size=size)


@dataclass
class RegionMm:
    position: PointMm
    size: SizeMm

    def __str__(self) -> str:
        return f'from {self.start} to {self.end}'

    @property
    def start(self) -> PointMm:
        return self.position

    @property
    def end(self) -> PointMm:
        end: PointMm = self.position + self.size
        return end
