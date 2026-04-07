import math
import os

from PySide6.QtCore import QThreadPool, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from model.config import (
    SqliteFavoriteSqlModel,
    SqliteScannedDirectoryModel,
    SqliteTableViewConfigModel,
)
from server.config import SearchConfig, SqliteQueryConfig
from services.sqlite_query_service import SqliteQueryService
from ui.dialogs.sqlite_column_config_dialog import SqliteColumnConfigDialog
from ui.dialogs.sqlite_favorite_sql_dialog import SqliteFavoriteSqlDialog
from ui.dialogs.work_dir_dialog import WorkDirDialog
from ui.widgets.searchable_combo_box import SearchableComboBox
from workers.worker import Worker


class SqliteQueryPage(QWidget):
    TABLE_KEY_SEPARATOR = "\u241f"
    FAVORITE_SCOPE_GLOBAL = "global"
    FAVORITE_SCOPE_DATABASE = "database"
    FAVORITE_SCOPE_TABLE = "table"

    def __init__(self):
        super().__init__()
        self.pool = QThreadPool.globalInstance()
        self._workers: list[Worker] = []
        self._state_guard = False
        self._scan_running = False
        self._pending_filter_field = "*"
        self._directory_label_map: dict[str, str] = {}

        self.config = SqliteQueryConfig.read_config()
        self.scanned_directories: list[SqliteScannedDirectoryModel] = list(
            self.config.scanned_directories or []
        )
        self.current_query_mode = "table"
        self.current_result_columns: list[str] = []
        self.current_result_rows: list[list] = []
        self.current_total_rows = 0
        self.current_page = 1

        self._init_ui()
        self._bind()
        self._load_saved_state()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        self.title_label = QLabel("SQLite 查询")
        self.title_label.setStyleSheet("font-size: 18px; font-weight: 600;")

        self.status_label = QLabel("状态：就绪")
        self.status_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.entry_type_label = QLabel("入口：POS")
        self.entry_type_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

        self.work_dir_btn = QPushButton("添加工作目录")
        self.scan_btn = QPushButton("扫描 SQLite")
        self.favorite_manage_btn = QPushButton("常用 SQL 管理")
        self.open_database_btn = QPushButton("载入表")
        self.refresh_table_btn = QPushButton("刷新结果")
        self.column_config_btn = QPushButton("列设置")
        self.status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        action_layout = QHBoxLayout()
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(8)
        action_layout.addWidget(self.title_label)
        action_layout.addSpacing(8)
        action_layout.addWidget(self.entry_type_label)
        action_layout.addWidget(self.work_dir_btn)
        action_layout.addWidget(self.scan_btn)
        action_layout.addWidget(self.favorite_manage_btn)
        action_layout.addStretch()
        action_layout.addWidget(self.status_label)
        main_layout.addLayout(action_layout)

        self.directory_combo = SearchableComboBox("输入目录关键字搜索")
        self.directory_combo.setMinimumWidth(300)
        self.database_combo = SearchableComboBox("输入数据库名搜索")
        self.database_combo.setMinimumWidth(300)
        self.table_combo = SearchableComboBox("输入表名搜索")
        self.table_combo.setMinimumWidth(220)

        self.page_size_spin = QSpinBox()
        self.page_size_spin.setRange(10, 5000)
        self.page_size_spin.setSingleStep(10)
        self.page_size_spin.setValue(100)

        selection_layout = QHBoxLayout()
        selection_layout.setContentsMargins(0, 0, 0, 0)
        selection_layout.setSpacing(8)
        selection_layout.addWidget(QLabel("目录"))
        selection_layout.addWidget(self.directory_combo, 2)
        selection_layout.addWidget(QLabel("数据库"))
        selection_layout.addWidget(self.database_combo, 2)
        selection_layout.addWidget(QLabel("表"))
        selection_layout.addWidget(self.table_combo, 1)
        main_layout.addLayout(selection_layout)

        self.filter_field_combo = SearchableComboBox("输入字段名搜索")
        self.filter_field_combo.setMinimumWidth(180)
        self.filter_operator_combo = SearchableComboBox("输入操作符搜索")
        self.filter_operator_combo.setMinimumWidth(120)
        self.filter_operator_combo.addItem("包含", "contains")
        self.filter_operator_combo.addItem("等于", "equals")
        self.filter_operator_combo.addItem("开头是", "starts_with")
        self.filter_operator_combo.addItem("结尾是", "ends_with")
        self.filter_operator_combo.addItem("大于", "gt")
        self.filter_operator_combo.addItem("大于等于", "gte")
        self.filter_operator_combo.addItem("小于", "lt")
        self.filter_operator_combo.addItem("小于等于", "lte")
        self.filter_operator_combo.addItem("为空", "is_null")
        self.filter_operator_combo.addItem("不为空", "not_null")

        self.filter_value_input = QLineEdit()
        self.filter_value_input.setPlaceholderText("输入关键字或值")
        self.filter_apply_btn = QPushButton("字段查询")
        self.filter_clear_btn = QPushButton("清空条件")

        filter_layout = QHBoxLayout()
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(8)
        filter_layout.addWidget(QLabel("自定义字段查询"))
        filter_layout.addWidget(self.filter_field_combo)
        filter_layout.addWidget(self.filter_operator_combo)
        filter_layout.addWidget(self.filter_value_input, 1)
        filter_layout.addWidget(self.filter_apply_btn)
        filter_layout.addWidget(self.filter_clear_btn)
        main_layout.addLayout(filter_layout)

        self.favorite_combo = SearchableComboBox("输入常用 SQL 名称搜索")
        self.favorite_combo.hide()

        sql_frame = QFrame()
        sql_frame.setObjectName("sqliteSqlFrame")
        sql_layout = QVBoxLayout(sql_frame)
        sql_layout.setContentsMargins(12, 12, 12, 12)
        sql_layout.setSpacing(8)

        sql_toolbar = QHBoxLayout()
        sql_toolbar.setContentsMargins(0, 0, 0, 0)
        sql_toolbar.setSpacing(8)
        sql_toolbar.addWidget(QLabel("SQL 查询"))
        sql_toolbar.addStretch()
        self.run_sql_btn = QPushButton("执行SQL")
        self.clear_sql_btn = QPushButton("清空SQL")
        sql_toolbar.addWidget(self.run_sql_btn)
        sql_toolbar.addWidget(self.clear_sql_btn)
        sql_layout.addLayout(sql_toolbar)

        self.sql_editor = QPlainTextEdit()
        self.sql_editor.setPlaceholderText(
            "支持 SELECT / WITH / PRAGMA 等查询。当前页面默认按查询用途使用。"
        )
        sql_font = QFont("Consolas")
        if not sql_font.exactMatch():
            sql_font = QFont("Courier New")
        self.sql_editor.setFont(sql_font)
        self.sql_editor.setMinimumHeight(120)
        sql_layout.addWidget(self.sql_editor, 1)

        result_frame = QFrame()
        result_frame.setObjectName("sqliteResultFrame")
        result_layout = QVBoxLayout(result_frame)
        result_layout.setContentsMargins(12, 12, 12, 12)
        result_layout.setSpacing(8)

        result_header_layout = QHBoxLayout()
        result_header_layout.setContentsMargins(0, 0, 0, 0)
        result_header_layout.setSpacing(8)
        self.current_table_label = QLabel("当前表：-")
        self.current_table_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        result_header_layout.addWidget(self.current_table_label)
        result_header_layout.addStretch()
        result_header_layout.addWidget(self.refresh_table_btn)
        result_header_layout.addWidget(self.column_config_btn)
        result_layout.addLayout(result_header_layout)

        self.result_summary_label = QLabel("结果：-")
        self.result_summary_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.result_summary_label.setWordWrap(True)

        self.result_table = QTableWidget(0, 0, self)
        self.result_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.result_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.result_table.setAlternatingRowColors(True)
        self.result_table.setWordWrap(False)
        self.result_table.verticalHeader().setVisible(False)
        self.result_table.horizontalHeader().setStretchLastSection(True)
        self.result_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents
        )
        result_layout.addWidget(self.result_table, 1)

        self.prev_page_btn = QPushButton("上一页")
        self.next_page_btn = QPushButton("下一页")
        self.page_spin = QSpinBox()
        self.page_spin.setRange(1, 1)
        self.total_page_label = QLabel("共 1 页")
        self.total_count_label = QLabel("共 0 行")

        pagination_layout = QHBoxLayout()
        pagination_layout.setContentsMargins(0, 0, 0, 0)
        pagination_layout.setSpacing(8)
        pagination_layout.addWidget(self.result_summary_label, 1)
        pagination_layout.addWidget(QLabel("每页"))
        pagination_layout.addWidget(self.page_size_spin)
        pagination_layout.addSpacing(6)
        pagination_layout.addWidget(self.total_count_label)
        pagination_layout.addWidget(self.prev_page_btn)
        pagination_layout.addWidget(QLabel("页码"))
        pagination_layout.addWidget(self.page_spin)
        pagination_layout.addWidget(self.total_page_label)
        pagination_layout.addWidget(self.next_page_btn)
        result_layout.addLayout(pagination_layout)

        self.sql_result_splitter = QSplitter(Qt.Vertical)
        self.sql_result_splitter.setChildrenCollapsible(False)
        self.sql_result_splitter.addWidget(sql_frame)
        self.sql_result_splitter.addWidget(result_frame)
        self.sql_result_splitter.setStretchFactor(0, 0)
        self.sql_result_splitter.setStretchFactor(1, 1)
        self.sql_result_splitter.setSizes([180, 520])
        main_layout.addWidget(self.sql_result_splitter, 1)

    def _bind(self):
        self.work_dir_btn.clicked.connect(self.open_work_dir_dialog)
        self.scan_btn.clicked.connect(self.start_scan)
        self.favorite_manage_btn.clicked.connect(self.open_favorite_sql_dialog)
        self.refresh_table_btn.clicked.connect(self.refresh_current_table)
        self.column_config_btn.clicked.connect(self.open_column_config_dialog)
        self.filter_apply_btn.clicked.connect(self.apply_quick_filter)
        self.filter_clear_btn.clicked.connect(self.clear_quick_filter)
        self.run_sql_btn.clicked.connect(self.run_sql_query)
        self.clear_sql_btn.clicked.connect(self.clear_sql_editor)
        self.directory_combo.currentIndexChanged.connect(self._on_directory_changed)
        self.database_combo.currentIndexChanged.connect(self._on_database_changed)
        self.table_combo.currentIndexChanged.connect(self._on_table_changed)
        self.filter_field_combo.currentIndexChanged.connect(self._on_filter_field_changed)
        self.page_size_spin.valueChanged.connect(self._on_page_size_changed)
        self.prev_page_btn.clicked.connect(self.goto_previous_page)
        self.next_page_btn.clicked.connect(self.goto_next_page)
        self.page_spin.editingFinished.connect(self.goto_specific_page)
        self.filter_value_input.returnPressed.connect(self.apply_quick_filter)

    def _load_saved_state(self):
        self.sql_editor.setPlainText(self.config.last_sql or "")
        self._refresh_work_dir_summary()
        self._restore_saved_selection()
        self._refresh_favorite_combo()
        if not self.scanned_directories:
            self._populate_filter_field_combo([])
            self._update_selection_summary()
            self._set_status("暂无扫描结果，请先扫描 SQLite")

    def open_work_dir_dialog(self):
        dialog = WorkDirDialog(self, mode="sqlite")
        dialog.exec()
        self._refresh_work_dir_summary()
        if SearchConfig.read_work_dir():
            self.start_scan()

    def open_favorite_sql_dialog(self):
        dialog = SqliteFavoriteSqlDialog(
            favorites=list(self.config.favorite_sqls or []),
            current_database_path=self.current_database_path(),
            current_table_name=self.current_table_name(),
            current_sql=self.sql_editor.toPlainText(),
            parent=self,
        )
        dialog.exec()

        updated_favorites = dialog.favorite_sqls()
        current_dump = [item.model_dump() for item in self.config.favorite_sqls]
        next_dump = [item.model_dump() for item in updated_favorites]
        if current_dump != next_dump:
            self.config.favorite_sqls = sorted(
                updated_favorites,
                key=lambda item: (
                    self._favorite_scope_order(item.scope),
                    item.name.lower(),
                    item.database_path.lower(),
                    item.table_name.lower(),
                ),
            )
            self._save_config()
            self._refresh_favorite_combo()

        if dialog.loaded_sql:
            self.sql_editor.setPlainText(dialog.loaded_sql)
            self.config.last_sql = dialog.loaded_sql
            self._save_config()

        if dialog.status_message:
            self._set_status(dialog.status_message)

    def start_scan(self):
        if self._scan_running:
            self._set_status("扫描进行中，请稍候")
            return

        work_dirs = SearchConfig.read_work_dir()
        if not work_dirs:
            QMessageBox.warning(self, "提示", "请先设置 POS 工作目录")
            return

        try:
            depth = int(SearchConfig.read().max_depth)
        except Exception:
            depth = 3

        self._scan_running = True
        self.scan_btn.setEnabled(False)
        self._set_status("开始扫描 SQLite 数据库...")
        self._start_worker(
            lambda: SqliteQueryService.scan_sqlite_directories(work_dirs, depth),
            self._on_scan_finished,
            on_error=self._on_scan_error,
        )

    def _on_scan_finished(self, scanned_directories: list[SqliteScannedDirectoryModel]):
        self._scan_running = False
        self.scan_btn.setEnabled(True)
        self.scanned_directories = list(scanned_directories or [])
        self.config.scanned_directories = self.scanned_directories
        self._save_config()

        total_databases = sum(
            len(item.database_files or []) for item in self.scanned_directories
        )
        self._restore_saved_selection()
        self._set_status(
            f"扫描完成，找到 {len(self.scanned_directories)} 个目录，{total_databases} 个数据库文件"
        )

    def _on_scan_error(self, message: str):
        self._scan_running = False
        self.scan_btn.setEnabled(True)
        self._handle_error(message)

    def _on_directory_changed(self):
        if self._state_guard:
            return
        current_directory_path = self.current_directory_path()
        self.config.last_directory_path = current_directory_path
        if current_directory_path != self._directory_path_for_database(
            self.config.last_database_path
        ):
            self.config.last_database_path = ""
            self.config.last_table_name = ""
        self._save_config()
        self._populate_database_combo(self.config.last_database_path)
        self._update_selection_summary()
        self._refresh_favorite_combo()
        if self.current_database_path():
            self._on_database_changed()
            return
        self._populate_table_combo([])
        self._render_empty_result()

    def _on_database_changed(self):
        if self._state_guard:
            return
        current_database_path = self.current_database_path()
        previous_database_path = self.config.last_database_path
        preferred_table = (
            self.config.last_table_name
            if current_database_path
            and current_database_path == previous_database_path
            else ""
        )
        self.config.last_database_path = current_database_path
        if current_database_path != previous_database_path:
            self.config.last_table_name = ""
        self._save_config()
        self._update_selection_summary()
        self._refresh_favorite_combo()
        if current_database_path:
            self.open_database(preferred_table=preferred_table)
            return
        self._populate_table_combo([])
        self._render_empty_result()

    def _on_table_changed(self):
        if self._state_guard:
            return
        self.config.last_table_name = self.current_table_name()
        self._save_config()
        self._update_selection_summary()
        self._refresh_favorite_combo()
        if not self.current_table_name():
            self._pending_filter_field = "*"
            self._populate_filter_field_combo([])
            self._render_empty_result()
            return

        table_view = self._get_current_table_view_config(create=True)
        self._pending_filter_field = table_view.filter_field or "*"
        self._state_guard = True
        self.page_size_spin.setValue(max(10, int(table_view.page_size or 100)))
        self._set_filter_operator(table_view.filter_operator or "contains")
        self.filter_value_input.setText(table_view.filter_value or "")
        self._state_guard = False
        self.current_page = 1
        self.load_current_table(reset_page=True)

    def _on_filter_field_changed(self):
        if self._state_guard:
            return
        self._pending_filter_field = str(
            self.filter_field_combo.currentData() or "*"
        ).strip() or "*"

    def _on_page_size_changed(self):
        if self._state_guard:
            return
        table_view = self._get_current_table_view_config(create=True)
        if table_view is not None:
            table_view.page_size = int(self.page_size_spin.value())
            self._save_config()

        if self.current_query_mode == "table" and self.current_table_name():
            self.current_page = 1
            self.load_current_table(reset_page=True)
        elif self.current_query_mode == "sql":
            self.current_page = 1
            self._render_sql_page()

    def open_database(self, preferred_table: str = ""):
        database_path = self.current_database_path()
        if not database_path:
            return

        self._set_status(f"正在打开数据库：{database_path}")
        self._start_worker(
            lambda: SqliteQueryService.list_tables(database_path),
            lambda tables: self._on_tables_loaded(
                database_path,
                tables,
                preferred_table,
            ),
        )

    def _on_tables_loaded(
        self,
        database_path: str,
        tables: list[str],
        preferred_table: str = "",
    ):
        if database_path != self.current_database_path():
            return
        self._populate_table_combo(tables, preferred_table)
        if self.current_table_name():
            self._on_table_changed()
            return
        self._set_status(f"数据库已打开，共 {len(tables or [])} 张表/视图")

    def refresh_current_table(self):
        if self.current_query_mode == "sql":
            self.run_sql_query()
            return
        self.load_current_table(reset_page=False)

    def load_current_table(self, reset_page: bool):
        database_path = self.current_database_path()
        table_name = self.current_table_name()
        if not database_path or not table_name:
            return

        if reset_page:
            self.current_page = 1

        table_view = self._get_current_table_view_config(create=True)
        filter_field = self._current_filter_field_value()
        filter_operator = self._current_filter_operator_value()
        filter_value = self.filter_value_input.text().strip()
        if table_view is not None:
            table_view.filter_field = filter_field
            table_view.filter_operator = filter_operator
            table_view.filter_value = filter_value
            table_view.page_size = int(self.page_size_spin.value())
            self._save_config()

        requested_page = max(1, int(self.current_page or 1))
        requested_page_size = max(10, int(self.page_size_spin.value()))
        self.current_query_mode = "table"
        self._set_status(f"正在查询表：{table_name}")
        self._start_worker(
            lambda: SqliteQueryService.fetch_table_page(
                database_path=database_path,
                table_name=table_name,
                page=requested_page,
                page_size=requested_page_size,
                filter_field=filter_field,
                filter_operator=filter_operator,
                filter_value=filter_value,
            ),
            lambda result: self._on_table_page_loaded(
                database_path,
                table_name,
                requested_page,
                result,
            ),
        )

    def _on_table_page_loaded(
        self,
        database_path: str,
        table_name: str,
        requested_page: int,
        result: dict,
    ):
        if database_path != self.current_database_path():
            return
        if table_name != self.current_table_name():
            return

        self.current_query_mode = "table"
        self.current_result_columns = list(result.get("columns") or [])
        self.current_result_rows = list(result.get("rows") or [])
        self.current_total_rows = int(result.get("total") or 0)
        self.current_page = min(
            max(1, requested_page),
            max(
                1,
                self._page_count(
                    self.current_total_rows,
                    self.page_size_spin.value(),
                ),
            ),
        )
        self._update_selection_summary()
        self._populate_filter_field_combo(self.current_result_columns)
        self._render_result_table(
            self.current_result_columns,
            self.current_result_rows,
        )
        self._apply_column_visibility()
        self._update_pagination(self.current_total_rows)
        self.result_summary_label.setText(
            f"结果：表 {table_name}，当前第 {self.current_page} 页，共 {self.current_total_rows} 行"
        )
        self._set_status(
            f"表查询完成：{table_name}，当前页 {len(self.current_result_rows)} 行，总计 {self.current_total_rows} 行"
        )

    def apply_quick_filter(self):
        if not self.current_table_name():
            QMessageBox.warning(self, "提示", "请先选择数据库表")
            return
        self.current_page = 1
        self.load_current_table(reset_page=True)

    def clear_quick_filter(self):
        table_view = self._get_current_table_view_config(create=True)
        self._state_guard = True
        self._pending_filter_field = "*"
        self._populate_filter_field_combo(self.current_result_columns)
        self._set_filter_operator("contains")
        self.filter_value_input.clear()
        self._state_guard = False
        if table_view is not None:
            table_view.filter_field = "*"
            table_view.filter_operator = "contains"
            table_view.filter_value = ""
            self._save_config()
        if self.current_table_name():
            self.current_page = 1
            self.load_current_table(reset_page=True)

    def run_sql_query(self):
        database_path = self.current_database_path()
        if not database_path:
            QMessageBox.warning(self, "提示", "请先选择数据库文件")
            return

        sql_text = self.sql_editor.toPlainText().strip()
        if not sql_text:
            QMessageBox.warning(self, "提示", "请输入要执行的 SQL")
            return

        self.config.last_sql = sql_text
        self._save_config()
        self.current_query_mode = "sql"
        self.current_page = 1
        self._set_status("正在执行 SQL 查询...")
        self._start_worker(
            lambda: SqliteQueryService.execute_sql(database_path, sql_text),
            lambda result: self._on_sql_result_loaded(database_path, result),
        )

    def _on_sql_result_loaded(self, database_path: str, result: dict):
        if database_path != self.current_database_path():
            return

        self.current_query_mode = "sql"
        self.current_result_columns = list(result.get("columns") or [])
        self.current_result_rows = list(result.get("rows") or [])
        self.current_total_rows = int(result.get("total") or 0)
        self.current_page = 1
        self._update_selection_summary()
        self._render_sql_page()
        message = result.get("message") or "SQL 执行完成"
        self.result_summary_label.setText(
            f"结果：{message}，当前展示第 {self.current_page} 页"
        )
        self._set_status(message)

    def clear_sql_editor(self):
        self.sql_editor.clear()
        self.config.last_sql = ""
        self._save_config()

    def load_selected_favorite(self):
        favorite = self.current_favorite()
        if favorite is None:
            return
        self.sql_editor.setPlainText(favorite.sql or "")
        self.config.last_sql = favorite.sql or ""
        self._save_config()
        self._set_status(f"已载入常用 SQL：{favorite.name}")

    def save_favorite_sql(self, scope: str):
        sql_text = self.sql_editor.toPlainText().strip()
        if not sql_text:
            QMessageBox.warning(self, "提示", "请先输入 SQL")
            return

        database_path = ""
        table_name = ""
        if scope in (
            self.FAVORITE_SCOPE_DATABASE,
            self.FAVORITE_SCOPE_TABLE,
        ):
            database_path = self.current_database_path()
            if not database_path:
                QMessageBox.warning(self, "提示", "请先选择数据库")
                return
        if scope == self.FAVORITE_SCOPE_TABLE:
            table_name = self.current_table_name()
            if not table_name:
                QMessageBox.warning(self, "提示", "请先选择表")
                return

        default_name = self._default_favorite_name(scope, table_name)
        name, ok = QInputDialog.getText(
            self,
            "保存常用 SQL",
            "请输入名称",
            text=default_name,
        )
        if not ok:
            return
        cleaned_name = (name or "").strip()
        if not cleaned_name:
            QMessageBox.warning(self, "提示", "名称不能为空")
            return

        new_favorite = SqliteFavoriteSqlModel(
            name=cleaned_name,
            sql=sql_text,
            scope=scope,
            database_path=database_path,
            table_name=table_name,
        )

        replaced = False
        next_favorites: list[SqliteFavoriteSqlModel] = []
        for favorite in self.config.favorite_sqls:
            if self._favorite_key(favorite) == self._favorite_key(new_favorite):
                next_favorites.append(new_favorite)
                replaced = True
            else:
                next_favorites.append(favorite)
        if not replaced:
            next_favorites.append(new_favorite)

        self.config.favorite_sqls = sorted(
            next_favorites,
            key=lambda item: (
                self._favorite_scope_order(item.scope),
                item.name.lower(),
                item.database_path.lower(),
                item.table_name.lower(),
            ),
        )
        self._save_config()
        self._refresh_favorite_combo(self._favorite_key(new_favorite))
        self._set_status(f"已保存常用 SQL：{cleaned_name}")

    def delete_selected_favorite(self):
        favorite = self.current_favorite()
        if favorite is None:
            QMessageBox.warning(self, "提示", "请先选择一条常用 SQL")
            return

        target_key = self._favorite_key(favorite)
        self.config.favorite_sqls = [
            item
            for item in self.config.favorite_sqls
            if self._favorite_key(item) != target_key
        ]
        self._save_config()
        self._refresh_favorite_combo()
        self._set_status(f"已删除常用 SQL：{favorite.name}")

    def open_column_config_dialog(self):
        if self.current_query_mode != "table" or not self.current_result_columns:
            QMessageBox.warning(self, "提示", "请先选择表并加载表数据")
            return

        table_view = self._get_current_table_view_config(create=True)
        visible_columns = (
            table_view.visible_columns
            if table_view and table_view.visible_columns
            else self.current_result_columns
        )
        dialog = SqliteColumnConfigDialog(
            columns=self.current_result_columns,
            visible_columns=visible_columns,
            parent=self,
        )
        if not dialog.exec():
            return

        selected_columns = dialog.visible_columns() or list(
            self.current_result_columns
        )
        if table_view is not None:
            table_view.visible_columns = list(selected_columns)
            self._save_config()
        self._apply_column_visibility()
        self._set_status("列显示设置已更新")

    def goto_previous_page(self):
        if self.current_page <= 1:
            return
        self.current_page -= 1
        self._reload_current_page()

    def goto_next_page(self):
        max_page = self._page_count(
            self.current_total_rows,
            self.page_size_spin.value(),
        )
        if self.current_page >= max_page:
            return
        self.current_page += 1
        self._reload_current_page()

    def goto_specific_page(self):
        target_page = max(1, int(self.page_spin.value() or 1))
        if target_page == self.current_page:
            return
        self.current_page = target_page
        self._reload_current_page()

    def _reload_current_page(self):
        if self.current_query_mode == "sql":
            self._render_sql_page()
            return
        self.load_current_table(reset_page=False)

    def _render_sql_page(self):
        page_rows = SqliteQueryService.paginate_rows(
            self.current_result_rows,
            self.current_page,
            self.page_size_spin.value(),
        )
        self._render_result_table(self.current_result_columns, page_rows)
        self._update_pagination(self.current_total_rows)
        self.result_summary_label.setText(
            f"结果：SQL 查询，共 {self.current_total_rows} 行，当前第 {self.current_page} 页"
        )
        self._set_status(
            f"SQL 查询结果已展示，第 {self.current_page} 页，共 {self.current_total_rows} 行"
        )

    def _render_result_table(self, columns: list[str], rows: list[list]):
        self.result_table.clear()
        self.result_table.setColumnCount(len(columns))
        self.result_table.setHorizontalHeaderLabels(list(columns or []))
        self.result_table.setRowCount(len(rows or []))

        for row_index, row_values in enumerate(rows or []):
            for column_index, value in enumerate(row_values):
                item = QTableWidgetItem("" if value is None else str(value))
                item.setToolTip("" if value is None else str(value))
                self.result_table.setItem(row_index, column_index, item)

        self.result_table.resizeColumnsToContents()

    def _render_empty_result(self):
        self.current_result_columns = []
        self.current_result_rows = []
        self.current_total_rows = 0
        self.current_page = 1
        self.current_query_mode = "table"
        self._pending_filter_field = "*"
        self._populate_filter_field_combo([])
        self._render_result_table([], [])
        self._update_pagination(0)
        self._update_selection_summary()
        self.result_summary_label.setText("结果：暂无数据")

    def _update_pagination(self, total_rows: int):
        page_count = self._page_count(total_rows, self.page_size_spin.value())
        self._state_guard = True
        self.page_spin.setRange(1, page_count)
        self.page_spin.setValue(min(max(1, self.current_page), page_count))
        self._state_guard = False
        self.total_page_label.setText(f"共 {page_count} 页")
        self.total_count_label.setText(f"共 {int(total_rows or 0)} 行")
        self.prev_page_btn.setEnabled(self.current_page > 1)
        self.next_page_btn.setEnabled(self.current_page < page_count)

    def _populate_directory_combo(self, preferred_path: str = ""):
        self._directory_label_map = self._build_directory_label_map()
        items = []
        for scanned_directory in self.scanned_directories:
            label = self._format_directory_label(scanned_directory)
            items.append((label, scanned_directory.directory_path))
        self._set_combo_items(
            self.directory_combo,
            items,
            "请选择目录",
            preferred_path,
            select_first_item=True,
        )
        if not items:
            self._populate_database_combo("")
            self._populate_table_combo([])
            self._render_empty_result()
        self._update_selection_summary()
        return self.current_directory_path()

    def _populate_database_combo(self, preferred_path: str = ""):
        current_directory = self.current_scanned_directory()
        items = []
        if current_directory is not None:
            for database_file in current_directory.database_files:
                label = self._format_database_label(
                    database_file.file_name,
                    database_file.size,
                )
                items.append((label, database_file.file_path))
        self._set_combo_items(
            self.database_combo,
            items,
            "请选择数据库",
            preferred_path,
            select_first_item=True,
        )
        if not items:
            self._populate_table_combo([])
            self._render_empty_result()
        self._update_selection_summary()
        return self.current_database_path()

    def _populate_table_combo(
        self,
        tables: list[str],
        preferred_table: str = "",
    ):
        items = [(table_name, table_name) for table_name in tables or []]
        self._set_combo_items(
            self.table_combo,
            items,
            "请选择表",
            preferred_table,
            select_first_item=True,
        )
        if not items:
            self._populate_filter_field_combo([])
            self._render_empty_result()
        self._update_selection_summary()
        return self.current_table_name()

    def _populate_filter_field_combo(self, columns: list[str]):
        current_value = self._pending_filter_field or self._current_filter_field_value()
        items = [("全部字段", "*")]
        items.extend((column, column) for column in columns or [])
        preferred_value = current_value if current_value in {"*"} | set(columns or []) else "*"
        self._set_combo_items(
            self.filter_field_combo,
            items,
            "",
            preferred_value,
            include_placeholder=False,
        )
        self._pending_filter_field = self._current_filter_field_value()

    def _set_combo_items(
        self,
        combo: QComboBox,
        items: list[tuple[str, str]],
        placeholder: str,
        preferred_value: str = "",
        include_placeholder: bool = True,
        select_first_item: bool = False,
    ) -> str:
        combo.blockSignals(True)
        combo.clear()
        if include_placeholder:
            combo.addItem(placeholder, "")
        preferred_index = 0
        start_index = 1 if include_placeholder else 0
        preferred_found = False
        for index, (label, value) in enumerate(items, start=start_index):
            combo.addItem(label, value)
            if preferred_value and value == preferred_value:
                preferred_index = index
                preferred_found = True
        if select_first_item and items and not preferred_found:
            preferred_index = start_index
        combo.setCurrentIndex(preferred_index if combo.count() else -1)
        combo.blockSignals(False)
        return combo.currentData() or ""

    def _apply_column_visibility(self):
        visible_columns = list(self.current_result_columns)
        if self.current_query_mode == "table":
            table_view = self._get_current_table_view_config(create=True)
            if table_view and table_view.visible_columns:
                visible_columns = list(table_view.visible_columns)

        for column_index, column_name in enumerate(self.current_result_columns):
            hidden = column_name not in visible_columns
            self.result_table.setColumnHidden(column_index, hidden)

    def _refresh_favorite_combo(self, preferred_key: str = ""):
        current_database = self.current_database_path()
        current_table = self.current_table_name()
        items: list[tuple[str, str]] = []
        for favorite in self.config.favorite_sqls:
            if favorite.scope == self.FAVORITE_SCOPE_GLOBAL:
                items.append((f"[全局] {favorite.name}", self._favorite_key(favorite)))
                continue
            if (
                favorite.scope == self.FAVORITE_SCOPE_DATABASE
                and favorite.database_path == current_database
            ):
                items.append((f"[库] {favorite.name}", self._favorite_key(favorite)))
                continue
            if (
                favorite.scope == self.FAVORITE_SCOPE_TABLE
                and favorite.database_path == current_database
                and favorite.table_name == current_table
            ):
                items.append((f"[表] {favorite.name}", self._favorite_key(favorite)))

        self._set_combo_items(
            self.favorite_combo,
            items,
            "请选择常用 SQL",
            preferred_key,
        )
        self.favorite_manage_btn.setText(f"常用 SQL ({len(items)})")
        if not items:
            self.favorite_manage_btn.setToolTip("当前上下文下暂无可用的常用 SQL")
            return
        preview_names = "；".join(label for label, _ in items[:5])
        if len(items) > 5:
            preview_names += "；..."
        self.favorite_manage_btn.setToolTip(preview_names)

    def current_scanned_directory(self) -> SqliteScannedDirectoryModel | None:
        current_directory_path = self.current_directory_path()
        for scanned_directory in self.scanned_directories:
            if scanned_directory.directory_path == current_directory_path:
                return scanned_directory
        return None

    def current_directory_path(self) -> str:
        return str(self.directory_combo.currentData() or "").strip()

    def current_database_path(self) -> str:
        return str(self.database_combo.currentData() or "").strip()

    def current_table_name(self) -> str:
        return str(self.table_combo.currentData() or "").strip()

    def current_favorite(self) -> SqliteFavoriteSqlModel | None:
        target_key = str(self.favorite_combo.currentData() or "").strip()
        if not target_key:
            return None
        for favorite in self.config.favorite_sqls:
            if self._favorite_key(favorite) == target_key:
                return favorite
        return None

    def _current_filter_field_value(self) -> str:
        pending_value = str(self._pending_filter_field or "").strip()
        if pending_value:
            return pending_value
        current_value = str(self.filter_field_combo.currentData() or "").strip()
        return current_value or "*"

    def _current_filter_operator_value(self) -> str:
        return str(self.filter_operator_combo.currentData() or "contains").strip()

    def _set_filter_operator(self, operator_value: str):
        for index in range(self.filter_operator_combo.count()):
            if self.filter_operator_combo.itemData(index) == operator_value:
                self.filter_operator_combo.setCurrentIndex(index)
                return
        self.filter_operator_combo.setCurrentIndex(0)

    def _get_current_table_view_config(
        self,
        create: bool = False,
    ) -> SqliteTableViewConfigModel | None:
        key = self._current_table_view_key()
        if not key:
            return None
        if key not in self.config.table_view_configs and create:
            self.config.table_view_configs[key] = SqliteTableViewConfigModel()
        return self.config.table_view_configs.get(key)

    def _current_table_view_key(self) -> str:
        directory_path = self.current_directory_path()
        database_path = self.current_database_path()
        table_name = self.current_table_name()
        if not directory_path or not database_path or not table_name:
            return ""
        return self.TABLE_KEY_SEPARATOR.join(
            [directory_path, database_path, table_name]
        )

    @staticmethod
    def _favorite_scope_order(scope: str) -> int:
        if scope == SqliteQueryPage.FAVORITE_SCOPE_GLOBAL:
            return 0
        if scope == SqliteQueryPage.FAVORITE_SCOPE_DATABASE:
            return 1
        if scope == SqliteQueryPage.FAVORITE_SCOPE_TABLE:
            return 2
        return 9

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

    def _default_favorite_name(self, scope: str, table_name: str) -> str:
        if scope == self.FAVORITE_SCOPE_TABLE and table_name:
            return f"{table_name}-常用查询"
        if scope == self.FAVORITE_SCOPE_DATABASE:
            database_name = os.path.basename(self.current_database_path()) or "当前库"
            return f"{database_name}-常用查询"
        return "常用查询"

    @staticmethod
    def _page_count(total_rows: int, page_size: int) -> int:
        normalized_page_size = max(1, int(page_size or 1))
        normalized_total = max(0, int(total_rows or 0))
        return max(1, math.ceil(normalized_total / normalized_page_size))

    @staticmethod
    def _directory_path_for_database(database_path: str) -> str:
        if not database_path:
            return ""
        return os.path.dirname(database_path)

    def _build_directory_label_map(self) -> dict[str, str]:
        work_dirs = [os.path.normpath(path) for path in SearchConfig.read_work_dir() or []]
        part_map: dict[str, list[str]] = {}
        depth_map: dict[str, int] = {}

        for scanned_directory in self.scanned_directories:
            directory_path = os.path.normpath(scanned_directory.directory_path)
            matched_root = self._matched_work_dir(directory_path, work_dirs)
            parts = self._path_parts_from_root(directory_path, matched_root)
            part_map[directory_path] = parts
            depth_map[directory_path] = 1

        if not part_map:
            return {}

        while True:
            grouped: dict[str, list[str]] = {}
            for directory_path, parts in part_map.items():
                current_depth = min(depth_map[directory_path], len(parts))
                label = os.path.join(*parts[-current_depth:]) if parts else directory_path
                grouped.setdefault(label, []).append(directory_path)

            duplicated = [paths for paths in grouped.values() if len(paths) > 1]
            if not duplicated:
                break

            progressed = False
            for duplicate_paths in duplicated:
                for directory_path in duplicate_paths:
                    if depth_map[directory_path] < len(part_map[directory_path]):
                        depth_map[directory_path] += 1
                        progressed = True
            if not progressed:
                break

        labels: dict[str, str] = {}
        grouped: dict[str, list[str]] = {}
        for directory_path, parts in part_map.items():
            current_depth = min(depth_map[directory_path], len(parts))
            label = os.path.join(*parts[-current_depth:]) if parts else directory_path
            labels[directory_path] = label
            grouped.setdefault(label, []).append(directory_path)

        for duplicate_paths in grouped.values():
            if len(duplicate_paths) <= 1:
                continue
            for directory_path in duplicate_paths:
                labels[directory_path] = directory_path
        return labels

    @staticmethod
    def _matched_work_dir(directory_path: str, work_dirs: list[str]) -> str:
        best_match = ""
        normalized_directory = os.path.normpath(directory_path)
        for work_dir in work_dirs:
            normalized_work_dir = os.path.normpath(work_dir)
            try:
                common = os.path.commonpath([normalized_directory, normalized_work_dir])
            except ValueError:
                continue
            if os.path.normcase(common) != os.path.normcase(normalized_work_dir):
                continue
            if len(normalized_work_dir) > len(best_match):
                best_match = normalized_work_dir
        return best_match

    @staticmethod
    def _path_parts_from_root(directory_path: str, work_dir: str) -> list[str]:
        normalized_directory = os.path.normpath(directory_path)
        normalized_work_dir = os.path.normpath(work_dir) if work_dir else ""
        if normalized_work_dir:
            try:
                relative = os.path.relpath(normalized_directory, normalized_work_dir)
            except ValueError:
                relative = normalized_directory
            relative_parts = [
                part for part in relative.split(os.sep) if part and part != "."
            ]
            root_name = (
                os.path.basename(normalized_work_dir.rstrip("\\/")) or normalized_work_dir
            )
            return [root_name, *relative_parts] if relative_parts else [root_name]
        return [
            part for part in normalized_directory.split(os.sep) if part and part != "."
        ] or [normalized_directory]

    def _format_directory_label(
        self,
        scanned_directory: SqliteScannedDirectoryModel,
    ) -> str:
        directory_path = os.path.normpath(scanned_directory.directory_path)
        directory_name = self._directory_label_map.get(directory_path) or (
            os.path.basename(directory_path.rstrip("\\/")) or directory_path
        )
        database_count = len(scanned_directory.database_files or [])
        return f"{directory_name} ({database_count} 库)"

    @staticmethod
    def _format_database_label(file_name: str, size: int) -> str:
        if size <= 0:
            return file_name
        if size < 1024:
            size_text = f"{size} B"
        elif size < 1024 * 1024:
            size_text = f"{size / 1024:.1f} KB"
        else:
            size_text = f"{size / 1024 / 1024:.2f} MB"
        return f"{file_name} ({size_text})"

    def _update_selection_summary(self):
        directory_text = self.current_directory_path() or "-"
        database_text = self.current_database_path() or "-"
        table_text = self.current_table_name() or "-"
        if self.current_query_mode == "sql":
            self.current_table_label.setText("当前结果：SQL 查询")
        else:
            self.current_table_label.setText(f"当前表：{table_text}")
        self.current_table_label.setToolTip(
            f"目录：{directory_text}\n数据库：{database_text}\n表：{table_text}"
        )
        self.directory_combo.setToolTip(directory_text)
        self.database_combo.setToolTip(database_text)
        self.table_combo.setToolTip(table_text)

    def _refresh_work_dir_summary(self):
        work_dirs = SearchConfig.read_work_dir()
        try:
            depth = int(SearchConfig.read().max_depth)
        except Exception:
            depth = 3
        if not work_dirs:
            self.work_dir_btn.setText("添加工作目录")
            self.work_dir_btn.setToolTip(
                "当前未设置工作目录。请先添加目录并设置递归深度，再扫描 SQLite。"
            )
            return
        joined_dirs = "；".join(work_dirs)
        self.work_dir_btn.setText(f"工作目录 ({len(work_dirs)})")
        self.work_dir_btn.setToolTip(
            f"当前共 {len(work_dirs)} 个工作目录，递归深度 {depth}：{joined_dirs}"
        )

    def _restore_saved_selection(self):
        self._populate_directory_combo(self.config.last_directory_path)
        if self.current_directory_path():
            self._on_directory_changed()
            return
        self._refresh_favorite_combo()

    def _save_config(self):
        SqliteQueryConfig.save_config(self.config)

    def _set_status(self, text: str):
        self.status_label.setText(f"状态：{text}")

    def _handle_error(self, message: str):
        self._set_status(f"错误：{message}")
        QMessageBox.warning(self, "错误", str(message))

    def _start_worker(self, fn, on_finished, on_error=None):
        worker = Worker(fn)
        self._workers.append(worker)

        def handle_finished(result):
            try:
                on_finished(result)
            finally:
                self._cleanup_worker(worker)

        def handle_error(message):
            try:
                if on_error is not None:
                    on_error(message)
                else:
                    self._handle_error(message)
            finally:
                self._cleanup_worker(worker)

        worker.signals.finished.connect(handle_finished)
        worker.signals.error.connect(handle_error)
        self.pool.start(worker)

    def _cleanup_worker(self, worker: Worker):
        if worker in self._workers:
            self._workers.remove(worker)
