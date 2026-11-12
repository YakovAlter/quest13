import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import csv
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
import uuid
import os



class ValidationError(ValueError):
    def __init__(self, field, message):
        super().__init__(message)
        self.field = field

@dataclass
class Item:
    id: str
    name: str
    category: str
    quantity: int
    price: float
    location: str
    created_at: str

def validate_item_data(data: dict) -> Item:
    item_id = data.get("id", "").strip()
    if not item_id:
        item_id = str(uuid.uuid4())[:8]

    name = data.get("name", "").strip()
    if not name:
        raise ValidationError("name", "Назва не може бути порожньою")
    
    category = data.get("category", "").strip()
    if not category:
        raise ValidationError("category", "Категорія не може бути порожньою")

    try:
        quantity = int(data.get("quantity", 0))
        if quantity < 0:
            raise ValueError()
    except ValueError:
        raise ValidationError("quantity", "Кількість має бути цілим числом ≥ 0")

    try:
        price_str = str(data.get("price", "0")).replace(",", ".")
        price = float(price_str)
        if price < 0:
            raise ValueError()
    except ValueError:
        raise ValidationError("price", "Ціна має бути числом ≥ 0")

    location = data.get("location", "").strip()
    created_at = data.get("created_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return Item(item_id, name, category, quantity, price, location, created_at)



class ItemRepository(ABC):
    @abstractmethod
    def all(self) -> list[Item]: pass
    
    @abstractmethod
    def get(self, item_id: str) -> Item | None: pass
    
    @abstractmethod
    def add(self, item: Item) -> None: pass
    
    @abstractmethod
    def update(self, item: Item) -> None: pass
    
    @abstractmethod
    def remove(self, item_id: str) -> None: pass
    
    @abstractmethod
    def clear(self) -> None: pass

    @abstractmethod
    def load_from_file(self, path: str) -> None: pass

    @abstractmethod
    def save_to_file(self, path: str) -> None: pass



class InventoryService:
    def __init__(self, repo: ItemRepository):
        self._repo = repo

    def get_all(self):
        return self._repo.all()

    def search(self, text: str):
        query = text.strip().lower()
        if not query:
            return self.get_all()
        return [
            item for item in self._repo.all()
            if query in item.name.lower() or query in item.category.lower()
        ]

    def add_item(self, form_data: dict) -> Item:
        item = validate_item_data(form_data)
        if self._repo.get(item.id):
            raise ValidationError("id", "Товар з таким ID вже існує")
        self._repo.add(item)
        return item

    def update_item(self, form_data: dict) -> Item:
        item = validate_item_data(form_data)
        if not self._repo.get(item.id):
            raise ValidationError("id", "Товар не знайдено для оновлення")
        self._repo.update(item)
        return item

    def delete_item(self, item_id: str):
        self._repo.remove(item_id)

    def load_data(self, path: str):
        self._repo.load_from_file(path)

    def save_data(self, path: str):
        self._repo.save_to_file(path)



class CsvItemRepository(ItemRepository):
    FIELDS = ["id", "name", "category", "quantity", "price", "location", "created_at"]

    def __init__(self, default_path: str = "inventory.csv"):
        self._items: dict[str, Item] = {}
        self.default_path = default_path
        if os.path.exists(default_path):
            self.load_from_file(default_path)

    def all(self) -> list[Item]:
        return list(self._items.values())

    def get(self, item_id: str) -> Item | None:
        return self._items.get(item_id)

    def add(self, item: Item):
        self._items[item.id] = item
        self.save_to_file(self.default_path)

    def update(self, item: Item):
        self._items[item.id] = item
        self.save_to_file(self.default_path)

    def remove(self, item_id: str):
        if item_id in self._items:
            del self._items[item_id]
            self.save_to_file(self.default_path)
            
    def clear(self):
        self._items.clear()

    def load_from_file(self, path: str):
        self.clear()
        try:
            with open(path, encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    item = validate_item_data(row)
                    self._items[item.id] = item
            self.default_path = path
        except FileNotFoundError:
            pass
        except Exception as e:
            raise ValueError(f"Помилка читання CSV: {e}")

    def save_to_file(self, path: str):
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self.FIELDS)
            writer.writeheader()
            for item in self.all():
                writer.writerow(item.__dict__)
        self.default_path = path



class TkinterApp:
    def __init__(self, root: tk.Tk, service: InventoryService):
        self.root = root
        self.service = service
        self.root.title("Система обліку товарів")
        self.root.geometry("1000x600")
        
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("Error.TEntry", fieldbackground="#ffd6d6")
        
        self.fields = ["id", "name", "category", "quantity", "price", "location"]
        self.form_vars = {field: tk.StringVar() for field in self.fields}
        self.form_vars["created_at"] = tk.StringVar()
        
        self._build_menu()
        self._build_ui()
        self._refresh_table()

    def _build_menu(self):
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Відкрити...", command=self.on_open)
        file_menu.add_command(label="Зберегти", command=self.on_save)
        file_menu.add_command(label="Зберегти як...", command=self.on_save_as)
        menubar.add_cascade(label="Файл", menu=file_menu)
        self.root.config(menu=menubar)

    def _build_ui(self):
        self.root.rowconfigure(1, weight=1)
        self.root.columnconfigure(0, weight=1)

        search_frame = ttk.Frame(self.root, padding=10)
        search_frame.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Label(search_frame, text="Пошук:").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self._refresh_table())
        ttk.Entry(search_frame, textvariable=self.search_var, width=40).pack(side="left", padx=10)

        cols = ("id", "name", "category", "quantity", "price", "location")
        self.tree = ttk.Treeview(self.root, columns=cols, show="headings", selectmode="browse")
        for c in cols:
            self.tree.heading(c, text=c.capitalize(), command=lambda _c=c: self._sort_table(_c))
            self.tree.column(c, width=100)
        self.tree.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        
        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.grid(row=1, column=1, sticky="ns", pady=10)

        form_frame = ttk.Frame(self.root, padding=10)
        form_frame.grid(row=1, column=2, sticky="n")
        
        self.entries = {}
        for idx, field in enumerate(self.fields):
            ttk.Label(form_frame, text=field.capitalize()).grid(row=idx, column=0, sticky="w", pady=5)
            entry = ttk.Entry(form_frame, textvariable=self.form_vars[field])
            entry.grid(row=idx, column=1, sticky="ew", pady=5, padx=5)
            self.entries[field] = entry

        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=len(self.fields), column=0, columnspan=2, pady=15)
        ttk.Button(btn_frame, text="Додати", command=self.on_add).grid(row=0, column=0, padx=2, pady=2)
        ttk.Button(btn_frame, text="Оновити", command=self.on_update).grid(row=0, column=1, padx=2, pady=2)
        ttk.Button(btn_frame, text="Видалити", command=self.on_delete).grid(row=1, column=0, padx=2, pady=2)
        ttk.Button(btn_frame, text="Очистити", command=self.on_clear).grid(row=1, column=1, padx=2, pady=2)

        self.status_var = tk.StringVar(value="Готово")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief="sunken", anchor="w")
        status_bar.grid(row=2, column=0, columnspan=3, sticky="ew")

    def _reset_styles(self):
        for entry in self.entries.values():
            entry.configure(style="TEntry")

    def _get_form_data(self):
        return {field: var.get() for field, var in self.form_vars.items()}

    def _refresh_table(self):
        self.tree.delete(*self.tree.get_children())
        items = self.service.search(self.search_var.get())
        for item in items:
            self.tree.insert("", "end", iid=item.id, values=(
                item.id, item.name, item.category, item.quantity, item.price, item.location
            ))

    def _sort_table(self, col, reverse=False):
        rows = [(self.tree.set(iid, col), iid) for iid in self.tree.get_children()]
        if col in ("quantity", "price"):
            rows.sort(key=lambda r: float(r[0]), reverse=reverse)
        else:
            rows.sort(key=lambda r: r[0].lower(), reverse=reverse)
        
        for pos, (_, iid) in enumerate(rows):
            self.tree.move(iid, "", pos)
        self.tree.heading(col, command=lambda: self._sort_table(col, not reverse))

    def on_select(self, event):
        self._reset_styles()
        selected = self.tree.selection()
        if not selected:
            return
        item_id = selected[0]
        item = self.service._repo.get(item_id) # Отримуємо актуальний об'єкт з пам'яті
        if item:
            self.form_vars["id"].set(item.id)
            self.form_vars["name"].set(item.name)
            self.form_vars["category"].set(item.category)
            self.form_vars["quantity"].set(str(item.quantity))
            self.form_vars["price"].set(str(item.price))
            self.form_vars["location"].set(item.location)
            self.form_vars["created_at"].set(item.created_at)

    def on_add(self):
        self._reset_styles()
        try:
            item = self.service.add_item(self._get_form_data())
            self._refresh_table()
            self.on_clear()
            self.status_var.set(f"Додано товар: {item.name}")
        except ValidationError as e:
            if e.field in self.entries:
                self.entries[e.field].configure(style="Error.TEntry")
            self.status_var.set(f"Помилка: {e}")

    def on_update(self):
        self._reset_styles()
        try:
            item = self.service.update_item(self._get_form_data())
            self._refresh_table()
            self.status_var.set(f"Оновлено товар: {item.name}")
        except ValidationError as e:
            if e.field in self.entries:
                self.entries[e.field].configure(style="Error.TEntry")
            self.status_var.set(f"Помилка: {e}")

    def on_delete(self):
        item_id = self.form_vars["id"].get()
        if not item_id:
            self.status_var.set("Оберіть товар для видалення")
            return
        if messagebox.askyesno("Підтвердження", f"Видалити товар {item_id}?"):
            self.service.delete_item(item_id)
            self._refresh_table()
            self.on_clear()
            self.status_var.set("Товар видалено")

    def on_clear(self):
        self._reset_styles()
        for var in self.form_vars.values():
            var.set("")
        self.tree.selection_remove(self.tree.selection())

    def on_open(self):
        path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
        if path:
            try:
                self.service.load_data(path)
                self._refresh_table()
                self.status_var.set(f"Дані завантажено з {os.path.basename(path)}")
            except Exception as e:
                messagebox.showerror("Помилка", str(e))

    def on_save(self):
        try:
            # Зберігаємо у поточний файл адаптера
            self.service._repo.save_to_file(self.service._repo.default_path)
            self.status_var.set("Дані успішно збережено")
        except Exception as e:
            messagebox.showerror("Помилка", str(e))

    def on_save_as(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if path:
            try:
                self.service.save_data(path)
                self.status_var.set(f"Дані експортовано у {os.path.basename(path)}")
            except Exception as e:
                messagebox.showerror("Помилка", str(e))



if __name__ == "__main__":
    repo = CsvItemRepository("inventory.csv")
    
    service = InventoryService(repo)
    
    root = tk.Tk()
    app = TkinterApp(root, service)
    
    root.mainloop()