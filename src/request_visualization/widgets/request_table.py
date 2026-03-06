# Table widget for displaying agent requests.
# Supports interactive buttons for status transitions based on current request status:
# - pending: Approve, Reject buttons
# - implemented: Complete, Revise, Cancel buttons
# For terminal states (completed, cancelled, rejected), buttons are cleared.

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QMenu,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from ..models import AgentRequest


class RequestTableWidget(QTableWidget):
    """Table widget for displaying and interacting with agent requests."""

    # Signals for pending requests
    approve_clicked = pyqtSignal(int)  # Emits request ID
    reject_clicked = pyqtSignal(int)  # Emits request ID

    # Signals for implemented requests
    complete_clicked = pyqtSignal(int)  # Emits request ID
    revise_clicked = pyqtSignal(int)  # Emits request ID
    cancel_clicked = pyqtSignal(int)  # Emits request ID

    # Signal for status change via context menu (request_id, new_status)
    status_change_requested = pyqtSignal(int, str)

    row_double_clicked = pyqtSignal(int)  # Emits request ID

    COLUMNS = ["ID", "Agent", "Created", "Request", "Reason", "Status", "Assigned", "Actions"]

    def __init__(self, parent=None):
        """Initialize the request table widget.

        Parameters
        ----------
        parent : QWidget, optional
            Parent widget.
        """
        super().__init__(parent)
        self._requests: list[AgentRequest] = []

        self.setColumnCount(len(self.COLUMNS))
        self.setHorizontalHeaderLabels(self.COLUMNS)

        # Configure table behavior
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)

        # Configure column sizing
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # ID
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Agent
        header.setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )  # Created
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)  # Request
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)  # Reason
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # Status
        header.setSectionResizeMode(
            6, QHeaderView.ResizeMode.ResizeToContents
        )  # Assigned
        header.setSectionResizeMode(
            7, QHeaderView.ResizeMode.ResizeToContents
        )  # Actions

        self.cellDoubleClicked.connect(self._on_cell_double_clicked)

        # Enable context menu for status column
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)

    def set_requests(self, requests: list[AgentRequest]) -> None:
        """Populate the table with requests.

        Parameters
        ----------
        requests : list[AgentRequest]
            List of requests to display.
        """
        self._requests = requests
        self.setRowCount(len(requests))

        for row, req in enumerate(requests):
            self._populate_row(row, req)

    def _populate_row(self, row: int, request: AgentRequest) -> None:
        """Populate a single row with request data.

        Parameters
        ----------
        row : int
            Row index.
        request : AgentRequest
            Request data to display.
        """
        # ID
        id_item = QTableWidgetItem(str(request.id))
        id_item.setData(Qt.ItemDataRole.UserRole, request.id)
        self.setItem(row, 0, id_item)

        # Agent
        self.setItem(row, 1, QTableWidgetItem(request.agent_name))

        # Created
        created_str = request.creation_time.strftime("%Y-%m-%d %H:%M")
        self.setItem(row, 2, QTableWidgetItem(created_str))

        # Request (truncated)
        request_text = request.request
        if len(request_text) > 80:
            request_text = request_text[:77] + "..."
        self.setItem(row, 3, QTableWidgetItem(request_text))

        # Reason (truncated)
        reason_text = request.reason_for_request or ""
        if len(reason_text) > 50:
            reason_text = reason_text[:47] + "..."
        self.setItem(row, 4, QTableWidgetItem(reason_text))

        # Status with color coding
        status_item = QTableWidgetItem(request.request_status)
        status_item.setForeground(self._get_status_color(request.request_status))
        self.setItem(row, 5, status_item)

        # Assigned time
        if request.assigned_time:
            assigned_str = request.assigned_time.strftime("%Y-%m-%d %H:%M")
        else:
            assigned_str = ""
        self.setItem(row, 6, QTableWidgetItem(assigned_str))

        # Actions (buttons based on status)
        if request.request_status == "pending":
            self._add_pending_actions(row, request.id)
        elif request.request_status == "implemented":
            self._add_implemented_actions(row, request.id)
        else:
            # Clear any existing cell widget for terminal states (completed, cancelled, rejected)
            # or other statuses that don't have actions
            self._clear_actions(row)

    def _get_status_color(self, status: str) -> Qt.GlobalColor:
        """Get the color for a status.

        Parameters
        ----------
        status : str
            The request status.

        Returns
        -------
        Qt.GlobalColor
            The color to use for the status text.
        """
        status_colors = {
            "pending": Qt.GlobalColor.darkYellow,
            "approved": Qt.GlobalColor.darkGreen,
            "rejected": Qt.GlobalColor.darkRed,
            "implemented": Qt.GlobalColor.darkBlue,
            "completed": Qt.GlobalColor.darkCyan,
            "cancelled": Qt.GlobalColor.darkMagenta,
        }
        return status_colors.get(status, Qt.GlobalColor.black)

    def _clear_actions(self, row: int) -> None:
        """Clear the actions cell for a row.

        Removes any cell widget (buttons) and sets an empty item.
        This is used for terminal states like completed or cancelled.

        Parameters
        ----------
        row : int
            Row index.
        """
        # Remove any existing cell widget (buttons) first
        self.removeCellWidget(row, 7)
        # Set an empty item
        self.setItem(row, 7, QTableWidgetItem(""))

    def _add_pending_actions(self, row: int, request_id: int) -> None:
        """Add action buttons for pending requests.

        Parameters
        ----------
        row : int
            Row index.
        request_id : int
            ID of the request.
        """
        actions_widget = QWidget()
        layout = QHBoxLayout(actions_widget)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)

        approve_btn = QPushButton("Approve")
        approve_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        approve_btn.clicked.connect(lambda _, rid=request_id: self._on_approve(rid))

        reject_btn = QPushButton("Reject")
        reject_btn.setStyleSheet("background-color: #f44336; color: white;")
        reject_btn.clicked.connect(lambda _, rid=request_id: self._on_reject(rid))

        layout.addWidget(approve_btn)
        layout.addWidget(reject_btn)

        self.setCellWidget(row, 7, actions_widget)

    def _add_implemented_actions(self, row: int, request_id: int) -> None:
        """Add action buttons for implemented requests.

        Provides three options:
        - Complete: Mark the implementation as verified and accepted
        - Revise: Edit the request and queue for re-implementation
        - Cancel: Cancel the request

        Parameters
        ----------
        row : int
            Row index.
        request_id : int
            ID of the request.
        """
        actions_widget = QWidget()
        layout = QHBoxLayout(actions_widget)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)

        complete_btn = QPushButton("Complete")
        complete_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        complete_btn.clicked.connect(lambda _, rid=request_id: self._on_complete(rid))

        revise_btn = QPushButton("Revise")
        revise_btn.setStyleSheet("background-color: #FF9800; color: white;")
        revise_btn.clicked.connect(lambda _, rid=request_id: self._on_revise(rid))

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("background-color: #9E9E9E; color: white;")
        cancel_btn.clicked.connect(lambda _, rid=request_id: self._on_cancel(rid))

        layout.addWidget(complete_btn)
        layout.addWidget(revise_btn)
        layout.addWidget(cancel_btn)

        self.setCellWidget(row, 7, actions_widget)

    def _on_approve(self, request_id: int) -> None:
        """Handle approve button click.

        Parameters
        ----------
        request_id : int
            ID of the request to approve.
        """
        self.approve_clicked.emit(request_id)

    def _on_reject(self, request_id: int) -> None:
        """Handle reject button click.

        Parameters
        ----------
        request_id : int
            ID of the request to reject.
        """
        self.reject_clicked.emit(request_id)

    def _on_complete(self, request_id: int) -> None:
        """Handle complete button click.

        Parameters
        ----------
        request_id : int
            ID of the request to mark as completed.
        """
        self.complete_clicked.emit(request_id)

    def _on_revise(self, request_id: int) -> None:
        """Handle revise button click.

        Parameters
        ----------
        request_id : int
            ID of the request to revise.
        """
        self.revise_clicked.emit(request_id)

    def _on_cancel(self, request_id: int) -> None:
        """Handle cancel button click.

        Parameters
        ----------
        request_id : int
            ID of the request to cancel.
        """
        self.cancel_clicked.emit(request_id)

    def _on_context_menu(self, position) -> None:
        """Handle right-click context menu on the table.

        Shows a status change menu when right-clicking on the Status column.

        Parameters
        ----------
        position : QPoint
            Position where the context menu was requested.
        """
        # Get the item at the clicked position
        item = self.itemAt(position)
        if item is None:
            return

        row = item.row()
        column = item.column()

        # Only show context menu for Status column (index 5)
        if column != 5:
            return

        if row >= len(self._requests):
            return

        request = self._requests[row]
        current_status = request.request_status

        # Define available status transitions
        all_statuses = ["pending", "approved", "rejected", "implemented", "completed", "cancelled"]

        # Create context menu
        menu = QMenu(self)

        for status in all_statuses:
            if status == current_status:
                # Show current status as disabled/checked
                action = QAction(f"✓ {status.capitalize()}", self)
                action.setEnabled(False)
            else:
                action = QAction(status.capitalize(), self)
                action.triggered.connect(
                    lambda checked, s=status, rid=request.id: self._on_status_change(rid, s)
                )
            menu.addAction(action)

        # Show the menu at the cursor position
        menu.exec(self.viewport().mapToGlobal(position))

    def _on_status_change(self, request_id: int, new_status: str) -> None:
        """Handle status change from context menu.

        Parameters
        ----------
        request_id : int
            ID of the request to change.
        new_status : str
            New status to set.
        """
        self.status_change_requested.emit(request_id, new_status)

    def _on_cell_double_clicked(self, row: int, column: int) -> None:
        """Handle cell double-click.

        Parameters
        ----------
        row : int
            Row index.
        column : int
            Column index.
        """
        if row < len(self._requests):
            self.row_double_clicked.emit(self._requests[row].id)

    def get_request_by_id(self, request_id: int) -> AgentRequest | None:
        """Get a request by its ID.

        Parameters
        ----------
        request_id : int
            The request ID to find.

        Returns
        -------
        AgentRequest | None
            The request if found, None otherwise.
        """
        for req in self._requests:
            if req.id == request_id:
                return req
        return None
