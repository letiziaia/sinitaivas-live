import utils.files_storage as fs
from typing import Final


CURSORS_FILE: Final = "cursors.json"

PATH_TO_CURSORS_FILE: Final = f"{fs.current_dir()}/{CURSORS_FILE}"
