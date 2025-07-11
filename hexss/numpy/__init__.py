from typing import Union, List
import numpy as np


def combine_uint16_to_int32(arr: Union[np.ndarray, List[int]]) -> np.int32:
    """
    Combines two 16-bit unsigned integers into a single 32-bit signed integer.

    Parameters:
        arr (list or np.ndarray): A list or array of two uint16 values.

    Returns:
        np.int32: A signed 32-bit integer.

    Example:
        >>> combine_uint16_to_int32([65535, 65535])
        np.int32(-1)
        >>> combine_uint16_to_int32([65535, 65534])
        np.int32(-2)
        >>> combine_uint16_to_int32([0, 65535])
        np.int32(65535)
    """
    arr = np.asarray(arr, dtype=np.uint16)
    if arr.shape != (2,):
        raise ValueError("Input must be a list or array of exactly two uint16 values.")

    # Combine the two uint16s into a uint32 (big-endian: arr[0]=high, arr[1]=low)
    combined_uint32 = (np.uint32(arr[0]) << 16) | np.uint32(arr[1])
    return combined_uint32.view(np.int32)


def split_int32_to_uint16(value: Union[np.int32, int, np.ndarray]) -> np.ndarray:
    """
    Splits a 32-bit signed integer into a numpy array of two 16-bit unsigned integers.

    Parameters:
        value (int or np.int32): A 32-bit signed integer.

    Returns:
        np.ndarray: A numpy array of two uint16 values.

    Example:
        >>> split_int32_to_uint16(np.int32(-1))
        array([65535, 65535], dtype=uint16)
        >>> split_int32_to_uint16(np.int32(-2))
        array([65535, 65534], dtype=uint16)
        >>> split_int32_to_uint16(np.int32(65535))
        array([    0, 65535], dtype=uint16)
    """
    value = np.int32(value)
    unsigned_value = value.view(np.uint32)
    high = np.uint16(unsigned_value >> 16)
    low = np.uint16(unsigned_value & 0xFFFF)
    return np.array([high, low], dtype=np.uint16)


def uint8(x: int) -> int:
    return int(np.uint8(x & 0xFF))


def uint16(x: int) -> int:
    return int(np.uint16(x & 0xFFFF))


def uint32(x: int) -> int:
    return int(np.uint32(x & 0xFFFFFFFF))


def int8(x: int) -> int:
    return int(np.uint8(x & 0xFF).view(np.int8))


def int16(x: int) -> int:
    return int(np.uint16(x & 0xFFFF).view(np.int16))


def int32(x: int) -> int:
    return int(np.uint32(x & 0xFFFFFFFF).view(np.int32))


if __name__ == '__main__':
    x_list = [-2, 0, 2, 65534, 4294967294]
    for x in x_list:
        print(f"16 bit {x} -> {int16(x)}")
        print(f"32 bit {x} -> {int32(x)}")
        print()
