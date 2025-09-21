from flet import SnackBar, Text, Colors


class UiUtil:
    @staticmethod
    def show_snackbar(page, msg: str, action: str = "知道了"):
        page.open(SnackBar(
            content=Text(msg),
            action=action,
        ))
        page.update()

    @staticmethod
    def show_snackbar_error(page, msg: str, action: str = "知道了"):
        page.open(SnackBar(
            bgcolor=Colors.RED,
            content=Text(msg),
            action=action,
        ))
        page.update()

    @staticmethod
    def show_snackbar_success(page, msg: str, action: str = "知道了"):
        page.open(SnackBar(
            bgcolor=Colors.GREEN,
            content=Text(msg),
            action=action,
        ))
        page.update()
