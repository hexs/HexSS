from typing import Union, List
import numpy as np


def combine_uint16_to_int32(arr: Union[np.array, List[int]]) -> np.int32:
    """
    Combines two 16-bit unsigned integers into a single 32-bit signed integer.

    Parameters:
        arr (list or np.array): A list or array of two uint16 values.

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
    if len(arr) != 2:
        raise ValueError("Input must be a list or array of two uint16 values.")

    arr = np.asarray(arr, dtype=np.uint16)
    combined = (np.uint32(arr[0]) << 16) | np.uint32(arr[1])

    return combined.view(np.int32)


def split_int32_to_uint16(value: Union[np.array, int]) -> np.array:
    """
    Splits a 32-bit signed integer into a numpy array of two 16-bit unsigned integers.

    Parameters:
        value (int or np.int32): A 32-bit signed integer.

    Returns:
        np.array: A numpy array of two uint16 values.

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
