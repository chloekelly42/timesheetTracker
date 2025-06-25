# Required pip installs:
# pip install PyQt6
# pip install pyinstaller

# Usage: 
#   python timesheetTracker.py
# Compile: 
#   pyinstaller --onefile --windowed timesheetTracker.py

import sys
from datetime import datetime, timedelta
import json
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                            QTreeWidget, QTreeWidgetItem, QMessageBox, 
                            QFileDialog, QMenuBar, QMenu, QStyledItemDelegate, 
                            QStyleOptionViewItem, QCheckBox)
from PyQt6.QtCore import Qt, QModelIndex
from PyQt6.QtGui import QPalette, QColor, QFont
import os

class CustomDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        if index.column() == 3:  # Description column
            text = index.data()
            metrics = option.fontMetrics
            width = self.tree.columnWidth(3)  # Get the actual column width
            
            # Calculate height with a smaller width to force earlier wrapping
            effective_width = width * 0.75  # Use slightly smaller width to encourage wrapping
            
            # Calculate required height with word wrap
            height = metrics.boundingRect(0, 0, int(effective_width), 0, 
                                        Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                                        text).height()
            
            # Set minimum height and add padding
            min_height = 30  # Minimum height for consistency
            size.setHeight(max(height + 12, min_height))
        return size

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        option.font = QFont("Arial", 12)
        if index.column() == 3:  # Description column
            option.displayAlignment = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            option.textElideMode = Qt.TextElideMode.ElideNone
            option.features |= QStyleOptionViewItem.ViewItemFeature.WrapText

class TimesheetTracker(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Timesheet Tracker")
        self.setMinimumSize(800, 600)
        
        # Center the window
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(
            (screen.width() - self.width()) // 2,
            (screen.height() - self.height()) // 2,
            800, 600
        )
        
        self.current_file = None
        self.total_time = 0.0
        self.billable_time = 0.0
        self.expected_time_offset = 0.0  # Track lunch and other non-counted time
        self.project_groups = {}  # Track time by project first letter
        
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Create menu bar
        self.create_menu()
        
        # Create input area
        input_layout = QHBoxLayout()
        
        # Time input and billable checkbox
        time_label = QLabel("Hours:")
        self.time_input = QLineEdit()
        self.time_input.setFixedWidth(100)
        self.time_input.setPlaceholderText("0.0")
        
        self.billable_label = QLabel("B:")
        self.billable_checkbox = QCheckBox()
        self.billable_checkbox.setChecked(False)

        # Project input
        project_label = QLabel("Project:")
        self.project_input = QLineEdit()
        self.project_input.setFixedWidth(60)
        self.project_input.setPlaceholderText("kdg")
        
        # Description input
        desc_label = QLabel("Description:")
        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("wrote code and cried")
        
        # Buttons
        self.add_button = QPushButton("Add Entry")
        self.edit_button = QPushButton("Edit")
        self.delete_button = QPushButton("Delete")
        
        # Add widgets to input layout
        input_layout.addWidget(time_label)
        input_layout.addWidget(self.time_input)                
        input_layout.addWidget(self.billable_label)
        input_layout.addWidget(self.billable_checkbox)
        input_layout.addWidget(project_label)
        input_layout.addWidget(self.project_input)
        input_layout.addWidget(desc_label)
        input_layout.addWidget(self.desc_input)
        input_layout.addWidget(self.add_button)
        input_layout.addWidget(self.edit_button)
        input_layout.addWidget(self.delete_button)
        
        # Create tree widget for entries
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Hours", "B", "Project", "Description", "Timestamp"])
        self.tree.setColumnWidth(0, 60)
        self.tree.setColumnWidth(1, 30)
        self.tree.setColumnWidth(2, 100)
        self.tree.setColumnWidth(3, 450)
        self.tree.setColumnWidth(4, 80)
                
        # Enable sorting
        self.tree.setSortingEnabled(True)
        self.tree.header().setSectionsClickable(True)
        
        # Sort by project column initially
        self.tree.sortByColumn(2, Qt.SortOrder.AscendingOrder)

        # Set custom delegate for larger text in cells
        delegate = CustomDelegate()
        delegate.tree = self.tree  # Give delegate access to tree widget
        self.tree.setItemDelegate(delegate)
        
        # Enable word wrap
        self.tree.setWordWrap(True)
        
        # Disable full row selection
        self.tree.setSelectionBehavior(QTreeWidget.SelectionBehavior.SelectItems)
        
        # Create status layout for total time and expected time
        status_layout = QHBoxLayout()
        
        # Create status area with vertical layout
        status_area = QVBoxLayout()
        
        # Create total time label
        self.total_label = QLabel(f"Total Time: 0.0 hours (Billable: 0.0 hours)")
        
        # Create project groups label
        self.project_groups_label = QLabel("")
        
        # Add labels to status area
        status_area.addWidget(self.total_label)
        status_area.addWidget(self.project_groups_label)
        
        # Create expected time label (assuming 8:00 AM start)
        self.expected_time_label = QLabel("Expected Time: 8:00 AM")
        
        # Add widgets to status layout
        status_layout.addLayout(status_area)
        status_layout.addStretch()
        status_layout.addWidget(self.expected_time_label)
        
        # Add all widgets to main layout
        layout.addLayout(input_layout)
        layout.addWidget(self.tree)
        layout.addLayout(status_layout)
        
        # Connect signals
        self.add_button.clicked.connect(self.add_entry)
        self.edit_button.clicked.connect(self.edit_entry)
        self.delete_button.clicked.connect(self.delete_entry)
        self.tree.itemDoubleClicked.connect(self.edit_entry)
    
    def create_menu(self):
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        new_action = file_menu.addAction("New")
        new_action.triggered.connect(self.new_timesheet)
        
        open_action = file_menu.addAction("Open")
        open_action.triggered.connect(self.load_timesheet)
        
        save_action = file_menu.addAction("Save")
        save_action.triggered.connect(self.save_timesheet)
        
        save_as_action = file_menu.addAction("Save As")
        save_as_action.triggered.connect(self.save_as_timesheet)
        
        file_menu.addSeparator()
        
        exit_action = file_menu.addAction("Exit")
        exit_action.triggered.connect(self.close)

    def new_timesheet(self):
        if self.tree.topLevelItemCount() > 0:
            reply = QMessageBox.question(self, "Confirm", 
                "There are unsaved changes. Are you sure you want to discard them?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return
                
        self.tree.clear()
        self.total_time = 0.0
        self.billable_time = 0.0
        self.expected_time_offset = 0.0
        self.project_groups = {}
        self.update_total()
        self.current_file = None

    def load_timesheet(self):
        if self.tree.topLevelItemCount() > 0:
            reply = QMessageBox.question(self, "Confirm", 
                "There are unsaved changes. Are you sure you want to discard them?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return
                
        filename, _ = QFileDialog.getOpenFileName(
            self, "Open Timesheet", "", "JSON Files (*.json);;All Files (*)"
        )
        
        if filename:
            try:
                with open(filename, 'r') as f:
                    data = json.load(f)
                self.tree.clear()
                self.total_time = 0.0
                self.billable_time = 0.0
                self.expected_time_offset = 0.0
                self.current_file = filename
                
                for entry in data['entries']:
                    billable_text = "X" if entry.get('billable', True) else ""
                    item = QTreeWidgetItem([
                        str(entry['time']),
                        billable_text,
                        entry['project'],
                        entry['description'],
                        entry['timestamp']
                    ])
                    self.tree.addTopLevelItem(item)
                    
                    # Special handling for "Lunch" project
                    if entry['project'].lower() == "lunch":
                        self.expected_time_offset += float(entry['time'])
                    else:
                        self.total_time += float(entry['time'])
                        if entry.get('billable', True):
                            self.billable_time += float(entry['time'])
                
                self.update_total()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load file: {str(e)}")

    def save_timesheet(self):
        if not self.current_file:
            self.save_as_timesheet()
        else:
            self.save_to_file(self.current_file)

    def save_as_timesheet(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Timesheet", "", "JSON Files (*.json);;All Files (*)"
        )
        
        if filename:
            self.save_to_file(filename)
            self.current_file = filename

    def save_to_file(self, filename):
        entries = []
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            entries.append({
                'time': float(item.text(0)),
                'project': item.text(2),
                'description': item.text(3),
                'timestamp': item.text(4),
                'billable': item.text(1) == "X"
            })
        
        data = {
            'entries': entries,
            'total_time': self.total_time,
            'billable_time': self.billable_time,
            'expected_time_offset': self.expected_time_offset
        }
        
        try:
            with open(filename, 'w') as f:
                json.dump(data, f, indent=4)
            QMessageBox.information(self, "Success", "Timesheet saved successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save file: {str(e)}")

    def edit_entry(self):
        current_item = self.tree.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Warning", "Please select an entry to edit")
            return
        
        time = float(current_item.text(0))
        project = current_item.text(2)
        
        # Remove time from appropriate counter
        if project.lower() == "lunch":
            self.expected_time_offset -= time
        else:
            self.total_time -= time
            if current_item.text(1) == "X":
                self.billable_time -= time
            
        self.time_input.setText(current_item.text(0))
        self.project_input.setText(current_item.text(2))
        self.desc_input.setText(current_item.text(3))
        self.billable_checkbox.setChecked(current_item.text(1) == "X")
        
        self.tree.takeTopLevelItem(self.tree.indexOfTopLevelItem(current_item))
        self.update_total()

    def delete_entry(self):
        current_item = self.tree.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Warning", "Please select an entry to delete")
            return
        
        reply = QMessageBox.question(self, "Confirm", 
            "Are you sure you want to delete this entry?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            
        if reply == QMessageBox.StandardButton.Yes:
            time = float(current_item.text(0))
            project = current_item.text(2)
            
            # Remove time from appropriate counter
            if project.lower() == "lunch":
                self.expected_time_offset -= time
            else:
                self.total_time -= time
                if current_item.text(1) == "X":
                    self.billable_time -= time
                    
            self.tree.takeTopLevelItem(self.tree.indexOfTopLevelItem(current_item))
            self.update_total()

    def update_total(self):
        # Update project groups first so we can include them in the total label
        self.update_project_groups()
        
        # Format project groups text for inclusion in total label
        project_groups_text = ""
        if self.project_groups:
            sorted_groups = sorted(self.project_groups.items())
            project_groups_text = f" [{', '.join([f'{letter}: {hours:.1f}h' for letter, hours in sorted_groups])}]"
        
        # Update total label with project groups included
        self.total_label.setText(f"Total Time: {self.total_time:.1f} hours (Billable: {self.billable_time:.1f} hours){project_groups_text}")
        
        # Calculate expected time (8:00 AM + total hours + expected_time_offset)
        start_time = datetime.strptime("8:00 AM", "%I:%M %p")
        total_expected_hours = self.total_time + self.expected_time_offset
        hours = int(total_expected_hours)
        minutes = int((total_expected_hours - hours) * 60)
        expected_time = start_time + timedelta(hours=hours, minutes=minutes)
        expected_time_str = expected_time.strftime("%I:%M %p")
        
        self.expected_time_label.setText(f"Expected Time: {expected_time_str}")
    
    def update_project_groups(self):
        # Reset project groups
        self.project_groups = {}
        
        # Iterate through all entries
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            time = float(item.text(0))
            project = item.text(2)
            billable = item.text(1) == "X"
            
            # Skip lunch entries and non-billable entries
            if project.lower() == "lunch" or not billable:
                continue
                
            # Get first letter of project (or use "?" if empty)
            first_letter = project[0].upper() if project else "?"
            
            # Add time to the appropriate group
            if first_letter in self.project_groups:
                self.project_groups[first_letter] += time
            else:
                self.project_groups[first_letter] = time
                
        # Clear the project_groups_label as we're now showing this info in the total_label
        self.project_groups_label.setText("")
            
    def add_entry(self):
        try:
            time = float(self.time_input.text())
            if not round(time * 10) % 1 == 0:
                raise ValueError("Time must be in increments of 0.1 hours")
            
            project = self.project_input.text()
            if not project:  # If project is empty
                project = "kdg"
                
            description = self.desc_input.text()
            timestamp = datetime.now().strftime("%I:%M:%S %p")
            
            billable = "X" if self.billable_checkbox.isChecked() else ""
            item = QTreeWidgetItem([str(time), billable, project, description, timestamp])
            # Make all columns sortable by setting text alignment
            for i in range(5):
                item.setTextAlignment(i, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self.tree.addTopLevelItem(item)
            
            # Force the tree to recalculate row heights
            row = self.tree.indexOfTopLevelItem(item)
            self.tree.updateGeometries()
            
            # Special handling for "Lunch" project
            if project.lower() == "lunch":
                self.expected_time_offset += time
            else:
                self.total_time += time
                if self.billable_checkbox.isChecked():
                    self.billable_time += time
            
            self.update_total()
            
            self.time_input.clear()
            self.project_input.clear()
            self.desc_input.clear()
            self.billable_checkbox.setChecked(False)
            
        except ValueError as e:
            QMessageBox.critical(self, "Error", str(e))

def main():
    app = QApplication(sys.argv)
    
    # Set the style to "Fusion"
    app.setStyle("Fusion")
    
    # Set up the dark theme palette
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(25, 25, 25))
    palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(35, 35, 35))
    
    # Apply the palette
    app.setPalette(palette)
    
    window = TimesheetTracker()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()