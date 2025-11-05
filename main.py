import ezdxf
import numpy as np
from collections import defaultdict

filename = "input_fixed.dxf"

def load_contours(filename):
    """Загружает все контуры из DXF файла"""
    try:
        doc = ezdxf.readfile(filename)
        msp = doc.modelspace()
        
        print(f"Анализ DXF файла...")
        print(f"Всего объектов в модели: {len(msp)}")
        
        contours = []
        
        for entity in msp:
            if entity.dxftype() == 'LWPOLYLINE':
                points = []
                for point in entity.get_points():
                    x, y = point[0], point[1]
                    points.append((x, y))
                
                if len(points) >= 3:
                    if entity.closed:
                        if not np.allclose(points[0], points[-1], atol=1e-6):
                            points.append(points[0])
                        contours.append(np.array(points))
                        print(f"LWPOLYLINE: замкнутый контур с {len(points)} точками")
                    else:
                        print(f"LWPOLYLINE: незамкнутый контур, игнорируется")
                        
            elif entity.dxftype() == 'POLYLINE':
                points = []
                for vertex in entity.vertices:
                    point = (vertex.dxf.location[0], vertex.dxf.location[1])
                    points.append(point)
                
                if len(points) >= 3:
                    if entity.is_closed:
                        if not np.allclose(points[0], points[-1], atol=1e-6):
                            points.append(points[0])
                        contours.append(np.array(points))
                        print(f"POLYLINE: замкнутый контур с {len(points)} точками")
                    else:
                        print(f"POLYLINE: незамкнутый контур, игнорируется")
        
        if not contours:
            print("Не найдено замкнутых контуров")
            return load_contours_from_lines(filename)
        
        print(f"Найдено контуров: {len(contours)}")
        return contours
        
    except Exception as ex:
        print(f"Ошибка при загрузке контуров: {ex}")
        import traceback
        traceback.print_exc()
        return None

def load_contours_from_lines(filename):
    """Загружает контуры из отдельных линий"""
    try:
        doc = ezdxf.readfile(filename)
        msp = doc.modelspace()
        
        print("Попытка восстановления контуров из отдельных линий...")
        
        segments = []
        endpoints = defaultdict(list)
        
        for entity in msp:
            if entity.dxftype() == 'LINE':
                start = (entity.dxf.start[0], entity.dxf.start[1])
                end = (entity.dxf.end[0], entity.dxf.end[1])
                segments.append((start, end))
                endpoints[start].append(end)
                endpoints[end].append(start)
        
        if not segments:
            print("Не найдено линий для построения контура")
            return None
        
        print(f"Найдено отрезков: {len(segments)}")
        
        contours = reconstruct_all_contours(segments, endpoints)
        print(f"Восстановлено контуров: {len(contours)}")
        return contours
        
    except Exception as ex:
        print(f"Ошибка при загрузке контуров из линий: {ex}")
        return None

def reconstruct_all_contours(segments, endpoints):
    """Восстанавливает все возможные контуры из отрезков"""
    if not segments:
        return []
    
    used_segments = set()
    contours = []
    segment_list = list(segments)
    
    for i in range(len(segment_list)):
        if i in used_segments:
            continue
            
        start_point, next_point = segment_list[i]
        contour = [start_point, next_point]
        used_segments.add(i)
        current_point = next_point
        contour_closed = False
        
        max_iterations = len(segment_list) * 2
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            found_next = False
            
            for j in range(len(segment_list)):
                if j in used_segments:
                    continue
                    
                p1, p2 = segment_list[j]
                
                if np.allclose(current_point, p1, atol=1e-6):
                    if np.allclose(p2, contour[0], atol=1e-6):
                        contour.append(contour[0])
                        contour_closed = True
                        used_segments.add(j)
                        break
                    
                    contour.append(p2)
                    current_point = p2
                    used_segments.add(j)
                    found_next = True
                    break
                elif np.allclose(current_point, p2, atol=1e-6):
                    if np.allclose(p1, contour[0], atol=1e-6):
                        contour.append(contour[0])
                        contour_closed = True
                        used_segments.add(j)
                        break
                    
                    contour.append(p1)
                    current_point = p1
                    used_segments.add(j)
                    found_next = True
                    break
            
            if not found_next or contour_closed:
                break
        
        if contour_closed or (len(contour) >= 3 and np.allclose(contour[0], contour[-1], atol=1e-6)):
            if len(contour) >= 4:
                contours.append(np.array(contour))
                print(f"  Замкнут контур с {len(contour)} точками")
        else:
            print(f"  Незамкнутый контур с {len(contour)} точками (игнорируется)")
    
    return contours

def create_hatch_lines_for_contours(contours, step=2.0):
    """Создает горизонтальные линии штриховки для нескольких контуров"""
    all_lines = []
    
    for i, contour in enumerate(contours):
        print(f"Создание штриховки для контура {i+1} ({len(contour)} точек)")
        
        lines = create_hatch_lines(contour, step)
        if lines:
            for line in lines:
                all_lines.append((line, i))
            print(f"  Добавлено {len(lines)} линий для контура {i+1}")
        else:
            print(f"  Не удалось создать штриховку для контура {i+1}")
    
    print(f"Всего линий штриховки: {len(all_lines)}")
    return all_lines

def create_hatch_lines(contour, step=2.0):
    """Создает горизонтальные линии штриховки для заполнения контура"""
    try:
        if not np.allclose(contour[0], contour[-1], atol=1e-6):
            contour = np.vstack([contour, contour[0]])
        
        # Горизонтальные линии (угол 0 градусов)
        min_y = np.min(contour[:, 1])
        max_y = np.max(contour[:, 1])
        
        lines = []
        
        y_levels = np.arange(min_y + step/2, max_y, step)
        
        for y in y_levels:
            intersections = []
            
            for i in range(len(contour) - 1):
                p1 = contour[i]
                p2 = contour[i + 1]
                
                if abs(p1[1] - p2[1]) < 1e-10:
                    continue
                
                if (p1[1] <= y <= p2[1]) or (p2[1] <= y <= p1[1]):
                    t = (y - p1[1]) / (p2[1] - p1[1])
                    x = p1[0] + t * (p2[0] - p1[0])
                    intersections.append(x)
            
            intersections.sort()
            for i in range(0, len(intersections) - 1, 2):
                if i + 1 < len(intersections):
                    x1, x2 = intersections[i], intersections[i + 1]
                    lines.append(((x1, y), (x2, y)))
        
        return lines
        
    except Exception as ex:
        print(f"Ошибка при создании линий штриховки: {ex}")
        import traceback
        traceback.print_exc()
        return None

def format_gcode(lines_with_contours, feed_rate=1500):
    """Форматирует линии в G-код с зигзагообразным движением"""
    print("Генерация G-кода...")
    
    gcode = []
    gcode.append("G21 ; Units in mm")
    gcode.append("G90 ; Absolute positioning")
    gcode.append("G0 X0 Y0 F3000")
    
    if not lines_with_contours:
        print("Ошибка: Нет линий для генерации G-кода")
        return None
    
    contour_groups = {}
    for line, contour_idx in lines_with_contours:
        if contour_idx not in contour_groups:
            contour_groups[contour_idx] = []
        contour_groups[contour_idx].append(line)
    
    print(f"Обработка {len(contour_groups)} контуров...")
    
    for contour_idx in sorted(contour_groups.keys()):
        print(f"Обработка контура {contour_idx + 1} ({len(contour_groups[contour_idx])} линий)")
        
        lines = contour_groups[contour_idx]
        gcode.extend(_process_contour_zigzag(lines, feed_rate, contour_idx))
        
        gcode.append(f"; === КОНТУР {contour_idx + 1} ЗАВЕРШЕН ===")
    
    gcode.append("G0 X0 Y0")
    gcode.append("M30")
    
    print("G-код успешно сгенерирован")
    return "\n".join(gcode)

def _process_contour_zigzag(lines, feed_rate, contour_idx):
    """Обрабатывает один контур в зигзагообразном режиме"""
    gcode = []
    gcode.append(f"; === НАЧАЛО КОНТУРА {contour_idx + 1} ===")
    
    line_data = []
    for start, end in lines:
        line_data.append({
            'start': start,
            'end': end,
            'reverse_start': end,
            'reverse_end': start
        })
    
    line_data.sort(key=lambda line: (line['start'][1], line['start'][0]))
    
    y_groups = {}
    for line in line_data:
        y_level = round(line['start'][1], 3)
        if y_level not in y_groups:
            y_groups[y_level] = []
        y_groups[y_level].append(line)
    
    sorted_y_levels = sorted(y_groups.keys())
    current_position = None
    
    for i, y_level in enumerate(sorted_y_levels):
        group_lines = y_groups[y_level]
        
        if i % 2 == 0:
            group_lines.sort(key=lambda line: line['start'][0])
            use_normal_direction = True
        else:
            group_lines.sort(key=lambda line: line['start'][0], reverse=True)
            use_normal_direction = False
        
        for j, line in enumerate(group_lines):
            if use_normal_direction:
                start = line['start']
                end = line['end']
            else:
                start = line['reverse_start']
                end = line['reverse_end']
            
            if j == 0:
                gcode.append(f"G0 X{start[0]:.3f} Y{start[1]:.3f} F3000")
            else:
                if current_position is not None:
                    distance = np.sqrt((start[0] - current_position[0])**2 + 
                                     (start[1] - current_position[1])**2)
                    if distance < 20.0:
                        gcode.append(f"G1 X{start[0]:.3f} Y{start[1]:.3f} F{feed_rate}")
                    else:
                        gcode.append(f"G0 X{start[0]:.3f} Y{start[1]:.3f} F3000")
                else:
                    gcode.append(f"G0 X{start[0]:.3f} Y{start[1]:.3f} F3000")
            
            gcode.append(f"G1 X{end[0]:.3f} Y{end[1]:.3f} F{feed_rate}")
            current_position = end
    
    return gcode

def main():
    try:
        print("=== Конвертер DXF в G-код ===")
        print("Горизонтальная штриховка с зигзагообразным движением")
        print("Стол не двигается (только перемещение по X/Y)")
        
        contours = load_contours(filename)
        
        if not contours:
            print("Не удалось загрузить контуры")
            return
        
        print(f"✓ Загружено контуров: {len(contours)}")
        
        # Создаем горизонтальные линии штриховки
        lines_with_contours = create_hatch_lines_for_contours(contours, step=5.0)
        
        if not lines_with_contours:
            print("Ошибка при создании линий штриховки")
            return
        
        print(f"✓ Линии штриховки созданы: {len(lines_with_contours)} линий")
        
        # Генерируем G-код
        gcode_text = format_gcode(lines_with_contours)
        if gcode_text is None:
            print("Ошибка при генерации G-кода")
            return
        
        with open("output.gcode", "w") as f:
            f.write(gcode_text)
        
        print("✓ Готово! G-код сохранен в 'output.gcode'")
        
    except Exception as ex:
        print(f"❌ Ошибка: {ex}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()