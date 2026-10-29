from pathlib import Path

# Where the worker writes clips (and `manifests/`), and what the API serves from. The
# backend must run on the machine that holds this folder.
RECORDINGS_DIR = Path(__file__).resolve().parents[3] / "recordings"

# `/` and `\` are folders, `:` is a drive or an NTFS stream on Windows, NUL ends C strings.
_FORBIDDEN_IN_NAMES = frozenset("/\\:\x00")


def is_plain_file_name(name: str) -> bool:
    """A single file name: no folders, no `..`, nothing Windows reads as a drive or stream.

    Checked by hand because `Path` rules differ per OS (`a\\b` is one name on Linux).
    """
    return bool(name) and name not in {".", ".."} and not _FORBIDDEN_IN_NAMES & set(name)


def recording_path(*parts: str) -> Path:
    """`RECORDINGS_DIR / parts...`, or `ValueError` for anything that could point outside it.

    Every route that opens or deletes a file from a database value or URL goes through here.
    """
    if not parts or not all(is_plain_file_name(part) for part in parts):
        raise ValueError("Not a plain file name.")
    root = RECORDINGS_DIR.resolve()
    path = root.joinpath(*parts).resolve()
    if not path.is_relative_to(root):  # a symlink inside recordings/ that points elsewhere
        raise ValueError("Path leaves the recordings folder.")
    return path
