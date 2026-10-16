"""Search the same channel details that the guide presents to the viewer."""
import unicodedata


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(text).casefold())
                   if not unicodedata.combining(c))


def filter_channels(rows, query):
    words = normalized(query).split()
    if not words:
        return tuple(rows)
    return tuple(row for row in rows if all(word in normalized(
        f'{row.number:02d} {row.number} {row.name} {row.episode}') for word in words))
