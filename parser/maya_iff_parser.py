import io
import struct
from typing import BinaryIO, Optional

from scene_parser.exception.invalid_magic import InvalidMagicException
from scene_parser import print_debug


class MayaIFFParser:
    """
    Парсер 32-х битных и 64-х битных IIF файлов
    """

    # Поток для чтения
    _stream: BinaryIO

    # Результат
    _result: dict

    # По каким путям ищем
    _requested: dict

    # Размер адрес в байтах
    _ptr_size: int

    # Идентификаторы чанков, которые являются списками
    _list_chunks = [
        b'FOR4',
        b'FOR8',
        b'SLCT'
    ]

    def __init__(self, stream: BinaryIO):
        """
        Конструктор. Принимается rb-поток
        """
        self._stream = stream
        # Проверяем магию
        buf = self._stream.read(4)
        if buf == b'FOR4':
            self._ptr_size = 4
            print_debug('Найден 32-х битный файл')
        elif buf == b'FOR8':
            self._ptr_size = 8
            print_debug('Найден 64-х битный файл')
        else:
            raise InvalidMagicException

        # Возвращаем на ноль
        self._stream.seek(0)

    def _add_to_result(self, prefix, key, value) -> None:
        """
        Добавляет в _result значение, если prefix/key указан в requested
        """
        # Добываем полный путь
        path = f'{prefix}/{key}'
        # Проверяем, есть ли он в requested
        if not path in self._requested:
            return
        # Достаём на что маппим
        key = self._requested[path]
        # проверяем, не является ли оно массивом
        if key.endswith('[]'):
            # Является. Отрезаем скобки
            key = key[:-2]
            # Создаём запись в result, если необходимо
            if not key in self._result:
                self._result[key] = []
            # Добавляем
            self._result[key].append(value)
        else:
            # Не является, перезаписываем
            self._result[key] = value

    def _read_header(self) -> tuple:
        """
        Считывает заголовок, возвращает (chunk_id, flags, size)
        """
        if self._ptr_size == 8:
            buf = self._stream.read(16)
            if len(buf) == 0:
                return None, None, None
            return struct.unpack(">4sLQ", buf)
        else:
            buf = self._stream.read(8)
            if len(buf) == 0:
                return None, None, None
            chunk_id, size = struct.unpack(">4sL", buf)
            return chunk_id, 0, size

    def _align(self, size) -> int:
        """
        Выравнивает по длине указателя. Возвращает насколько байт выровнял
        """
        align = (self._ptr_size - (size % self._ptr_size)) % self._ptr_size
        self._stream.seek(align, 1)
        return align

    def _read_slct(self) -> Optional[str]:
        """
        Читает чанк SLCT
        """
        id, flags, size = self._read_header()
        return self._stream.read(size).decode(errors='backslashreplace')

    def _read_chunk(self, prefix='') -> int:
        """
        Рекурсивно читает чанки.
        Возвращает число прочитанных байт
        """
        chunk_id, flags, size = self._read_header()

        if chunk_id is None:
            return -1

        if chunk_id in self._list_chunks:
            # Это список чанков
            # Считываем имя
            name = self._stream.read(4)
            # декодируем
            name = name.decode(errors='backslashreplace')

            # Имя входит в длину содержимого списка
            children_size = 4

            # Если имя SLCT, то первый чанк обязателельно типа SLCT с длинным названием списка
            if name == 'SLCT':
                name = self._read_slct()
                l = len(name)
                align = self._align(l)
                children_size += 16 + l + align

            # Проверяем, можем ли мы пропустить этот список
            list_path = f'{prefix}/{name}'
            skip = True
            for key in self._requested:
                if key.startswith(list_path):
                    skip = False
                    break

            if skip:
                self._stream.seek(size - children_size, 1)
                return 2 * self._ptr_size + 4 + size

            # Проходим по всем детям, выравнивая по размеру указателя
            while children_size < size:
                l = self._read_chunk(prefix + "/" + name)
                # Последний массив не полный, прерываемся
                if l == -1:
                    break
                align = self._align(l)
                children_size += l + align
            return 2*self._ptr_size + 4 + size
        elif chunk_id == b'DBLE':
            # Чанк со значением с плавающей запятой
            buf = self._stream.read(size)
            # Находим ноль-символ
            pos = buf.find(b'\x00')
            # Разбираем
            if len(buf) - pos - 2 == 8:
                # double, 8 байт
                key, value = struct.unpack(f'>{pos}sxxd', buf)
            elif len(buf) - pos - 2 == 4:
                # float, 4 байта
                key, value = struct.unpack(f'>{pos}sxxf', buf)
            else:
                # Неизвестно
                return 2 * self._ptr_size + size

            key = key.decode(errors='backslashreplace')
            self._add_to_result(prefix, key, value)
        elif chunk_id == b'STR ' or chunk_id == b'FINF':
            # Строковый чанк
            buf = self._stream.read(size)
            p = buf.find(b'\0')
            key = buf[:p].decode(errors='backslashreplace')
            offset = 1
            if chunk_id == b'STR ':
                # У STR есть лишний байт после \0, а у FINF -- нет
                offset = 2

            value = buf[p + offset:-1].decode(errors='backslashreplace')

            self._add_to_result(prefix, key, value)
        elif chunk_id == b'PLUG':
            # Чанк описания плагинов
            buf = self._stream.read(size)
            data = [x.strip(b'\x00').decode(errors='backslashreplace') for x in buf.split(b'\x00')]
            value = {
                'name': data[0],
                'version': data[1]
            }

            self._add_to_result(prefix, chunk_id.decode(), value)
        elif chunk_id == b'CREA':
            buf = self._stream.read(size)
            try:
                name = buf.split(b'\x00')[1].decode(errors='backslashreplace')
                self._add_to_result(prefix, chunk_id.decode(), name)
            except IndexError:
                pass
        else:
            # Неизвестный чанк, пропускаем
            self._stream.seek(size, 1)
        return 2*self._ptr_size + size

    def parse(self, requested: dict) -> dict:
        self._result = {}
        self._requested = requested

        # Инициализируем пустые массивы
        for key in self._requested:
            value = self._requested[key]
            if value.endswith('[]'):
                value = value[:-2]
                self._result[value] = []

        # Приступаем к чтению чанков
        self._read_chunk()

        return self._result
