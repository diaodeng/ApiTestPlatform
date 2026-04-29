from PySide6.QtWidgets import QMessageBox


class DialogUtil:
    @staticmethod
    def confirm(parent, title, content) -> bool:
        reply = QMessageBox.question(
            parent, title, content, QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        return reply == QMessageBox.Yes

    @staticmethod
    def choice(parent, title, content) -> int:
        msg = QMessageBox(parent)
        msg.setWindowTitle(title)
        msg.setText(content)

        btn_cancel = msg.addButton("取消", QMessageBox.RejectRole)
        btn_ok = msg.addButton("确定", QMessageBox.AcceptRole)
        btn_switch = msg.addButton("切换后启动", QMessageBox.ActionRole)

        msg.exec()

        if msg.clickedButton() == btn_cancel:
            return 0
        elif msg.clickedButton() == btn_ok:
            return 1
        elif msg.clickedButton() == btn_switch:
            return 2

        return 0
