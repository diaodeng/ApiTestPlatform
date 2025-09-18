
from view_contents.content_home import Home
from view_contents.content_settings import Settings
from view_contents.content_shortcut import Shortcut
from view_contents.content_about import About
from view_contents.content_fileSearch import FileSearcher
from view_contents.content_goods import Goods


class Contents(object):
    def __init__(self, ft, log, page, **kwargs):
        self.ft = ft
        self.log = log
        self.page = page

        self.home = Home(ft, page, log, **kwargs).home()
        self.settings = Settings(ft, page, log).settings()
        self.shortcut = Shortcut(ft, page, log).shortcut()
        self.about = About(ft).about()
        self.fileSearcher = FileSearcher(ft, page).fileSearcher()
        self.goods = Goods(ft, page, log, **kwargs).goods()

    # 内容区域函数
    def get_content(self, index):
        contents = [
            self.home,
            self.shortcut,
            self.settings,
            self.goods,
            self.fileSearcher,
            self.about

        ]
        return contents[index]

