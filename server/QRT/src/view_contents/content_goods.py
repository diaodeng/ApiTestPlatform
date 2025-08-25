import base64
import io
import sqlite3
from typing import List, Dict
import barcode
import flet as flt
from barcode.writer import ImageWriter


class Goods(object):
    """关于"""

    def __init__(self, ft, page, log, **kwargs):
        self.ft = ft
        self.page = page
        self.log = log
        self.page_size = 20
        self.current_page = 0
        self.file_path = ""
        self._is_loading = False
        self.table_name = "offline_ware_info"
        self.params = []
        self.conditions = {}
        self.offset = 0
        self.columns = []
        self.data = []

        self.goodsDB = kwargs.get("GoodsDB")
        self.setup_ui()

    def setup_ui(self):
        self.db = self.ft.Dropdown(
            editable=True,
            label="选择商品库",
            options=self.get_option(),
            on_change=self.dropdown_changed
        )
        self.rf = self.ft.TextField(
            label="物料码",
            hint_text="支持模糊搜索",
            width=150,
            on_change=lambda e: self._rf_search()
        )

        self.mc = self.ft.TextField(
            label="商品分类ID",
            hint_text="支持模糊搜索",
            width=150,
            on_change=lambda e: self._mc_search()
        )

        self.price = self.ft.TextField(
            label="单价",
            hint_text="支持模糊搜索",
            width=150,
            on_change=lambda e: self._price_search()
        )

        self.can_sale = self.ft.Checkbox("是否可售", value=True, on_change=lambda e: self._can_sale())

        self.grid = self.ft.GridView(
            expand=True,
            runs_count=5,
            max_extent=300,
            child_aspect_ratio=1.5,
            spacing=5,
            run_spacing=5,
            on_scroll=self._handle_scroll
        )

    def _can_sale(self):
        self.current_page = 0
        self.did_mount()

    def _price_search(self):
        self.current_page = 0
        if self.price.value is not None and self.price.value != "":
            self.conditions["price"] = self.price.value
        else:
            self.conditions.pop("price")
        self.did_mount()

    def _mc_search(self):
        self.current_page = 0
        if self.mc.value is not None and self.mc.value != "":
            self.conditions["mc_code"] = self.mc.value
        else:
            self.conditions.pop("mc_code")
        self.did_mount()

    def _rf_search(self):
        self.current_page = 0
        if self.rf.value is not None and self.rf.value != "":
            self.conditions["rf_id"] = self.rf.value
        else:
            self.conditions.pop("rf_id")
        self.did_mount()

    def _get_table_columns(self) -> List[str]:
        """获取表结构信息"""
        conn = sqlite3.connect(self.file_path)
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({self.table_name})")
        columns = [col[1] for col in cursor.fetchall()]
        conn.close()
        return columns

    def set_conditions(self):
        self.query = f"SELECT * FROM {self.table_name} where 1=1 "
        self.params.clear()
        if self.can_sale.value:
            self.query += " AND CAN_SALE = ?"
            self.params.append(1)
        else:
            self.query += " AND CAN_SALE = ?"
            self.params.append(0)
        if self.conditions.get('mc_code'):
            self.query += " AND MC_CODE LIKE ?"
            self.params.append(f"%{self.conditions['mc_code']}%")
        if self.conditions.get('price'):
            self.query += " AND RETAIL_PRICE LIKE ?"
            self.params.append(f"%{self.conditions['price']}%")
        if self.conditions.get('rf_id'):
            self.query += " AND RF_ID LIKE ?"
            self.params.append(f"%{self.conditions['rf_id']}")

        self.query += " LIMIT ? OFFSET ?"

        self.params.append(self.page_size)
        self.params.append(self.offset)

    def _load_data(self) -> List[Dict]:
        """分页查询数据"""
        self.offset = self.current_page * self.page_size
        conn = sqlite3.connect(self.file_path)
        cursor = conn.cursor()
        self.set_conditions()
        self.log.info(f"商品查询语句：{self.query}")
        self.log.info(f"查询参数：{self.params}")
        cursor.execute(self.query, self.params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(zip(self.columns, row)) for row in rows]

    def _handle_scroll(self, e: flt.OnScrollEvent):
        """滚动加载更多数据"""
        if e.pixels >= e.max_scroll_extent - 100 and not self._is_loading:  # 接近底部时加载
            self._is_loading = True
            self.current_page += 1
            new_data = self._load_data()
            if new_data:
                self.data.extend(new_data)
                self._update_grid()
                self.page.update()
            else:
                self.current_page -= 1
            self._is_loading = False

    def _update_grid(self):
        """更新Gridview显示"""
        self.grid.controls.clear()
        for item in self.data:
            # 行内紧凑布局组件
            def inline_row(label, value):
                return self.ft.Row(
                    controls=[
                        self.ft.Text(f"{label}:", width=60),
                        self.ft.Text(value, expand=1),
                        self.ft.IconButton(
                            icon=self.ft.Icons.CONTENT_COPY,
                            icon_size=14,
                            tooltip="复制",
                            height=20,
                            width=20,
                            on_click=lambda e, v=value: self.page.set_clipboard(str(v))
                        )
                    ],
                    spacing=0,
                    tight=True,
                    vertical_alignment="center"
                )

            self.grid.controls.append(
                self.ft.Container(
                    content=self.ft.Column([
                        self.ft.Image(src_base64=self.generate_barcode(item.get('RF_ID')),
                                      width=260, height=80),
                        self.ft.Text(item.get("TITLE", ""),
                                     weight="bold",
                                     max_lines=1,
                                     overflow="ellipsis"),
                        inline_row("物料码", item.get('RF_ID', 0)),
                        inline_row("国条码", item.get('ITEM_NUM', 0)),
                        inline_row("单 价", item.get('RETAIL_PRICE', 0))
                    ],
                        spacing=0,  # 关键参数：消除默认行距
                        tight=True),  # 关键参数：紧凑模式
                    padding=self.ft.padding.only(left=10, right=10, top=5, bottom=5),
                    border=self.ft.border.all(1, "black"),
                    bgcolor=self.ft.Colors.with_opacity(0.2, self.ft.Colors.GREY_300),
                    border_radius=10
                )
            )

    def generate_barcode(self, number):
        # 生成Code128格式条形码
        # 生成条形码到内存
        code = barcode.Code128(number, writer=ImageWriter())
        buffer = io.BytesIO()
        code.write(buffer, options={
            "write_text": False,
            "module_width": 0.6,
            "module_height": 18,
            # "font_size": 10,
            # "text_distance": 3,
            "quiet_zone": 12
        })

        # 转换为标准Base64字符串（不含前缀）
        b64_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return b64_str

    def did_mount(self):
        """初始加载数据"""
        self.data = self._load_data()
        self._update_grid()
        self.page.update()

    def get_option(self):
        options = []
        for goods in self.goodsDB:
            options.append(
                self.ft.DropdownOption(
                    key=f"{goods["env"]}-{goods["vendorName"]}-{goods['vendorId']}-{goods['storeId']}",
                    content=self.ft.Text(
                        value=f"{goods["env"]}-{goods["vendorName"]}-{goods['vendorId']}-{goods['storeId']}"
                    ),
                )
            )
        return options

    def dropdown_changed(self, e):
        vendorInfo = e.control.value.split("-")
        self.current_page = 0
        for vd in self.goodsDB:
            if vd.get("env") == vendorInfo[0] and str(vd.get("vendorId")) == vendorInfo[2] and str(vd.get("storeId")) == \
                    vendorInfo[3]:
                self.file_path = vd.get("filePath")
                self.columns = self._get_table_columns()
                self.did_mount()
                self.page.update()

    def goods(self):
        content = self.ft.Container(
            content=self.ft.Column([
                self.ft.Text("商品查询（离线）>", size=20),
                self.ft.Divider(),
                self.ft.Row([
                    self.db,
                    self.rf,
                    self.mc,
                    self.price,
                    self.can_sale
                ]),
                self.ft.Divider(),
                self.grid,
            ], alignment=self.ft.MainAxisAlignment.START),
            alignment=self.ft.alignment.center_left
        )
        return content
