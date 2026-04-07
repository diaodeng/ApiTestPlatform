from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from model.config import SqliteFavoriteSqlModel
from ui.utils.icon_util import apply_window_icon
from ui.widgets.searchable_combo_box import SearchableComboBox


class SqliteFavoriteSqlDialog(QDialog):
    TABLE_KEY_SEPARATOR = "\u241f"

    def __init__(
        self,
        favorites: list[SqliteFavoriteSqlModel],
        current_database_path: str,
        current_table_name: str,
        current_sql: str,
        parent=None,
    ):
        super().__init__(parent)
        self._favorites = list(favorites or [])
        self.current_database_path = current_database_path or ""
        self.current_table_name = current_table_name or ""
        self._page_sql_text = current_sql or ""
        self.loaded_sql = ""
        self.status_message = ""

        self.setWindowTitle("常用 SQL 管理")
        self.resize(860, 620)
        apply_window_icon(self)

        self._init_ui()
        self.sql_editor.setPlainText(self._page_sql_text)
        self._refresh_scope_options()
        self._refresh_list()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        context_text = (
            f"当前数据库：{self.current_database_path or '-'} | 当前表：{self.current_table_name or '-'}"
        )
        self.context_label = QLabel(context_text)
        self.context_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.context_label.setWordWrap(True)
        layout.addWidget(self.context_label)

        filter_layout = QHBoxLayout()
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(8)
        filter_layout.addWidget(QLabel("查看范围"))
        self.scope_filter_combo = SearchableComboBox("输入范围关键字搜索")
        self.scope_filter_combo.addItem("当前可用", "current")
        self.scope_filter_combo.addItem("全部", "all")
        self.scope_filter_combo.addItem("全局", "global")
        self.scope_filter_combo.addItem("当前库", "database")
        self.scope_filter_combo.addItem("当前表", "table")
        filter_layout.addWidget(self.scope_filter_combo)
        filter_layout.addStretch()
        self.use_page_sql_btn = QPushButton("带入当前页面 SQL")
        filter_layout.addWidget(self.use_page_sql_btn)
        layout.addLayout(filter_layout)

        self.favorite_list = QListWidget()
        layout.addWidget(self.favorite_list, 1)

        editor_toolbar = QHBoxLayout()
        editor_toolbar.setContentsMargins(0, 0, 0, 0)
        editor_toolbar.setSpacing(8)
        editor_toolbar.addWidget(QLabel("SQL 内容"))
        editor_toolbar.addStretch()
        self.load_btn = QPushButton("载入到主页面")
        self.delete_btn = QPushButton("删除选中")
        editor_toolbar.addWidget(self.load_btn)
        editor_toolbar.addWidget(self.delete_btn)
        layout.addLayout(editor_toolbar)

        self.sql_editor = QPlainTextEdit()
        self.sql_editor.setPlaceholderText("这里可以编辑要保存或载入的 SQL")
        layout.addWidget(self.sql_editor, 1)

        save_layout = QHBoxLayout()
        save_layout.setContentsMargins(0, 0, 0, 0)
        save_layout.setSpacing(8)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("常用 SQL 名称")
        self.save_scope_combo = SearchableComboBox("输入保存范围关键字搜索")
        self.save_btn = QPushButton("保存")
        self.close_btn = QPushButton("关闭")
        save_layout.addWidget(QLabel("名称"))
        save_layout.addWidget(self.name_input, 1)
        save_layout.addWidget(QLabel("保存范围"))
        save_layout.addWidget(self.save_scope_combo)
        save_layout.addWidget(self.save_btn)
        save_layout.addWidget(self.close_btn)
        layout.addLayout(save_layout)

        self.scope_filter_combo.currentIndexChanged.connect(self._refresh_list)
        self.favorite_list.currentItemChanged.connect(self._on_item_changed)
        self.use_page_sql_btn.clicked.connect(self._restore_page_sql)
        self.load_btn.clicked.connect(self._load_current_sql)
        self.delete_btn.clicked.connect(self._delete_selected)
        self.save_btn.clicked.connect(self._save_current_sql)
        self.close_btn.clicked.connect(self.reject)

    def favorite_sqls(self) -> list[SqliteFavoriteSqlModel]:
        return list(self._favorites)

    def _refresh_scope_options(self):
        self.save_scope_combo.clear()
        self.save_scope_combo.addItem("全局", "global")
        self.save_scope_combo.addItem("当前库", "database")
        self.save_scope_combo.setItemData(
            1,
            "需要先选择数据库",
            Qt.ToolTipRole,
        )
        self.save_scope_combo.addItem("当前表", "table")
        self.save_scope_combo.setItemData(
            2,
            "需要先选择数据库表",
            Qt.ToolTipRole,
        )

    def _refresh_list(self):
        target_scope = str(self.scope_filter_combo.currentData() or "current").strip()
        self.favorite_list.clear()
        for favorite in self._filtered_favorites(target_scope):
            item = QListWidgetItem(self._favorite_label(favorite))
            item.setData(Qt.UserRole, self._favorite_key(favorite))
            item.setToolTip(favorite.sql or "")
            self.favorite_list.addItem(item)
        self.delete_btn.setEnabled(self.favorite_list.count() > 0)

    def _filtered_favorites(self, target_scope: str) -> list[SqliteFavoriteSqlModel]:
        if target_scope == "all":
            return list(self._favorites)
        if target_scope == "global":
            return [item for item in self._favorites if item.scope == "global"]
        if target_scope == "database":
            return [
                item
                for item in self._favorites
                if item.scope == "database"
                and item.database_path == self.current_database_path
            ]
        if target_scope == "table":
            return [
                item
                for item in self._favorites
                if item.scope == "table"
                and item.database_path == self.current_database_path
                and item.table_name == self.current_table_name
            ]
        return [
            item
            for item in self._favorites
            if item.scope == "global"
            or (
                item.scope == "database"
                and item.database_path == self.current_database_path
            )
            or (
                item.scope == "table"
                and item.database_path == self.current_database_path
                and item.table_name == self.current_table_name
            )
        ]

    def _on_item_changed(
        self,
        current: QListWidgetItem | None,
        previous: QListWidgetItem | None = None,
    ):
        favorite = self._selected_favorite()
        self.delete_btn.setEnabled(favorite is not None)
        if favorite is None:
            return
        self.name_input.setText(favorite.name or "")
        self.sql_editor.setPlainText(favorite.sql or "")
        self._set_scope_value(favorite.scope or "global")

    def _restore_page_sql(self):
        self.sql_editor.setPlainText(self._page_sql_text)
        if not self.name_input.text().strip():
            self.name_input.setText(self._default_name("global"))
        self.sql_editor.setFocus()

    def _load_current_sql(self):
        sql_text = self.sql_editor.toPlainText().strip()
        if not sql_text:
            favorite = self._selected_favorite()
            if favorite is not None:
                sql_text = favorite.sql or ""
        if not sql_text:
            QMessageBox.warning(self, "提示", "请先选择一条常用 SQL 或输入 SQL")
            return
        self.loaded_sql = sql_text
        self.status_message = "已载入常用 SQL 到主页面"
        self.accept()

    def _delete_selected(self):
        favorite = self._selected_favorite()
        if favorite is None:
            QMessageBox.warning(self, "提示", "请先选择一条常用 SQL")
            return
        target_key = self._favorite_key(favorite)
        self._favorites = [
            item for item in self._favorites if self._favorite_key(item) != target_key
        ]
        self.status_message = f"已删除常用 SQL：{favorite.name}"
        self._refresh_list()
        self.name_input.clear()
        self.sql_editor.clear()

    def _save_current_sql(self):
        sql_text = self.sql_editor.toPlainText().strip()
        if not sql_text:
            QMessageBox.warning(self, "提示", "请输入要保存的 SQL")
            return

        scope = str(self.save_scope_combo.currentData() or "global").strip()
        if scope == "database" and not self.current_database_path:
            QMessageBox.warning(self, "提示", "当前未选择数据库，不能保存为库级 SQL")
            return
        if scope == "table" and not (
            self.current_database_path and self.current_table_name
        ):
            QMessageBox.warning(self, "提示", "当前未选择表，不能保存为表级 SQL")
            return

        name = (self.name_input.text() or "").strip()
        if not name:
            name = self._default_name(scope)
            self.name_input.setText(name)
        if not name:
            QMessageBox.warning(self, "提示", "请输入名称")
            return

        favorite = SqliteFavoriteSqlModel(
            name=name,
            sql=sql_text,
            scope=scope,
            database_path=self.current_database_path if scope != "global" else "",
            table_name=self.current_table_name if scope == "table" else "",
        )
        target_key = self._favorite_key(favorite)
        replaced = False
        next_favorites: list[SqliteFavoriteSqlModel] = []
        for item in self._favorites:
            if self._favorite_key(item) == target_key:
                next_favorites.append(favorite)
                replaced = True
            else:
                next_favorites.append(item)
        if not replaced:
            next_favorites.append(favorite)
        self._favorites = sorted(
            next_favorites,
            key=lambda item: (
                self._scope_order(item.scope),
                (item.name or "").lower(),
                (item.database_path or "").lower(),
                (item.table_name or "").lower(),
            ),
        )
        self.status_message = f"已保存常用 SQL：{name}"
        self._refresh_list()
        self._select_favorite(target_key)

    def _select_favorite(self, target_key: str):
        for index in range(self.favorite_list.count()):
            item = self.favorite_list.item(index)
            if item.data(Qt.UserRole) == target_key:
                self.favorite_list.setCurrentItem(item)
                return

    def _selected_favorite(self) -> SqliteFavoriteSqlModel | None:
        item = self.favorite_list.currentItem()
        target_key = item.data(Qt.UserRole) if item is not None else ""
        if not target_key:
            return None
        for favorite in self._favorites:
            if self._favorite_key(favorite) == target_key:
                return favorite
        return None

    def _set_scope_value(self, target_scope: str):
        for index in range(self.save_scope_combo.count()):
            if self.save_scope_combo.itemData(index) == target_scope:
                self.save_scope_combo.setCurrentIndex(index)
                return

    def _favorite_label(self, favorite: SqliteFavoriteSqlModel) -> str:
        scope_label = {
            "global": "全局",
            "database": "库",
            "table": "表",
        }.get(favorite.scope or "", "未知")
        return f"[{scope_label}] {favorite.name or '-'}"

    def _default_name(self, scope: str) -> str:
        if scope == "table" and self.current_table_name:
            return f"{self.current_table_name}-常用查询"
        if scope == "database" and self.current_database_path:
            return f"{os.path.basename(self.current_database_path)}-常用查询"
        return "常用查询"

    @classmethod
    def _favorite_key(cls, favorite: SqliteFavoriteSqlModel) -> str:
        return cls.TABLE_KEY_SEPARATOR.join(
            [
                favorite.scope or "",
                favorite.database_path or "",
                favorite.table_name or "",
                favorite.name or "",
            ]
        )

    @staticmethod
    def _scope_order(scope: str) -> int:
        if scope == "global":
            return 0
        if scope == "database":
            return 1
        if scope == "table":
            return 2
        return 9
