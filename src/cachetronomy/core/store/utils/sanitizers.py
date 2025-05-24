import json
import logging

from sqlite3 import Row


def clean_tags(row: Row):
    try:
        cleaned_row: dict = dict(row)
        try:
            cleaned_row['tags'] = json.loads(cleaned_row.get('tags') or '[]')
        except json.JSONDecodeError:
            cleaned_row['tags'] = []
        except (TypeError, KeyError):
            cleaned_row['tags'] = []
        return cleaned_row
    except (TypeError, ValueError) as e:
        logging.error(f'Error cleaning tags: {e}')
        return {}
