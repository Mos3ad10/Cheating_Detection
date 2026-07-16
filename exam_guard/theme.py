APP_STYLESHEET = r"""
QWidget {
    color: #18211e;
    background: #f1f4f2;
    font-family: "Segoe UI Variable Text", "Segoe UI";
    font-size: 10pt;
}

QMainWindow, QDialog {
    background: #f1f4f2;
}

QFrame#Header {
    background: #ffffff;
    border-bottom: 1px solid #d8dfdb;
}

QLabel#Brand {
    color: #113f42;
    font-family: "Segoe UI Variable Display", "Segoe UI";
    font-size: 18pt;
    font-weight: 700;
}

QLabel#BrandAccent {
    color: #167c80;
    font-family: "Cascadia Mono", "Consolas";
    font-size: 8pt;
    font-weight: 700;
}

QLabel#StateBadge {
    background: #e8eeeb;
    color: #43514c;
    border: 1px solid #ced8d2;
    border-radius: 4px;
    padding: 5px 9px;
    font-family: "Cascadia Mono", "Consolas";
    font-size: 8pt;
    font-weight: 700;
}

QLabel#StateBadge[state="live"] {
    background: #dff3e7;
    color: #206b45;
    border-color: #acd7bd;
}

QLabel#StateBadge[state="alert"] {
    background: #f9e2e2;
    color: #9d3030;
    border-color: #e8b0b0;
}

QPushButton, QComboBox, QDoubleSpinBox, QSpinBox {
    min-height: 32px;
    background: #ffffff;
    border: 1px solid #c9d3cd;
    border-radius: 5px;
    padding: 0 10px;
}

QPushButton:hover, QComboBox:hover, QDoubleSpinBox:hover, QSpinBox:hover {
    border-color: #167c80;
}

QPushButton:pressed {
    background: #e5eeea;
}

QPushButton:disabled {
    color: #98a39e;
    background: #edf0ee;
    border-color: #dce2de;
}

QPushButton[primary="true"] {
    color: #ffffff;
    background: #167c80;
    border-color: #12696c;
    font-weight: 600;
}

QPushButton[primary="true"]:hover {
    background: #116d71;
}

QPushButton[destructive="true"] {
    color: #a53636;
    background: #fffafa;
    border-color: #e0bcbc;
}

QToolButton {
    width: 34px;
    height: 34px;
    background: #ffffff;
    border: 1px solid #c9d3cd;
    border-radius: 5px;
}

QToolButton:hover {
    border-color: #167c80;
    background: #edf5f3;
}

QFrame#MetricStrip, QFrame#SideRail, QFrame#VideoShell {
    background: #ffffff;
    border: 1px solid #d7dfda;
    border-radius: 6px;
}

QLabel#MetricLabel {
    color: #6e7b75;
    font-family: "Cascadia Mono", "Consolas";
    font-size: 8pt;
    font-weight: 600;
}

QLabel#MetricValue {
    color: #18211e;
    font-family: "Segoe UI Variable Display", "Segoe UI";
    font-size: 15pt;
    font-weight: 700;
}

QLabel#VideoView {
    color: #afbbb5;
    background: #111815;
    border: 0;
    font-size: 11pt;
}

QTabWidget::pane {
    border: 0;
    border-top: 1px solid #d9e0dc;
    background: #ffffff;
}

QTabBar::tab {
    color: #69766f;
    background: #ffffff;
    padding: 10px 14px;
    border: 0;
    border-bottom: 3px solid transparent;
}

QTabBar::tab:selected {
    color: #125f62;
    border-bottom-color: #167c80;
    font-weight: 600;
}

QTableWidget {
    background: #ffffff;
    alternate-background-color: #f6f8f7;
    border: 0;
    gridline-color: #e6ebe8;
    selection-background-color: #dcefed;
    selection-color: #18211e;
}

QHeaderView::section {
    color: #68766f;
    background: #f5f7f6;
    border: 0;
    border-bottom: 1px solid #dce3df;
    padding: 7px 5px;
    font-family: "Cascadia Mono", "Consolas";
    font-size: 8pt;
    font-weight: 600;
}

QTableWidget::item {
    padding: 6px 4px;
    border-bottom: 1px solid #edf0ee;
}

QLabel#Policy {
    color: #6c7772;
    font-size: 8pt;
}

QLabel#FooterStatus {
    color: #5f6d66;
    font-family: "Cascadia Mono", "Consolas";
    font-size: 8pt;
}

QFrame#Toast {
    background: #fff7f7;
    border: 1px solid #d98f8f;
    border-left: 5px solid #c94747;
    border-radius: 6px;
}

QLabel#ToastTitle {
    color: #922d2d;
    background: transparent;
    font-size: 11pt;
    font-weight: 700;
}

QLabel#ToastBody {
    color: #5f3434;
    background: transparent;
}

QGroupBox {
    margin-top: 12px;
    padding-top: 12px;
    border: 1px solid #d7dfda;
    border-radius: 6px;
    font-weight: 600;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}
"""
