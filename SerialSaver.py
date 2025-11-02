import serial

def read_from_com_port(port_name, output_filename):
    lines = []
    try:
        with serial.Serial(port=port_name, baudrate=9600, timeout=1) as ser:
            while True:
                line = ser.readline().decode('utf-8').rstrip('\r\n')
                lines.append(line)
                if line == 'EOF':
                    break
    except serial.SerialException as e:
        print(f"Ошибка открытия порта: {e}")

    # Удаляем пустые строки
    non_empty_lines = [line for line in lines if line.strip() != '']

    # Записываем непустые строки в файл
    with open(output_filename, 'w', encoding='utf-8') as file:
        for line in non_empty_lines:
            file.write(line + '\n')


if __name__ == "__main__":
    port_name = "COM11"
    output_filename = "input.dxf"
    read_from_com_port(port_name, output_filename)