# Main application window for the request visualization GUI.
# Manages the display and interaction with agent requests, supporting status
# transitions including pending->approved/rejected and implemented->completed/cancelled/revised.

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import database
from ..models import AgentRequest
from .dialogs import ApproveDialog, NewRequestDialog, RejectDialog, RequestDetailDialog, ReviseDialog
from .request_table import RequestTableWidget


class MainWindow(QMainWindow):
    """Main application window for managing agent requests."""

    def __init__(self, db_path: Path = database.DEFAULT_DB_PATH):
        """Initialize the main window.

        Parameters
        ----------
        db_path : Path
            Path to the SQLite database file.
        """
        super().__init__()
        self.db_path = db_path

        self.setWindowTitle("Agent Request Visualization")
        self.setMinimumSize(1000, 600)

        self._setup_ui()
        self._setup_menu()
        self._connect_signals()

        # Ensure table exists and load initial data
        database.ensure_table_exists(self.db_path)
        self._refresh_data()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        # Filter bar
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Status Filter:"))

        self.status_filter = QComboBox()
        self.status_filter.addItems([
            "All",
            "Active",
            "Pending",
            "Approved",
            "Rejected",
            "In Progress",
            "Implemented",
            "Completed",
            "Cancelled",
        ])
        self.status_filter.setCurrentIndex(1)  # Default to "Active"
        filter_layout.addWidget(self.status_filter)

        filter_layout.addStretch()

        # New request button
        self.new_button = QPushButton("New")
        self.new_button.setStyleSheet("background-color: #2196F3; color: white;")
        filter_layout.addWidget(self.new_button)

        layout.addLayout(filter_layout)

        # Request table
        self.request_table = RequestTableWidget()
        layout.addWidget(self.request_table)

        # Status bar
        self.statusBar().showMessage("Ready")

    def _setup_menu(self) -> None:
        """Set up the menu bar."""
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("&File")

        refresh_action = QAction("&Refresh", self)
        refresh_action.setShortcut(QKeySequence.StandardKey.Refresh)
        refresh_action.triggered.connect(self._refresh_data)
        file_menu.addAction(refresh_action)

        file_menu.addSeparator()

        quit_action = QAction("&Quit", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # View menu
        view_menu = menu_bar.addMenu("&View")

        active_action = QAction("Show A&ctive", self)
        active_action.triggered.connect(lambda: self._set_filter("Active"))
        view_menu.addAction(active_action)

        pending_action = QAction("Show &Pending", self)
        pending_action.triggered.connect(lambda: self._set_filter("Pending"))
        view_menu.addAction(pending_action)

        implemented_action = QAction("Show &Implemented", self)
        implemented_action.triggered.connect(lambda: self._set_filter("Implemented"))
        view_menu.addAction(implemented_action)

        all_action = QAction("Show &All", self)
        all_action.triggered.connect(lambda: self._set_filter("All"))
        view_menu.addAction(all_action)

    def _connect_signals(self) -> None:
        """Connect widget signals to handlers."""
        self.status_filter.currentTextChanged.connect(self._on_filter_changed)

        # Pending request actions
        self.request_table.approve_clicked.connect(self._on_approve)
        self.request_table.reject_clicked.connect(self._on_reject)

        # Implemented request actions
        self.request_table.complete_clicked.connect(self._on_complete)
        self.request_table.revise_clicked.connect(self._on_revise)
        self.request_table.cancel_clicked.connect(self._on_cancel)

        # Context menu status change
        self.request_table.status_change_requested.connect(self._on_status_change)

        # Other actions
        self.request_table.row_double_clicked.connect(self._on_show_details)
        self.new_button.clicked.connect(self._on_new_request)

    def _set_filter(self, filter_text: str) -> None:
        """Set the status filter dropdown.

        Parameters
        ----------
        filter_text : str
            Filter value to set.
        """
        index = self.status_filter.findText(filter_text)
        if index >= 0:
            self.status_filter.setCurrentIndex(index)

    def _on_filter_changed(self, text: str) -> None:
        """Handle status filter change.

        Parameters
        ----------
        text : str
            New filter value.
        """
        self._refresh_data()

    def _refresh_data(self) -> None:
        """Refresh the request data from the database."""
        filter_text = self.status_filter.currentText()

        if filter_text == "All":
            requests = database.get_all_requests(self.db_path)
            self.request_table.set_requests(requests)
            pending_count = sum(1 for r in requests if r.request_status == "pending")
            implemented_count = sum(1 for r in requests if r.request_status == "implemented")
            self.statusBar().showMessage(
                f"Showing {len(requests)} request(s) "
                f"({pending_count} pending, {implemented_count} implemented)"
            )
        elif filter_text == "Active":
            requests = database.get_active_requests(self.db_path)
            self.request_table.set_requests(requests)
            self.statusBar().showMessage(
                f"Showing {len(requests)} active request(s)"
            )
        else:
            # Handle "In Progress" -> "in_progress" conversion
            status_filter = filter_text.lower().replace(" ", "_")
            requests = database.get_all_requests(self.db_path, status_filter)
            self.request_table.set_requests(requests)
            self.statusBar().showMessage(
                f"Showing {len(requests)} {filter_text.lower()} request(s)"
            )

    def _on_approve(self, request_id: int) -> None:
        """Handle approve action for a request.

        Parameters
        ----------
        request_id : int
            ID of the request to approve.
        """
        request = self.request_table.get_request_by_id(request_id)
        if not request:
            return

        # Show approval dialog
        dialog = ApproveDialog(self)
        if dialog.exec() != ApproveDialog.DialogCode.Accepted:
            return

        reason = dialog.get_reason() or None

        # Update database
        if database.approve_request(request_id, reason, self.db_path):
            QMessageBox.information(
                self,
                "Request Approved",
                f"Request #{request_id} has been approved.",
            )
        else:
            QMessageBox.warning(
                self, "Error", f"Failed to approve request #{request_id}"
            )

        self._refresh_data()

    def _on_reject(self, request_id: int) -> None:
        """Handle reject action for a request.

        Parameters
        ----------
        request_id : int
            ID of the request to reject.
        """
        dialog = RejectDialog(self)
        if dialog.exec() != RejectDialog.DialogCode.Accepted:
            return

        reason = dialog.get_reason()
        if not reason:
            QMessageBox.warning(
                self, "Error", "A rejection reason is required."
            )
            return

        if database.reject_request(request_id, reason, self.db_path):
            QMessageBox.information(
                self, "Request Rejected", f"Request #{request_id} has been rejected."
            )
        else:
            QMessageBox.warning(
                self, "Error", f"Failed to reject request #{request_id}"
            )

        self._refresh_data()

    def _on_complete(self, request_id: int) -> None:
        """Handle complete action for an implemented request.

        Parameters
        ----------
        request_id : int
            ID of the request to mark as completed.
        """
        reply = QMessageBox.question(
            self,
            "Complete Request",
            f"Mark request #{request_id} as completed?\n\n"
            "This confirms the implementation has been verified and accepted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        if database.complete_request(request_id, db_path=self.db_path):
            QMessageBox.information(
                self,
                "Request Completed",
                f"Request #{request_id} has been marked as completed.",
            )
        else:
            QMessageBox.warning(
                self, "Error", f"Failed to complete request #{request_id}"
            )

        self._refresh_data()

    def _on_revise(self, request_id: int) -> None:
        """Handle revise action for an implemented request.

        Opens a dialog to edit the request text. On save, the request is
        updated and its status is set back to 'approved' for re-implementation.

        Parameters
        ----------
        request_id : int
            ID of the request to revise.
        """
        request = database.get_request_by_id(request_id, self.db_path)
        if not request:
            QMessageBox.warning(
                self, "Error", f"Request #{request_id} not found."
            )
            return

        dialog = ReviseDialog(request.request, self)
        if dialog.exec() != ReviseDialog.DialogCode.Accepted:
            return

        new_text = dialog.get_revised_text()
        if not new_text:
            QMessageBox.warning(
                self, "Error", "Request text cannot be empty."
            )
            return

        # Show working status
        self.statusBar().showMessage("Revising request and generating embedding...")

        try:
            if database.revise_request(request_id, new_text, self.db_path):
                QMessageBox.information(
                    self,
                    "Request Revised",
                    f"Request #{request_id} has been revised and set to 'approved' "
                    "for re-implementation.",
                )
            else:
                QMessageBox.warning(
                    self, "Error", f"Failed to revise request #{request_id}"
                )
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to revise request: {e}"
            )

        self._refresh_data()

    def _on_cancel(self, request_id: int) -> None:
        """Handle cancel action for an implemented request.

        Parameters
        ----------
        request_id : int
            ID of the request to cancel.
        """
        reply = QMessageBox.question(
            self,
            "Cancel Request",
            f"Cancel request #{request_id}?\n\n"
            "This will mark the request as cancelled.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        if database.cancel_request(request_id, db_path=self.db_path):
            QMessageBox.information(
                self,
                "Request Cancelled",
                f"Request #{request_id} has been cancelled.",
            )
        else:
            QMessageBox.warning(
                self, "Error", f"Failed to cancel request #{request_id}"
            )

        self._refresh_data()

    def _on_status_change(self, request_id: int, new_status: str) -> None:
        """Handle status change from context menu.

        Parameters
        ----------
        request_id : int
            ID of the request to change.
        new_status : str
            New status to set.
        """
        request = database.get_request_by_id(request_id, self.db_path)
        if not request:
            QMessageBox.warning(
                self, "Error", f"Request #{request_id} not found."
            )
            return

        # Confirm the status change
        reply = QMessageBox.question(
            self,
            "Change Status",
            f"Change request #{request_id} status from "
            f"'{request.request_status}' to '{new_status}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        if database.set_request_status(request_id, new_status, db_path=self.db_path):
            QMessageBox.information(
                self,
                "Status Changed",
                f"Request #{request_id} status changed to '{new_status}'.",
            )
        else:
            QMessageBox.warning(
                self, "Error", f"Failed to change status for request #{request_id}"
            )

        self._refresh_data()

    def _on_show_details(self, request_id: int) -> None:
        """Show request details dialog.

        Parameters
        ----------
        request_id : int
            ID of the request to show.
        """
        request = database.get_request_by_id(request_id, self.db_path)
        if request:
            dialog = RequestDetailDialog(request, self)
            dialog.exec()

    def _on_new_request(self) -> None:
        """Handle new request button click."""
        dialog = NewRequestDialog(self)
        if dialog.exec() != NewRequestDialog.DialogCode.Accepted:
            return

        agent_name = dialog.get_agent_name()
        request_text = dialog.get_request()
        reason = dialog.get_reason() or None

        if not agent_name:
            QMessageBox.warning(self, "Error", "Agent name is required.")
            return

        if not request_text:
            QMessageBox.warning(self, "Error", "Request text is required.")
            return

        # Update status bar to show we're working
        self.statusBar().showMessage("Creating request and generating embedding...")

        try:
            request_id = database.create_request(
                agent_name=agent_name,
                request=request_text,
                reason_for_request=reason,
                db_path=self.db_path,
            )
            if request_id:
                QMessageBox.information(
                    self,
                    "Request Created",
                    f"Request #{request_id} has been created.",
                )
            else:
                QMessageBox.warning(self, "Error", "Failed to create request.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create request: {e}")

        self._refresh_data()
