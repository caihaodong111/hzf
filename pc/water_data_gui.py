"""
国家水质数据爬取工具 - GUI版本
使用tkinter创建图形界面
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import csv
import json
import requests
import urllib3
from datetime import datetime
import re

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class WaterDataGUI:
    """水质数据爬取GUI"""

    def __init__(self, root):
        self.root = root
        self.root.title("国家水质数据爬取工具")
        self.root.geometry("900x700")
        self.root.resizable(True, True)

        # API客户端
        self.base_url = "https://szzdjc.cnemc.cn:8070"
        self.api_url = f"{self.base_url}/GJZ/Ajax/Publish.ashx"
        self.session = requests.Session()
        self.session.verify = False

        # 数据存储
        self.current_data = []
        self.current_headers = []
        self.is_running = False

        # 区域和流域数据
        self.areas = {
            "全国": "",
            "北京市": "110000", "天津市": "120000", "河北省": "130000",
            "山西省": "140000", "内蒙古自治区": "150000", "辽宁省": "210000",
            "吉林省": "220000", "黑龙江省": "230000", "上海市": "310000",
            "江苏省": "320000", "浙江省": "330000", "安徽省": "340000",
            "福建省": "350000", "江西省": "360000", "山东省": "370000",
            "河南省": "410000", "湖北省": "420000", "湖南省": "430000",
            "广东省": "440000", "广西壮族自治区": "450000", "海南省": "460000",
            "重庆市": "500000", "四川省": "510000", "贵州省": "520000",
            "云南省": "530000", "西藏自治区": "540000", "陕西省": "610000",
            "甘肃省": "620000", "青海省": "630000", "宁夏回族自治区": "640000",
            "新疆维吾尔自治区": "650000"
        }

        self.rivers = {
            "所有流域": "",
            "长江流域": "1100000000",
            "黄河流域": "0900000000",
            "珠江流域": "1500000000",
            "松花江流域": "0200000000",
            "淮河流域": "1000000000",
            "海河流域": "6010000000",
            "辽河流域": "0500000000",
            "浙闽片河流": "ZMP",
            "西南诸河": "6040000000",
            "西北诸河": "0800000000",
            "太湖流域": "1200000000",
            "巢湖流域": "1300000000",
            "滇池流域": "1700000000"
        }

        self._create_widgets()

    def _create_widgets(self):
        """创建界面组件"""
        # 主容器
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ===== 参数设置区域 =====
        param_frame = ttk.LabelFrame(main_frame, text="参数设置", padding="10")
        param_frame.pack(fill=tk.X, pady=(0, 10))

        # 第一行：区域和流域
        row1 = ttk.Frame(param_frame)
        row1.pack(fill=tk.X, pady=5)

        ttk.Label(row1, text="区域:", width=8).pack(side=tk.LEFT)
        self.area_var = tk.StringVar(value="全国")
        area_combo = ttk.Combobox(row1, textvariable=self.area_var, values=list(self.areas.keys()),
                                   state="readonly", width=20)
        area_combo.pack(side=tk.LEFT, padx=5)

        ttk.Label(row1, text="流域:", width=8).pack(side=tk.LEFT, padx=(20, 0))
        self.river_var = tk.StringVar(value="所有流域")
        river_combo = ttk.Combobox(row1, textvariable=self.river_var, values=list(self.rivers.keys()),
                                    state="readonly", width=20)
        river_combo.pack(side=tk.LEFT, padx=5)

        # 第二行：搜索关键词
        row2 = ttk.Frame(param_frame)
        row2.pack(fill=tk.X, pady=5)

        ttk.Label(row2, text="断面搜索:", width=8).pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(row2, textvariable=self.search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=5)

        # 第三行：分页设置
        row3 = ttk.Frame(param_frame)
        row3.pack(fill=tk.X, pady=5)

        ttk.Label(row3, text="每页数量:", width=8).pack(side=tk.LEFT)
        self.page_size_var = tk.StringVar(value="60")
        page_size_spin = ttk.Spinbox(row3, from_=10, to=200, textvariable=self.page_size_var, width=10)
        page_size_spin.pack(side=tk.LEFT, padx=5)

        ttk.Label(row3, text="最大页数:", width=8).pack(side=tk.LEFT, padx=(20, 0))
        self.max_pages_var = tk.StringVar(value="10")
        max_pages_spin = ttk.Spinbox(row3, from_=1, to=100, textvariable=self.max_pages_var, width=10)
        max_pages_spin.pack(side=tk.LEFT, padx=5)

        # 第四行：操作按钮
        row4 = ttk.Frame(param_frame)
        row4.pack(fill=tk.X, pady=10)

        self.start_btn = ttk.Button(row4, text="开始爬取", command=self.start_fetch, width=15)
        self.start_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = ttk.Button(row4, text="停止", command=self.stop_fetch, width=15, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        ttk.Button(row4, text="清空数据", command=self.clear_data, width=15).pack(side=tk.LEFT, padx=5)

        # ===== 进度显示区域 =====
        progress_frame = ttk.LabelFrame(main_frame, text="进度信息", padding="10")
        progress_frame.pack(fill=tk.X, pady=(0, 10))

        self.progress_var = tk.StringVar(value="就绪")
        ttk.Label(progress_frame, textvariable=self.progress_var).pack(anchor=tk.W)

        self.progress_bar = ttk.Progressbar(progress_frame, mode='indeterminate')
        self.progress_bar.pack(fill=tk.X, pady=(5, 0))

        # ===== 数据预览区域 =====
        preview_frame = ttk.LabelFrame(main_frame, text="数据预览", padding="10")
        preview_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # 创建Treeview表格
        tree_frame = ttk.Frame(preview_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        # 滚动条
        vsb = ttk.Scrollbar(tree_frame, orient="vertical")
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal")

        # 表格
        self.tree = ttk.Treeview(tree_frame, yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        vsb.config(command=self.tree.yview)
        hsb.config(command=self.tree.xview)

        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree.pack(fill=tk.BOTH, expand=True)

        # 状态栏
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X)

        self.status_var = tk.StringVar(value="共 0 条记录")
        ttk.Label(status_frame, textvariable=self.status_var).pack(side=tk.LEFT)

        # 保存按钮
        ttk.Button(status_frame, text="导出CSV", command=self.export_csv).pack(side=tk.RIGHT, padx=5)
        ttk.Button(status_frame, text="导出JSON", command=self.export_json).pack(side=tk.RIGHT, padx=5)

    def clean_value(self, value, col_index=None):
        """清理数据值"""
        if not value or value == "--":
            return ""

        if isinstance(value, str):
            # 处理监测时间（第4列，索引3）- 添加年份
            if col_index == 3 and re.match(r'^\d{2}-\d{2}\s+\d{2}:\d{2}$', value):
                current_year = datetime.now().year
                return f"{current_year}-{value}"

            span_match = re.search(r"<span[^>]*title='([^']*)'[^>]*>(.*?)</span>", value)
            if span_match:
                return span_match.group(2).strip()
            value = re.sub(r'<br/>.*', '', value)
            value = re.sub(r'<[^>]+>', '', value)
            return value.strip()

        return str(value)

    def get_real_data(self, area_id="", river_id="", mn_name="", page_index=1, page_size=60):
        """获取数据"""
        params = {
            "action": "getRealDatas",
            "AreaID": area_id,
            "RiverID": river_id,
            "MNName": mn_name,
            "PageIndex": page_index,
            "PageSize": page_size
        }

        try:
            response = self.session.post(self.api_url, data=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return None

    def start_fetch(self):
        """开始爬取"""
        if self.is_running:
            return

        # 获取参数
        area_name = self.area_var.get()
        river_name = self.river_var.get()
        area_id = self.areas.get(area_name, "")
        river_id = self.rivers.get(river_name, "")
        mn_name = self.search_var.get().strip()

        try:
            page_size = int(self.page_size_var.get())
            max_pages = int(self.max_pages_var.get())
        except ValueError:
            messagebox.showerror("错误", "页数和每页数量必须是数字")
            return

        # 清空当前数据
        self.current_data = []
        self.current_headers = []
        self._clear_tree()

        # 更新UI状态
        self.is_running = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.progress_bar.start()

        # 在新线程中执行爬取
        thread = threading.Thread(
            target=self._fetch_thread,
            args=(area_id, river_id, mn_name, max_pages, page_size, area_name, river_name)
        )
        thread.daemon = True
        thread.start()

    def _fetch_thread(self, area_id, river_id, mn_name, max_pages, page_size, area_name, river_name):
        """爬取线程"""
        all_data = []
        total_pages = 0

        try:
            for page_index in range(1, max_pages + 1):
                if not self.is_running:
                    break

                self.root.after(0, lambda p=page_index: self.progress_var.set(f"正在获取第 {p} 页..."))

                data = self.get_real_data(
                    area_id=area_id,
                    river_id=river_id,
                    mn_name=mn_name,
                    page_index=page_index,
                    page_size=page_size
                )

                if not data or not data.get("result"):
                    break

                tbody = data.get("tbody", [])
                if not tbody:
                    break

                # 获取表头
                if page_index == 1:
                    self.current_headers = data.get("thead", [])
                    self.root.after(0, self._setup_tree_columns)

                all_data.extend(tbody)
                total_pages = data.get("total", 1)

                # 更新表格显示
                self.root.after(0, lambda rows=tbody: self._add_tree_rows(rows))

                if page_index >= total_pages:
                    break

            self.current_data = all_data

            # 完成
            self.root.after(0, lambda: self._fetch_complete(len(all_data), len(all_data)))

        except Exception as e:
            self.root.after(0, lambda: self._fetch_error(str(e)))

    def _setup_tree_columns(self):
        """设置表格列"""
        # 清空现有列
        self.tree['columns'] = []
        self.tree.delete(*self.tree.get_children())

        # 清理表头
        clean_headers = []
        for h in self.current_headers[:10]:  # 只显示前10列
            h_clean = re.sub(r'<br/>.*', '', h)
            clean_headers.append(h_clean)

        # 设置列
        self.tree['columns'] = clean_headers

        # 设置列标题
        for col in clean_headers:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100, anchor=tk.W)

    def _add_tree_rows(self, rows):
        """添加数据行"""
        for row in rows:
            clean_row = [self.clean_value(cell, i) for i, cell in enumerate(row[:10])]
            self.tree.insert('', tk.END, values=clean_row)

    def _clear_tree(self):
        """清空表格"""
        for item in self.tree.get_children():
            self.tree.delete(item)

    def _fetch_complete(self, count, total):
        """爬取完成"""
        self.is_running = False
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.progress_bar.stop()
        self.progress_var.set(f"完成！共获取 {count} 条记录")
        self.status_var.set(f"共 {count} 条记录")

    def _fetch_error(self, error):
        """爬取错误"""
        self.is_running = False
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.progress_bar.stop()
        self.progress_var.set("爬取失败")
        messagebox.showerror("错误", f"爬取失败: {error}")

    def stop_fetch(self):
        """停止爬取"""
        self.is_running = False
        self.progress_var.set("正在停止...")

    def clear_data(self):
        """清空数据"""
        self.current_data = []
        self.current_headers = []
        self._clear_tree()
        self.status_var.set("共 0 条记录")
        self.progress_var.set("数据已清空")

    def export_csv(self):
        """导出CSV"""
        if not self.current_data:
            messagebox.showwarning("警告", "没有数据可导出")
            return

        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV文件", "*.csv"), ("所有文件", "*.*")],
            initialfile=f"water_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )

        if filename:
            try:
                # 清理表头
                clean_headers = []
                for h in self.current_headers:
                    h_clean = re.sub(r'<br/>.*', '', h)
                    clean_headers.append(h_clean)

                # 清理数据
                rows = []
                for row in self.current_data:
                    clean_row = [self.clean_value(cell, i) for i, cell in enumerate(row)]
                    rows.append(clean_row)

                # 保存CSV
                with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    writer.writerow(clean_headers)
                    writer.writerows(rows)

                messagebox.showinfo("成功", f"数据已导出到:\n{filename}")
            except Exception as e:
                messagebox.showerror("错误", f"导出失败: {e}")

    def export_json(self):
        """导出JSON"""
        if not self.current_data:
            messagebox.showwarning("警告", "没有数据可导出")
            return

        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")],
            initialfile=f"water_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )

        if filename:
            try:
                # 清理数据
                clean_data = []
                for row in self.current_data:
                    clean_row = [self.clean_value(cell, i) for i, cell in enumerate(row)]
                    clean_data.append(clean_row)

                output = {
                    "headers": [re.sub(r'<br/>.*', '', h) for h in self.current_headers],
                    "data": clean_data,
                    "count": len(clean_data),
                    "export_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }

                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(output, f, ensure_ascii=False, indent=2)

                messagebox.showinfo("成功", f"数据已导出到:\n{filename}")
            except Exception as e:
                messagebox.showerror("错误", f"导出失败: {e}")


def main():
    """主函数"""
    root = tk.Tk()
    app = WaterDataGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()
