import io
from posixpath import commonpath
import struct
from dataclasses import dataclass
from pathlib import Path
from struct import unpack
from typing import Callable, Dict, List, Optional, OrderedDict, Set, Tuple, Union

from bitstring import BitArray, Bits, BitStream, ConstBitStream

marker_mapping = {
    0xFFD8: "Start of Image",
    0xFFE0: "Application Default Header",
    0xFFDB: "Quantization Table",
    0xFFC0: "Start of Frame",
    0xFFC4: "Huffman Table",
    0xFFDA: "Start of Scan",
    0xFFD9: "End of Image",
    0xFFFE: "Comment",
    0xFFDD: "Define Restart Interval"
}

TAG = 0xFF
START_OF_IMAGE = 0xFFD8
APPLICATION_DEFAULT_HEADER = 0xFFE0
QUANTIZATION_TABLE = 0xFFDB
START_OF_FRAME = 0xFFC0
HUFFMAN_TABLE = 0xFFC4
START_OF_SCAN = 0xFFDA
END_OF_IMAGE = 0xFFD9

BYTE_TAG = bytes([0xFF])
BYTE_STUFFING = bytes([0x00])

MCU_SIZE = 8


@dataclass
class HuffmanLeaf:
    """Huffman leaf, only contains a value"""
    value: int


@dataclass
class HuffmanNode:
    """Huffman node, contains up to two nodes, that are either other
    Huffman nodes or leaves."""

    def __init__(self, depth: int) -> None:
        """Create a Huffman node at tree depth (code length).

        Parameters
        ----------
        depth: int
            The tree depth of the node.

        """

        self._depth: int = depth
        self._nodes: List[Optional[Union['HuffmanNode', HuffmanLeaf]]] = []

    def __len__(self) -> int:
        return len(self._nodes)

    @property
    def full(self) -> bool:
        """Return True if node is full."""
        return len(self._nodes) > 1

    def _insert_into_self(
        self,
        leaf: HuffmanLeaf,
        depth: int
    ) -> Optional[int]:
        """Return Huffman code for leaf if leaf could be inserted as child to
        this node. Returns None if not inserted."""
        if depth == self._depth and not self.full:
            self._nodes.append(leaf)
            return len(self) - 1
        return None

    def _insert_into_child(
        self,
        leaf: HuffmanLeaf,
        depth: int
    ) -> Optional[int]:
        """Return Huffman code for leaf if leaf could be inserted in a child
        (or a child of a child, recursively) to this node. Returns None if
        not inserted."""
        for index, node in enumerate(self._nodes):
            if isinstance(node, HuffmanNode):
                # Try to insert leaf into child node
                code = node.insert(leaf, depth)
                if code is not None:
                    return code*2 + index
        return None

    def _insert_into_new_child(
        self,
        leaf: HuffmanLeaf,
        depth: int
    ) -> Optional[int]:
        """Return Huffman code for leaf if leaf could be inserted as a new
        child to this node. Returns None if not inserted."""
        if self.full:
            return None
        node = HuffmanNode(self._depth+1)
        node.insert(leaf, depth)
        self._nodes.append(node)
        return len(self) - 1

    def insert(
        self,
        leaf: HuffmanLeaf,
        depth: int
    ) -> Optional[int]:
        """Returns Huffman code for leaf if leaf could be fit inside this node
        or this node's children, recursivley). Returns None if not inserted."""
        # Insertion order:
        # 1. Try to insert leaf directly into this node
        # 2. If there is a child node, try to insert into that
        # 3. Otherwise try to create a new child node
        insertion_order: List[Callable([HuffmanLeaf, int], Optional[int])] = [
            self._insert_into_self,
            self._insert_into_child,
            self._insert_into_new_child
        ]
        for insertion_function in insertion_order:
            code = insertion_function(leaf, depth)
            if code is not None:
                return  code

        # No space for a new child node, insert leaf somewhere else
        return None

    def get(self, key: int) -> Union[None, HuffmanLeaf, 'HuffmanNode']:
        """Return node child from this node"""
        try:
            return self._nodes[key]
        except IndexError:
            return None


class Stream:
    """Convenience class for reading bits from byte stuffed bytes."""
    def __init__(self, data: bytes) -> None:
        """Create a Stream from data. Reads byte by byte from buffer to check
        for tags and byte stuffing. Offers read function for single or multiple
        bits.

        Parameters
        ----------
        data: bytes
            Bytes to stream.

        """
        self._buffer = io.BytesIO(data)

        self._byte = ConstBitStream()

        self._total_read_bits: int = 0

    # @property
    # def pos(self) -> Tuple[int, int]:
    #     """The current bit position."""
    #     return (self._buffer.tell(), self._byte.pos)

    @property
    def pos(self) -> Tuple[int, int]:
        bytes = self._total_read_bits // 8
        bits = self._total_read_bits - bytes * 8
        return (
            bytes,
            bits
        )

    def _read_byte(self) -> bytes:
        """Return next byte from buffer. If read byte is a tag (0xFF), check if
        the coming byte is byte stuffing (0x00) or a tag. Raise ValueError when
        encountering a tag, but this will change."""
        next_byte = self._buffer.read(1)
        # print(f"read byte {next_byte.hex()}")
        if next_byte == BYTE_TAG:
            tag = self._buffer.read(1)
            print(f"tag {tag.hex()}")
            if tag != BYTE_STUFFING:
                raise ValueError(f"tag at position {self.pos}")
        return next_byte

    def read_bit(self) -> int:
        """Return a bit from the buffer. If the stored byte has been read, read
        a new one."""
        if self._byte.pos == 0:
            self._byte = ConstBitStream(self._read_byte())

        bit = self._byte.read('uint:1')
        if self._byte.pos == 8:
            self._byte.pos = 0
        self._total_read_bits += 1
        return bit

    def read_bits(self, count: int) -> List[int]:
        """Read multiple bits from the buffer."""
        return [self.read_bit() for i in range(count)]


class HuffmanTable:
    """Huffman table that can be used to decode bytes"""
    def __init__(
        self,
        header: int,
        symbols_in_levels: List[List[int]]
    ) -> None:
        """Create a Huffman table from specifed table with symbols per level.
        Only the first Huffman table in the data is parsed. The number of bytes
        read for creating the table is avaiable in property byte_length, that
        can be used to read multiple tables.

        Parameters
        ----------
        header: int
            Header of table
        symbols_in_levels: List[List[int]]
            Symbols in the table, listed per level

        """
        self._root = HuffmanNode(0)
        self._header = header

        for depth, level in enumerate(symbols_in_levels):
            for symbol in level:
                leaf = HuffmanLeaf(symbol)
                # Return true if leaf inserted
                if self._root.insert(leaf, depth) is None:
                # if not self._root.insert(leaf, depth):
                    raise ValueError(
                        "Huffman table not correct "
                        f"header {header} symbol {symbol} at depth {depth}"
                    )

    @property
    def byte_length(self) -> int:
        """Byte length of the Huffman table in provide data."""
        return self._byte_length

    @property
    def header(self) -> int:
        """Header of the Huffman table"""
        return self._header

    @classmethod
    def from_data(cls, data: bytes) -> Tuple['HuffmanTable', int]:
        """Create a Huffman table using data from Quantization Table payload.
        Only the first Huffman table in the data is parsed. The number of bytes
        read for creating the table is avaiable in property byte_length, that
        can be used to read multiple tables.

        Parameters
        ----------
        data: bytes
            Quantization Table payload

        Returns
        ----------
        Tuple[HuffmanTable, int]
            Created Huffman table and length read from data
        """
        with io.BytesIO(data) as buffer:
            header: int = unpack('B', buffer.read(1))[0]
            symbols_per_level: Tuple[int] = unpack('B'*16, buffer.read(16))
            symbols_in_levels: List[List[int]] = [
                list(unpack(
                    'B'*number_of_symbols,
                    buffer.read(number_of_symbols)
                ))
                for number_of_symbols in symbols_per_level
            ]
            return (
                cls(header, symbols_in_levels),
                buffer.tell()
            )

    def decode(self, stream: Stream) -> int:
        """Decode stream using Huffman table.

        Parameters
        ----------
        stream: Stream
            Byte stream to decode.
        """
        node = self._root
        # Search table until leaf is found
        while not isinstance(node, HuffmanLeaf):
            bit = stream.read_bit()
            try:
                node = node.get(bit)
            except IndexError:
                raise ValueError(
                    f"error when reading bit {bit} at"
                    f"position{stream.pos}"
                )
        return node.value

    def decode_from_bits(self, bits: ConstBitStream) -> int:
        """Decode bits using Huffman table.

        Parameters
        ----------
        bits: ConstBitStream
            Bits to decode.
        """
        node = self._root
        # Search table until leaf is found
        while not isinstance(node, HuffmanLeaf):
            bit = bits.read('uint:1')
            try:
                node = node._nodes[bit]
            except IndexError:
                raise ValueError(
                    f"error when reading bit {bit} at"
                    f"position{bits.pos}"
                )
        return node.value


class JpegHeader:
    """Class for minimal parsing of jpeg header"""

    def __init__(
        self,
        huffman_tables: List[HuffmanTable],
        width: int,
        height: int,
        table_selection: List[Tuple[int, int]]
    ) -> None:

        self.huffman_tables = {
            table.header: table for table in huffman_tables
        }
        self.width = width
        self.height = height
        self.table_selection = table_selection


    @classmethod
    def from_bytes(cls, data: bytes) -> 'JpegHeader':
        """Parse jpeg header. Read markers from data and parse payload if
        huffman table(s) or start of frame. Ignore other markers (for now)

        Parameters
        ----------
        data: bytes
            Jpeg header in bytes.
        """
        huffman_tables: List[HuffmanTable] = []
        width: int
        height: int
        table_selection: List[Tuple[int]] = []

        with io.BytesIO(data) as buffer:
            marker = cls.read_marker(buffer)
            if not marker == START_OF_IMAGE:
                raise ValueError("Expected start of image marker")
            marker = cls.read_marker(buffer)
            while marker is not None:
                print(marker_mapping[marker])
                if (
                    marker == START_OF_IMAGE or
                    marker == END_OF_IMAGE
                ):
                    raise ValueError("Unexpected marker")
                payload = cls.read_payload(buffer)
                if marker == HUFFMAN_TABLE:
                    huffman_tables += cls.parse_huffman(payload)
                elif marker == START_OF_FRAME:
                    (width, height) = cls.parse_start_of_frame(payload)
                elif marker == START_OF_SCAN:
                    table_selection = cls.parse_start_of_scan(payload)
                else:
                    pass

                marker = cls.read_marker(buffer)
        if (
            huffman_tables == [] or
            width is None or height is None or
            table_selection == []
        ):
            raise ValueError("missing tags")
        return cls(huffman_tables, width, height, table_selection)

    @staticmethod
    def parse_start_of_scan(payload: bytes) -> List[Tuple[int, int]]:
        """Parse start of scan paylaod. Only Huffman table selections are
        extracted.

        Parameters
        ----------
        payload: bytes
            Start of scan in bytes.

        """
        with io.BytesIO(payload) as buffer:
            components: int = unpack('B', buffer.read(1))[0]
            table_selection: List[Tuple[int, int]] = [
                unpack('BB', buffer.read(2))
                for component in range(components)
            ]
        return table_selection


    @staticmethod
    def parse_huffman(payload: bytes) -> List[HuffmanTable]:
        """Parse huffman table(s) in payload. Multiple tables can be defined in
        the same tag. Each table is stored in a dict with header as key.

        Parameters
        ----------
        payload: bytes
            Huffman table in bytes.

        """
        tables: List[HuffmanTable] = []
        table_start = 0
        while(table_start < len(payload)):
            (table, byte_read) = HuffmanTable.from_data(payload[table_start:])
            tables.append(table)
            print(f"got huffman with header {table.header}")
            table_start += byte_read
        return tables

    @staticmethod
    def parse_start_of_frame(payload: bytes) -> Tuple[int, int]:
        """Parse start of frame paylaod. Only height and width of frame is
        important.

        Parameters
        ----------
        payload: bytes
            Start of frame in bytes.

        """
        hdr, height, width, components = unpack('>BHHB', payload[0:6])
        return (width, height)

    @staticmethod
    def read_marker(buffer: io.BytesIO) -> Optional[int]:
        """Read a marker from buffer.

        Parameters
        ----------
        buffer: io.BytesIO
            Buffer to read marker from.

        """
        try:
            (marker,) = unpack('>H', buffer.read(2))
            return marker
        except struct.error:
            return None

    @staticmethod
    def read_payload(buffer: io.BytesIO) -> bytes:
        """Read a payload from buffer.

        Parameters
        ----------
        buffer: io.BytesIO
            Buffer to read payload from.

        """
        payload_length = unpack('>H', buffer.read(2))[0]
        # Payload length includes length bytes
        return buffer.read(payload_length-2)


class JpegScan:
    """Class for minimal decoding of jpeg scan data"""

    def __init__(
        self,
        header: JpegHeader,
        data: bytes
    ):
        """Parse jpeg scan using info in header.

        Parameters
        ----------
        header: JpegHeader
            Header containing
        data: bytes
            Jpeg scan data, excluding start of scan tag

        """
        # self.data = data
        # print(f"jpeg scan data {data.hex()}")
        self.huffman_tables = header.huffman_tables
        self.mcu_count = header.height * header.width // (MCU_SIZE * MCU_SIZE)
        self.mcu_positions = self.get_mcu_positions(data)
        self.table_selection = header.table_selection

    def get_mcu_positions(self, data: bytes) -> List[Tuple[int, int]]:
        """Return list of mcu positions in scan (relative to scan start).

        Parameters
        ----------
        data: bytes
            Jpeg scan data.

        Returns
        ----------
        List[int]
            List of mcu positions.
        """
        stream = Stream(data)
        self.mcu = 0

        positions = [
            self.read_mcu_position(stream)
            for mcu in range(self.mcu_count)
        ]
        return positions

    def read_mcu_position(self, stream) -> Tuple[int, int]:
        self.mcu += 1
        position = stream.pos
        huffmant_table_indices = [0, 1, 1]
        for index in huffmant_table_indices:
            self.read_component(stream, index)
        return position

    def read_component(self, stream: Stream, index: int) -> None:
        """Read single component of a MCU

        Parameters
        ----------
        stream: Stream
            Stream of jpeg scan data
        index: int
            Index of Huffman table to use
        """
        dc_table = self.huffman_tables[index]
        ac_table = self.huffman_tables[16+index]
        dc_amplitude_length = dc_table.decode(stream)
        dc_amplitude = stream.read_bits(dc_amplitude_length)
        mcu_length = 1

        while mcu_length < 64:
            code = ac_table.decode(stream)
            if code == 0:
                mcu_length = 64
            else:
                # First 4 bits are number of leading zeros
                zeros = code >> 4
                mcu_length += zeros
                # Second 4 bits are ac amplitude length
                ac_amplitude_length = code & 0x0F
                ac_amplitude = stream.read_bits(ac_amplitude_length)
                mcu_length += 1
