from hexss.pandas.dataframe_transformation import transform_dataframe, reverse_transformation

column_mapping = {
    "Target": [0, 1],
    "INP": [2, 3],  # Positioning band
    "Speed": [4, 5],
    "ZNMP": [6, 7],  # "Zone Boundary (+) | (6,7)": [6, 7],
    "ZNLP": [8, 9],  # "Zone Boundary (-) | (8,9)": [8, 9],
    "Acc": [10],  # "Acceleration | (10)": [10],
    "Dec": [11],  # "Deceleration | (11)": [11],
    "PPOW": [12],  # Push-current limiting value
    "LPOW": [13],  # Load current threshold
    "CTLF": [14,15],  # Control flag specification
}


def read_p_df(robot, slave_id: int):
    df = robot.read_table_data(slave_id)
    p_df = transform_dataframe(df, column_mapping)
    data = {
        'data': p_df.values.tolist(),
        'rowHeaders': [f"{i}" for i in range(len(p_df.values.tolist()))],
        'colHeaders': p_df.columns.tolist(),
        'columns': [{'type': 'numeric'} for _ in range(len(p_df.columns.tolist()))],
        'manualColumnResize': True,
        'manualRowResize': True,
        'contextMenu': ['undo', 'redo', '---------', 'cut', 'copy'],
        'licenseKey': 'non-commercial-and-evaluation',
        'stretchH': 'all',
        'height': 'auto',
        'width': '100%'
    }
    return data


def write_p_df(robot, slave_id: int, p_df):
    df = reverse_transformation(p_df, column_mapping)
    robot.write_table_data(slave_id, df)
