import struct
from typing import Optional


class MaxDocumentSummaryParser:
    """
    Разбирает содержимое потока \x05DocumentSummaryInfo
    """

    # Храним заголовок, вдруг потребуется
    _header = None

    # Список групп и их содержимого
    _result = dict()

    def __init__(self, stream):
        self._result = dict()

        # Считываем заголовок
        self._header = stream.read(200)

        # Находим в нём разделитель
        pos = self._header.find(b'\x1E\x00\x00\x00')

        # Разделитель обязательно должен быть выровнен по четному байту
        # Если это не так, то нам попались данные
        while pos % 2 != 0:
            pos = self._header.find(b'\x1E\x00\x00\x00', pos+1)

        # Переходим к разделителю
        stream.seek(pos)

        # Считываем разделитель
        buf = stream.read(4)
        delimiter, = struct.unpack('<I', buf)

        # Начинаем вести суммарное кол-во детей
        total_children = 0

        # Пока нам нам встречается правильный разделитель мы читаем названия групп
        while delimiter == 0x1e:
            # Считываем длину строки
            buf = stream.read(4)
            length, = struct.unpack('<I', buf)

            # Добавляем выравнивание
            length += (4 -(stream.tell() + length) % 4) % 4

            # Готовим формат строка
            fmt = f'<{length}s'
            # Считываем
            buf = stream.read(length)
            name, = struct.unpack(fmt, buf)

            # Имя может содержать символы \0 в конце для выравнивания. Удаляем их
            # А может быть в UTF-16. Мы ожидаем в этом блоке латиницу, так что просто удаляем все \0
            name = name.replace(b'\x00', b'').decode(errors='backslashreplace')

            # Если строка пуста, то флагов и количества детей не будет
            if len(name) == 0:
                # Считываем разделитель
                buf = stream.read(4)
                delimiter, = struct.unpack('<I', buf)
                continue

            # Считываем флаги
            buf = stream.read(4)
            flags, = struct.unpack('<I', buf)

            if flags == 0x1e:
                delimiter = flags
                continue

            # Считываем количество детей
            buf = stream.read(4 + 4)
            count, delimiter = struct.unpack('<II', buf)

            if flags != 0x03:
                count = 0

            self._result[name] = {
                'flags': flags,
                'count': count,
                'items': []
            }

            total_children += count

        # Нам встретился другой разделитель
        # Убедимся, что дальше идёт список детей

        if delimiter != 0x101e:
            raise ValueError(f'Неверный разделитель: {delimiter:08X}')

        # Считываем суммарное количество детей
        buf = stream.read(4)
        children_count, = struct.unpack('<I', buf)

        # Проверяем, что не просчитались
        if children_count != total_children:
            raise ValueError(f'Число детей не совпадает! Ожидалось {total_children}, получено {children_count}')

        # Проходим по всем группам и читаем детей
        for name in self._result:
            for i in range(self._result[name]['count']):
                # Считываем длину строки
                buf = stream.read(4)
                length, = struct.unpack('<I', buf)
                # Добавляем выравнивание
                length += (4 - (stream.tell() + length) % 4) % 4
                # Считываем строку
                buf = stream.read(length)
                # Зачищаем строку
                buf = buf.replace(b'\x00', b'').decode(errors='backslashreplace')

                self._result[name]['items'].append(buf)

        # Делаем секцию Render Data красивой
        self._make_render_data_pretty()

    def _get_general_section(self) -> Optional[dict]:
        names = [
            'General',
            'Allgemein',
            '\u4e00\u822c'
        ]
        for name in names:
            if name in self._result:
                return self._result[name]
        return None

    def get_plugins(self) -> list:
        """
        Возвращает список плагинов
        """
        plugins_strings = [
            'Used Plug-Ins',
            'Verwendete Plug-Ins',
            '\u4f7f\u7528\u3057\u3066\u3044\u308b\u30d7\u30e9\u30b0\u30a4\u30f3'
        ]
        for s in plugins_strings:
            if s in self._result:
                return self._result[s]['items']
        return []

    def get_renderer_name(self) -> Optional[str]:
        """
        Возвращает имя рендер-движка
        """
        if 'Render Data' in self._result:
            if 'Renderer Name' in self._result['Render Data']:
                return self._result['Render Data']['Renderer Name']

        return None

    def get_version(self) -> Optional[str]:
        """
        Возвращает версию, в которой сохранён проект
        """
        versions = {}

        # Получаем секцию General
        section = self._get_general_section()
        if section is None:
            return None

        # Разбираем каждое поле секции General
        for item in section['items']:
            data = item.split(': ', 1)
            if len(data) != 2:
                continue
            versions[data[0]] = data[1]

        version_strings = [
            # Первым приоритетом добываем Saved As
            'Saved As Version',
            'Gespeichert als Version',
            '\u30d0\u30fc\u30b8\u30e7\u30f3\u3068\u3057\u3066\u4fdd\u5b58',
            # Если не получилось узнать формат, в котором сохранили, то забираем версию макса, в которой сохранили
            '3ds Max Version',
            '3ds Max-Version',
            '3ds Max \u30d0\u30fc\u30b8\u30e7\u30f3 ',
            # Если и так не сработало, добываем из сборки
            'Build',
            '\u30d3\u30eb\u30c9 '
        ]

        for s in version_strings:
            if s in versions:
                try:
                    version = int(versions[s][:2])-2
                    return f'20{version}'
                except:
                    pass

        # Ничего не сработало
        return None

    def _make_render_data_pretty(self) -> None:
        """
        Парсит каждый элемент блока Render Data по символу '=' и добавляет в родителя
        """
        if not 'Render Data' in self._result:
            return None

        # Создаём массив для камер
        self._result['Render Data']['Render Cameras'] = []

        # Проходим по всем детям
        for item in self._result['Render Data']['items']:
            key, value = item.split('=', 1)

            # Не камера ли нам встретилась?
            if key.startswith('Render Camera'):
                self._result['Render Data']['Render Cameras'].append(value)
                continue

            # Может быть это число?
            try:
                self._result['Render Data'][key] = int(value)
                continue
            except ValueError:
                # Нет, не число
                pass

            self._result['Render Data'][key] = value

        # Сбрасываем исходный массив items
        self._result['Render Data'].pop('items')
        self._result['Render Data'].pop('count')

    def get_cameras(self) -> []:
        """
        Возвращает массив имён камер
        """
        if 'Render Data' not in self._result:
            return []
        return self._result['Render Data']['Render Cameras']

    def get_resolution(self) -> tuple:
        """
        Возвращает пару значений ширина, высота
        """
        if 'Render Data' not in self._result:
            return None, None
        width = self._result['Render Data']['Render Width']
        height = self._result['Render Data']['Render Height']
        return width, height

    def get_duration(self):
        """
        Возвращает тройку значений старт, конец, nthFrame
        """
        if 'Render Data' not in self._result:
            return None, None, None
        start = self._result['Render Data']['Animation Start']
        finish = self._result['Render Data']['Animation End']
        try:
            nth = self._result['Render Data']['Nth Frame']
        except KeyError:
            nth = 1

        return start, finish, nth

    def get_render_output(self) -> Optional[str]:
        if 'Render Data' not in self._result:
            return None
        if 'Render Output' in self._result['Render Data']:
            return self._result['Render Data']['Render Output']
        return None

    def get_render_gamma(self) -> tuple:
        if 'Render Data' not in self._result:
            return None, None
        input = None
        if 'Render Input Gamma' in self._result['Render Data']:
            data = self._result['Render Data']['Render Input Gamma']
            try:
                input = float(data.replace(',', '.'))
            except ValueError:
                pass
        output = None
        if 'Render Output Gamma' in self._result['Render Data']:
            data = self._result['Render Data']['Render Output Gamma']
            try:
                output = float(data.replace(',', '.'))
            except ValueError:
                pass
        return input, output
