from PySide6.QtWidgets import QMessageBox

from ..utils.dialog_util import DialogUtil


class DialogService:
    def __init__(self, parent):
        self.parent = parent

    def confirm(self, title, msg):
        return DialogUtil.confirm(self.parent, title, msg)

    def choice(self, title, msg):
        return DialogUtil.choice(self.parent, title, msg)

    def error(self, msg):
        QMessageBox.critical(self.parent, "错误", msg)

    def success(self, msg):
        QMessageBox.information(self.parent, "成功", msg)
