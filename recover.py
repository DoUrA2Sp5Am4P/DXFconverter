from pathlib import Path
import re
import shutil

def add_missing_acdbpolyline(filename):
    path = Path(filename)
    backup = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(path, backup)
    print(f"🔁 Создан backup: {backup}")

    text = path.read_text(encoding="utf-8", errors="ignore")

    # вставляем подклассы AcDbEntity + AcDbPolyline сразу после LWPOLYLINE
    fixed_text, n = re.subn(
        r"(?m)(^0\s*\nLWPOLYLINE\s*\n)",
        "0\nLWPOLYLINE\n100\nAcDbEntity\n100\nAcDbPolyline\n",
        text
    )

    if n == 0:
        print("⚠ Не найдено ни одной LWPOLYLINE для исправления.")
        return

    fixed_path = path.with_name(path.stem + "_fixed" + path.suffix)
    fixed_path.write_text(fixed_text, encoding="utf-8", errors="ignore")
    print(f"✅ Исправлено LWPOLYLINE: {n} → добавлены блоки AcDbPolyline")
    print(f"💾 Сохранено как: {fixed_path}")

if __name__ == "__main__":
    add_missing_acdbpolyline("input.dxf")
