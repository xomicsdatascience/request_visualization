# Entry point for the Agent Request Visualization application.

import sys
from importlib import resources
from pathlib import Path

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from .widgets import MainWindow


def _get_icon_path() -> Path:
    """Get the path to the application icon.

    Returns
    -------
    Path
        Path to the icon file.
    """
    with resources.as_file(
        resources.files("request_visualization.resources").joinpath("icon.svg")
    ) as icon_path:
        # Return a copy of the path since context manager will clean up
        return Path(icon_path)


def main(db_path: Path | None = None) -> int:
    """Run the request visualization application.

    Parameters
    ----------
    db_path : Path | None
        Optional path to the SQLite database. If None, uses the default path.

    Returns
    -------
    int
        Exit code from the application.
    """
    app = QApplication(sys.argv)
    app.setApplicationName("Agent Request Visualization")
    app.setOrganizationName("MCP")
    app.setDesktopFileName("request-viz")

    # Set application icon
    icon_path = _get_icon_path()
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    if db_path:
        window = MainWindow(db_path)
    else:
        window = MainWindow()

    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
