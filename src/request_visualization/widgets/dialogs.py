# Dialog widgets for the request visualization GUI.
# Provides modal dialogs for approving, rejecting, revising, and creating requests.
# The NewRequestDialog supports selecting existing projects or creating new ones.

from pathlib import Path

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
)

from ..models import AgentRequest


class ApproveDialog(QDialog):
    """Modal dialog for entering an optional approval reason."""

    def __init__(self, parent=None):
        """Initialize the approve dialog.

        Parameters
        ----------
        parent : QWidget, optional
            Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Approve Request")
        self.setMinimumWidth(400)
        self.setMinimumHeight(200)

        layout = QVBoxLayout(self)

        label = QLabel("Enter reason for approval (optional):")
        layout.addWidget(label)

        self.reason_edit = QTextEdit()
        self.reason_edit.setPlaceholderText("Enter your reason here...")
        layout.addWidget(self.reason_edit)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_reason(self) -> str:
        """Get the entered approval reason.

        Returns
        -------
        str
            The approval reason text.
        """
        return self.reason_edit.toPlainText().strip()


class RejectDialog(QDialog):
    """Modal dialog for entering a rejection reason."""

    def __init__(self, parent=None):
        """Initialize the reject dialog.

        Parameters
        ----------
        parent : QWidget, optional
            Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Reject Request")
        self.setMinimumWidth(400)
        self.setMinimumHeight(200)

        layout = QVBoxLayout(self)

        label = QLabel("Enter reason for rejection:")
        layout.addWidget(label)

        self.reason_edit = QTextEdit()
        self.reason_edit.setPlaceholderText("Enter your reason here...")
        layout.addWidget(self.reason_edit)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_reason(self) -> str:
        """Get the entered rejection reason.

        Returns
        -------
        str
            The rejection reason text.
        """
        return self.reason_edit.toPlainText().strip()


class ReviseDialog(QDialog):
    """Modal dialog for revising a request's text.

    Used when an implemented request needs modifications before re-implementation.
    """

    def __init__(self, current_request_text: str, parent=None):
        """Initialize the revise dialog.

        Parameters
        ----------
        current_request_text : str
            The current request text to display for editing.
        parent : QWidget, optional
            Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Revise Request")
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)

        layout = QVBoxLayout(self)

        label = QLabel(
            "Edit the request below. After saving, the request will be marked "
            "as 'approved' and queued for re-implementation."
        )
        label.setWordWrap(True)
        layout.addWidget(label)

        self.request_edit = QTextEdit()
        self.request_edit.setPlainText(current_request_text)
        layout.addWidget(self.request_edit)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_revised_text(self) -> str:
        """Get the revised request text.

        Returns
        -------
        str
            The revised request text.
        """
        return self.request_edit.toPlainText().strip()


class RequestDetailDialog(QDialog):
    """Modal dialog for viewing full request details."""

    def __init__(self, request: AgentRequest, parent=None):
        """Initialize the request detail dialog.

        Parameters
        ----------
        request : AgentRequest
            The request to display.
        parent : QWidget, optional
            Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle(f"Request #{request.id} Details")
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)

        layout = QVBoxLayout(self)

        # Request metadata
        meta_text = (
            f"<b>ID:</b> {request.id}<br>"
            f"<b>Agent:</b> {request.agent_name}<br>"
            f"<b>Created:</b> {request.creation_time.strftime('%Y-%m-%d %H:%M:%S')}<br>"
            f"<b>Status:</b> {request.request_status}<br>"
            f"<b>Updated:</b> {request.updated_at.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        meta_label = QLabel(meta_text)
        layout.addWidget(meta_label)

        # Request content
        layout.addWidget(QLabel("<b>Request:</b>"))
        request_edit = QTextEdit()
        request_edit.setPlainText(request.request)
        request_edit.setReadOnly(True)
        layout.addWidget(request_edit)

        # Reason for request
        if request.reason_for_request:
            layout.addWidget(QLabel("<b>Reason for Request:</b>"))
            reason_edit = QTextEdit()
            reason_edit.setPlainText(request.reason_for_request)
            reason_edit.setReadOnly(True)
            reason_edit.setMaximumHeight(100)
            layout.addWidget(reason_edit)

        # Status reason (if rejected)
        if request.status_reason:
            layout.addWidget(QLabel("<b>Status Reason:</b>"))
            status_edit = QTextEdit()
            status_edit.setPlainText(request.status_reason)
            status_edit.setReadOnly(True)
            status_edit.setMaximumHeight(100)
            layout.addWidget(status_edit)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)


class NewRequestDialog(QDialog):
    """Modal dialog for creating a new request.

    Supports selecting an existing project from a dropdown or creating a new project
    by selecting "New Project" and entering a project name.
    """

    # Default base directory for discovering projects
    DEFAULT_BASE_DIR = Path("./")

    # Special option for creating a new project
    NEW_PROJECT_OPTION = "New Project"

    def __init__(self, parent=None, base_dir: Path | str | None = None):
        """Initialize the new request dialog.

        Parameters
        ----------
        parent : QWidget, optional
            Parent widget.
        base_dir : Path | str | None, optional
            Base directory to search for project directories.
            Defaults to /home/lex/projects/mcp.
        """
        super().__init__(parent)
        self.setWindowTitle("New Request")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        self._base_dir = Path(base_dir) if base_dir else self.DEFAULT_BASE_DIR

        layout = QVBoxLayout(self)

        # Form layout for fields
        self.form_layout = QFormLayout()

        # Project dropdown (directories of the base directory)
        self.project_combo = QComboBox()
        self.project_combo.addItem("")  # Blank default option
        self._populate_projects()
        self.project_combo.addItem(self.NEW_PROJECT_OPTION)  # Add "New Project" option
        self.form_layout.addRow("Project:", self.project_combo)

        # New project name field (initially hidden)
        self.new_project_label = QLabel("New Project Name:")
        self.new_project_edit = QLineEdit()
        self.new_project_edit.setPlaceholderText("Enter new project name...")
        self.form_layout.addRow(self.new_project_label, self.new_project_edit)
        self.new_project_label.hide()
        self.new_project_edit.hide()

        # Connect signal to show/hide new project name field
        self.project_combo.currentTextChanged.connect(self._on_project_changed)

        # Agent name field (defaults to "human")
        self.agent_name_edit = QLineEdit()
        self.agent_name_edit.setText("human")
        self.agent_name_edit.setPlaceholderText("Enter agent name...")
        self.form_layout.addRow("Agent Name:", self.agent_name_edit)

        layout.addLayout(self.form_layout)

        # Request field (multi-line)
        layout.addWidget(QLabel("Request:"))
        self.request_edit = QTextEdit()
        self.request_edit.setPlaceholderText("Enter your request here...")
        layout.addWidget(self.request_edit)

        # Reason for request field (multi-line, optional)
        layout.addWidget(QLabel("Reason for Request (optional):"))
        self.reason_edit = QTextEdit()
        self.reason_edit.setPlaceholderText("Enter reason for the request...")
        self.reason_edit.setMaximumHeight(100)
        layout.addWidget(self.reason_edit)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self._validate_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _populate_projects(self) -> None:
        """Populate the project dropdown with directories from the base directory.

        Excludes hidden directories (starting with '.') and common non-project
        directories like .venv.
        """
        if not self._base_dir.exists():
            return

        # Get all subdirectories, excluding hidden ones and common non-project dirs
        exclude_patterns = {".venv", "__pycache__", ".git", ".tox", "node_modules"}

        for path in sorted(self._base_dir.iterdir()):
            if path.is_dir() and not path.name.startswith("."):
                if path.name not in exclude_patterns:
                    self.project_combo.addItem(path.name)

    def _on_project_changed(self, text: str) -> None:
        """Handle project dropdown selection change.

        Shows or hides the new project name field based on whether
        "New Project" is selected.

        Parameters
        ----------
        text : str
            The currently selected project text.
        """
        if text == self.NEW_PROJECT_OPTION:
            self.new_project_label.show()
            self.new_project_edit.show()
            self.new_project_edit.setFocus()
        else:
            self.new_project_label.hide()
            self.new_project_edit.hide()
            self.new_project_edit.clear()

    def _validate_and_accept(self) -> None:
        """Validate form fields and accept if valid.

        Shows an error message if "New Project" is selected but no
        project name is provided.
        """
        if self.project_combo.currentText() == self.NEW_PROJECT_OPTION:
            new_project_name = self.new_project_edit.text().strip()
            if not new_project_name:
                QMessageBox.warning(
                    self,
                    "Validation Error",
                    "New project name is required when 'New Project' is selected.",
                )
                self.new_project_edit.setFocus()
                return
        self.accept()

    def get_project(self) -> str:
        """Get the selected project.

        Returns the new project name if "New Project" is selected and a name
        is provided, otherwise returns the selected existing project name.

        Returns
        -------
        str
            The selected or entered project name, or empty string if none selected.
        """
        selected = self.project_combo.currentText().strip()
        if selected == self.NEW_PROJECT_OPTION:
            return self.new_project_edit.text().strip()
        return selected

    def get_agent_name(self) -> str:
        """Get the entered agent name.

        Returns
        -------
        str
            The agent name text.
        """
        return self.agent_name_edit.text().strip()

    def get_request(self) -> str:
        """Get the entered request text with project prefix if selected.

        If a project is selected, the request text is prefixed with
        "Project: [project_name]" on a separate line.

        Returns
        -------
        str
            The request text, possibly prefixed with project.
        """
        request_text = self.request_edit.toPlainText().strip()
        project = self.get_project()

        if project:
            return f"Project: {project}\n{request_text}"
        return request_text

    def get_raw_request(self) -> str:
        """Get the entered request text without project prefix.

        Returns
        -------
        str
            The raw request text as entered by the user.
        """
        return self.request_edit.toPlainText().strip()

    def get_reason(self) -> str:
        """Get the entered reason for request.

        Returns
        -------
        str
            The reason text.
        """
        return self.reason_edit.toPlainText().strip()
