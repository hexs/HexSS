from typing import List


def unpack_16bit(words: List[int]) -> int:
    '''
    Example:
        >>> unpack_16bit([65535])
        -1
        >>> unpack_16bit([200])
        200
        >>> unpack_16bit([65535, 200])
        -65336
        >>> unpack_16bit([0, 65535, 200])
        4294901960
        >>> unpack_16bit([1, 200])
        65736
        >>> unpack_16bit([2, 1, 200])
        8590000328
        >>> unpack_16bit([1, 2, 1, 200])
        281483566710984
        >>> unpack_16bit([0xFFFF] * 8)
        -1
    '''
    val = sum((w & 0xFFFF) << (16 * i) for i, w in enumerate(reversed(words)))
    bits = 16 * len(words)
    return val - (1 << bits) if val >> (bits - 1) else val


def pack_16bit(val: int, count: int = 1) -> List[int]:
    '''
    Example:
        >>> pack_16bit(-1, 1)
        [65535]
        >>> pack_16bit(-1, 2)
        [65535, 65535]
        >>> pack_16bit(-1, 4)
        [65535, 65535, 65535, 65535]
        >>> pack_16bit(200)
        [200]
        >>> pack_16bit(200, 2)
        [0, 200]
        >>> pack_16bit(65736, 2)
        [1, 200]
        >>> pack_16bit(65736, 1)
        [200]
        >>> pack_16bit(-1, 8)
        [65535, 65535, 65535, 65535, 65535, 65535, 65535, 65535]
    '''
    val &= (1 << (16 * count)) - 1
    return [(val >> (16 * i)) & 0xFFFF for i in reversed(range(count))]
