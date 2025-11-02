import ezdxf
import numpy as np
from collections import defaultdict
from ezdxf import recover


def load_contour(filename):
    """Загружает контур из DXF файла и соединяет линии в замкнутый контур"""
    try:
        # 🔹 Безопасное открытие DXF — восстанавливает повреждённые или нестандартные файлы
        doc, auditor = recover.readfile(filename)
        if auditor.has_errors:
            print(f"⚠ Найдены ошибки в DXF, но файл восстановлен ({len(auditor.errors)} ошибок)")

        msp = doc.modelspace()
        print(f"Анализ DXF файла...")
        print(f"Всего объектов в модели: {len(msp)}")

        segments = []
        endpoints = defaultdict(list)

        for i, entity in enumerate(msp):
            dtype = entity.dxftype()

            try:
                if dtype == "LINE":
                    start = (round(entity.dxf.start[0], 6), round(entity.dxf.start[1], 6))
                    end = (round(entity.dxf.end[0], 6), round(entity.dxf.end[1], 6))
                    segments.append((start, end))
                    endpoints[start].append(end)
                    endpoints[end].append(start)
                    print(f"Линия: {start} -> {end}")

                elif dtype in ("POLYLINE", "LWPOLYLINE"):
                    points = []

                    if dtype == "POLYLINE":
                        for vertex in entity.vertices:
                            points.append(
                                (round(vertex.dxf.location[0], 6), round(vertex.dxf.location[1], 6))
                            )
                    else:  # LWPOLYLINE
                        for x, y, *_ in entity.lwpoints:
                            points.append((round(x, 6), round(y, 6)))

                    if len(points) < 2:
                        continue

                    # Создаем сегменты между вершинами
                    for p1, p2 in zip(points, points[1:]):
                        segments.append((p1, p2))
                        endpoints[p1].append(p2)
                        endpoints[p2].append(p1)

                    # Замыкаем полилинию, если она закрыта
                    if getattr(entity, "closed", False):
                        p1, p2 = points[-1], points[0]
                        segments.append((p1, p2))
                        endpoints[p1].append(p2)
                        endpoints[p2].append(p1)

                    print(f"Полилиния ({dtype}): {len(points)} вершин")

            except Exception as e:
                print(f"⚠ Ошибка при чтении объекта {dtype}: {e}")

        if not segments:
            print("❌ Не найдено линий для построения контура")
            return None

        print(f"Найдено отрезков: {len(segments)}")

        contour = reconstruct_contour(segments, endpoints)
        if contour is not None:
            print(f"Восстановлен контур с {len(contour)} точками")
            return np.array(contour)
        else:
            print("❌ Не удалось восстановить замкнутый контур")
            return None

    except Exception as ex:
        print(f"Ошибка при загрузке контура: {ex}")
        import traceback
        traceback.print_exc()
        return None


def reconstruct_contour(segments, endpoints):
    """Восстанавливает замкнутый контур из отдельных отрезков"""
    if not segments:
        return None

    start_point, next_point = segments[0]
    contour = [start_point, next_point]
    used_segments = set([0])
    current_point = next_point

    while len(contour) < len(segments) + 1:
        found_next = False

        for i, (p1, p2) in enumerate(segments):
            if i in used_segments:
                continue

            if np.allclose(current_point, p1, atol=1e-6):
                contour.append(p2)
                current_point = p2
                used_segments.add(i)
                found_next = True
                break
            elif np.allclose(current_point, p2, atol=1e-6):
                contour.append(p1)
                current_point = p1
                used_segments.add(i)
                found_next = True
                break

        if not found_next:
            break

        if np.allclose(current_point, contour[0], atol=1e-6):
            print("Контур успешно замкнут!")
            return contour

    print(f"⚠ Построен контур с {len(contour)} точками, но не замкнут")
    return contour


def create_hatch_lines(contour, step=5.0, angle=0):
    """Создает линии штриховки для заполнения контура"""
    try:
        if not np.allclose(contour[0], contour[-1], atol=1e-6):
            contour = np.vstack([contour, contour[0]])

        angle_rad = np.deg2rad(angle)
        rotation_matrix = np.array([
            [np.cos(angle_rad), -np.sin(angle_rad)],
            [np.sin(angle_rad), np.cos(angle_rad)]
        ])

        rotated_contour = np.dot(rotation_matrix, contour.T).T
        min_y = np.min(rotated_contour[:, 1])
        max_y = np.max(rotated_contour[:, 1])

        lines = []
        y_levels = np.arange(min_y + step / 2, max_y, step)

        for y in y_levels:
            intersections = []
            for i in range(len(rotated_contour) - 1):
                p1 = rotated_contour[i]
                p2 = rotated_contour[i + 1]

                if abs(p1[1] - p2[1]) < 1e-10:
                    continue

                if (p1[1] <= y <= p2[1]) or (p2[1] <= y <= p1[1]):
                    t = (y - p1[1]) / (p2[1] - p1[1])
                    x = p1[0] + t * (p2[0] - p1[0])
                    intersections.append(x)

            intersections.sort()
            for i in range(0, len(intersections) - 1, 2):
                x1, x2 = intersections[i], intersections[i + 1]
                p1_rot = np.array([x1, y])
                p2_rot = np.array([x2, y])
                p1_orig = np.dot(rotation_matrix.T, p1_rot)
                p2_orig = np.dot(rotation_matrix.T, p2_rot)
                lines.append((p1_orig, p2_orig))

        print(f"Создано {len(lines)} линий штриховки")
        return lines

    except Exception as ex:
        print(f"Ошибка при создании линий штриховки: {ex}")
        import traceback
        traceback.print_exc()
        return None


def format_gcode(lines, z_up=5, z_down=0, feed_rate=1500):
    """Форматирует линии в G-код"""
    print("Генерация G-кода...")

    gcode = [
        "G21 ; Units in mm",
        "G90 ; Absolute positioning",
        f"G0 Z{z_up} F500",
        "G0 X0 Y0 F3000"
    ]

    if not lines:
        print("Ошибка: Нет линий для генерации G-кода")
        return None

    lines.sort(key=lambda line: (line[0][1], line[0][0]))

    for i, (start, end) in enumerate(lines):
        x1, y1 = start
        x2, y2 = end

        gcode.append(f"G0 X{x1:.3f} Y{y1:.3f} F3000")
        gcode.append(f"G1 Z{z_down} F500")
        gcode.append(f"G1 X{x2:.3f} Y{y2:.3f} F{feed_rate}")
        gcode.append(f"G1 Z{z_up} F500")

        if (i + 1) % 10 == 0:
            print(f"  Обработано {i + 1}/{len(lines)} линий")

    gcode.append("G0 X0 Y0")
    gcode.append("M30")

    print("G-код успешно сгенерирован")
    return "\n".join(gcode)


def main():
    try:
        print("=== Конвертер DXF в G-код ===")

        contour = load_contour("input_fixed.dxf")
        if contour is None:
            print("❌ Не удалось загрузить контур")
            return

        print(f"✓ Контур загружен: {len(contour)} точек")

        lines = create_hatch_lines(contour, step=2.0, angle=45)
        if lines is None:
            print("❌ Ошибка при создании линий штриховки")
            return

        print(f"✓ Линии штриховки созданы: {len(lines)} линий")

        gcode_text = format_gcode(lines)
        if gcode_text is None:
            print("❌ Ошибка при генерации G-кода")
            return

        with open("output.gcode", "w") as f:
            f.write(gcode_text)

        print("✅ Готово! G-код сохранен в 'output.gcode'")

    except Exception as ex:
        print(f"❌ Ошибка: {ex}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
