import pandas as pd
from typing import List, Dict, Optional
from constants import DATE, GENRE_EVT, HORAIRE
from event_utils import parse_bidul_event

def read_and_sort_csv(filename: str) -> Optional[List[Dict]]:
    try:
        df = pd.read_csv(filename, encoding='utf8', keep_default_na=False, na_values=[''])
        df = df.where(pd.notnull(df), None)
        df['Day'] = df[DATE].apply(lambda x: x.split()[1].zfill(2) if x else None)
        df_sorted = df.sort_values(by=['Day', GENRE_EVT, HORAIRE])
        return df_sorted.to_dict('records')
    except Exception as e:
        print(f"Error sorting the file: {e}. Ensure each line has a defined date.")
        return None

def parse_bidul(filename: str) -> tuple:
    body_content = ''
    body_content_agenda = ''
    sorted_events = read_and_sort_csv(filename)
    if sorted_events is None:
        return body_content, body_content_agenda, 0

    current_date = None
    number_of_lines = 0

    for row in sorted_events:
        row = {key: (value.strip() if isinstance(value, str) else value) for key, value in row.items()}
        formatted_line_bidul, formatted_line_agenda, _, current_date = parse_bidul_event(row, current_date)
        body_content += formatted_line_bidul + "\n\n"
        body_content_agenda += formatted_line_agenda + "\n\n"
        number_of_lines += 1

    return body_content, body_content_agenda, number_of_lines
