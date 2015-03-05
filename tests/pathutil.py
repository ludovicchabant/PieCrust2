import os


def slashfix(path):
    if path is None:
        return None
    if isinstance(path, str):
        return path.replace('/', os.sep)
    fixed = []
    for p in path:
        fixed.append(p.replace('/', os.sep))
    return fixed

