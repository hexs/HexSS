import pandas as pd
from typing import Dict, List


def transform_dataframe(dataframe: pd.DataFrame, column_mapping: Dict[str, List[int]]) -> pd.DataFrame:
    """
    Transform the input DataFrame by combining specified columns into new 'pretty' columns.

    Args:
        df (pd.DataFrame): The input DataFrame to transform.
        column_mapping (Dict[str, List[int]]): A dictionary where keys are target column names,
                                               and values are lists of indices of columns to combine.

    Returns:
        pd.DataFrame: A new DataFrame containing the transformed ('pretty') columns.
    """
    if not isinstance(dataframe, pd.DataFrame):
        raise ValueError("Input 'dataframe' must be a pandas DataFrame.")

    if not isinstance(column_mapping, dict):
        raise ValueError("Input 'column_mapping' must be a dictionary.")

    transformed_dataframe = pd.DataFrame()

    for column_name, column_indices in column_mapping.items():

        if not all(isinstance(index, int) for index in column_indices):
            raise ValueError(f"All column indices must be integers. Found: {column_indices}")

        # Combine columns into a single key column using specified mapping
        transformed_dataframe[column_name] = dataframe.iloc[:, column_indices].apply(
            lambda row: sum(row.iloc[i] * (65536 ** (len(column_indices) - i - 1)) for i in range(len(column_indices))),
            axis=1
        )

    return transformed_dataframe


def reverse_transformation(transformed_dataframe: pd.DataFrame, column_mapping: Dict[str, List[int]]) -> pd.DataFrame:
    """
    Reverse the transformation and extract original columns from 'pretty' DataFrame.

    Args:
        pretty_df (pd.DataFrame): The input DataFrame with combined columns.
        column_mapping (Dict[str, List[int]]): A dictionary mapping keys to the original column indices.

    Returns:
        pd.DataFrame: A new DataFrame with original columns computed from 'pretty_df'.
    """
    if not isinstance(transformed_dataframe, pd.DataFrame):
        raise ValueError("Input 'transformed_dataframe' must be a pandas DataFrame.")

    if not isinstance(column_mapping, dict):
        raise ValueError("Input 'column_mapping' must be a dictionary.")

    reconstructed_dataframe = pd.DataFrame()

    for column_name, column_indices in column_mapping.items():
        number_of_columns = len(column_indices)

        # Split the 'pretty' column back into original columns
        for index_position, original_column in enumerate(column_indices):
            reconstructed_dataframe[original_column] = transformed_dataframe[column_name].apply(
                lambda x: (x // (65536 ** (number_of_columns - index_position - 1))) % 65536
            )

    # Ensure original columns are ordered correctly
    reconstructed_dataframe = reconstructed_dataframe.reindex(sorted(reconstructed_dataframe.columns), axis=1)

    return reconstructed_dataframe


if __name__ == "__main__":
    # Example usage

    # Create sample DataFrame
    data = {
        0: [1, 2, 3],
        1: [4, 5, 6],
        2: [7, 8, 9],
        3: [10, 11, 12]
    }
    df = pd.DataFrame(data)

    # Define column mapping: Group columns [0, 1] and [2, 3] into keys 'A' and 'B'
    mapping = {
        "A": [0, 1],
        "B": [2, 3]
    }

    print("DataFrame:")
    print(df)

    # Transform DataFrame
    transformed_dataframe = transform_dataframe(df, mapping)
    print("\nTransformed DataFrame:")
    print(transformed_dataframe)

    # Reverse the transformation
    reconstructed_dataframe = reverse_transformation(transformed_dataframe, mapping)
    print("\nReversed DataFrame:")
    print(reconstructed_dataframe)
