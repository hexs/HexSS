from hexss.pandas.dataframe_transformation import transform_dataframe, reverse_transformation

column_mapping = {
    "Target | (0,1)": [0, 1],
    "Speed | (4,5)": [4, 5],
    "Acceleration | (10)": [10],
    "Deceleration | (11)": [11],
    "Zone Boundary (+) | (6,7)": [6, 7],
    "Zone Boundary (-) | (8,9)": [8, 9],
    "(2)": [2],
    "(3)": [3],
    "(12)": [12],
    "(13)": [13],
    "(14)": [14],
    "(15)": [15],
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
