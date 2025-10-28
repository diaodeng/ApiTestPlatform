
from view_contents.content_home import Home
from view_contents.content_settings import Settings
from view_contents.content_about import About


class Contents(object):
    def __init__(self, ft, log, page, **kwargs):
        self.ft = ft
        self.log = log
        self.page = page

        self.home = Home(ft, page, log, **kwargs).home()
        self.settings = Settings(ft, page, log).settings()
        self.about = About(ft).about()

    # 内容区域函数
    def get_content(self, index):
        contents = [
            self.home,
            self.settings,
            self.about

        ]
        return contents[index]

