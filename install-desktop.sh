#!/bin/bash
# Install desktop integration files for request-viz.
# Run this script after installing the package with pip.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ICON_DIR="${HOME}/.local/share/icons/hicolor/scalable/apps"
DESKTOP_DIR="${HOME}/.local/share/applications"

echo "Installing desktop integration for request-viz..."

# Create directories if they don't exist
mkdir -p "${ICON_DIR}"
mkdir -p "${DESKTOP_DIR}"

# Copy icon
cp "${SCRIPT_DIR}/src/request_visualization/resources/icon.svg" "${ICON_DIR}/request-viz.svg"
echo "Installed icon to ${ICON_DIR}/request-viz.svg"

# Copy desktop file
cp "${SCRIPT_DIR}/request-viz.desktop" "${DESKTOP_DIR}/"
echo "Installed desktop file to ${DESKTOP_DIR}/request-viz.desktop"

# Update icon cache
if command -v gtk-update-icon-cache &> /dev/null; then
    gtk-update-icon-cache -f -t "${HOME}/.local/share/icons/hicolor" 2>/dev/null || true
fi

# Update desktop database
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database "${DESKTOP_DIR}" 2>/dev/null || true
fi

echo "Desktop integration installed successfully!"
echo "You may need to log out and back in for the icon to appear in your application menu."
