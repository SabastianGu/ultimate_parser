from typing import TextIO


class MayaASCIIParser:

    _stream : TextIO

    def __init__(self, stream : TextIO):
        self._stream = stream
        self._handlers = {
            'requires': self._on_requires,
            'fileInfo': self._on_file_info,
            'createNode': self._on_create_node,
            'setAttr': self._on_set_attr,
            'select': self._on_select
        }

    # Некоторые команды учитывают "контекст". Для них будем хранить информацию о последней ноде
    _previous_node = None

    # Регистрируем обработчики известных комманд
    _handlers: dict

    # Результат
    _result: dict

    # Словарь сопоставлений
    _requested: dict

    def _parse_type(self, value):
        """
        Приводит к правильному типу
        """
        if isinstance(value, dict):
            return value

        try:
            if value[0] == '"' and value[-1] == '"':
                return value[1:-1]
        except IndexError:
            pass

        try:
            return int(value)
        except ValueError:
            pass

        try:
            return float(value)
        except ValueError:
            pass

        return value

    def _add_to_result(self, path, value):
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
            self._result[key].append(self._parse_type(value))
        else:
            # Не является, перезаписываем
            self._result[key] = self._parse_type(value)

    def _parse_args(self, args: str) -> list:
        """
        Разбирает строку на аргументы.
        """
        result = []

        i = 0
        separator = ' '
        arg = ''
        while i < len(args):
            if args[i] == ' ':
                if separator == ' ':
                    result.append(arg)
                    arg = ''
                else:
                    arg += args[i]
            elif args[i] == '"':
                if separator == '"':
                    separator = ' '
                else:
                    separator = '"'
            elif args[i] == '\\':
                arg += args[i]
                i += 1
                arg += args[i]
            else:
                arg += args[i]

            i += 1
        result.append(arg)
        return result

    def _on_requires(self, args):
        a = self._parse_args(args)
        # Исключаем подключение модуля maya
        if a[-2] == 'maya':
            return
        # Здесь остались только плагины
        value = {
            'name': a[-2],
            'version': a[-1]
        }
        self._add_to_result('requires', value)

    def _on_file_info(self, args):
        a = self._parse_args(args)
        self._add_to_result(f'fileInfo/{a[-2]}', a[-1])

    def _on_create_node(self, args):
        a = self._parse_args(args)
        if a[0] == 'camera':
            i = 0
            name = ''
            while i < len(a):
                if a[i] == '-p':
                    name = a[i+1]
                i += 1

            self._add_to_result(f'createNode/camera', name)
            self._previous_node = None
        else:
            self._previous_node = None

    def _on_set_attr(self, args):
        if self._previous_node is None:
            return
        if self._previous_node.startswith('select/'):
            a = self._parse_args(args)
            # FIXME: Не для всех типов подходит такая выборка. Однако, пока норм.
            self._add_to_result(f'{self._previous_node}{a[0]}', a[-1])

    def _on_select(self, args):
        a = self._parse_args(args)
        i = 0
        name = ''
        while i < len(a):
            if a[i] == '-ne':
                name = a[i + 1]
            i += 1

        self._previous_node = f'select/{name}'

    def _on_comment(self, string):
        pass

    def parse(self, requested: dict):
        self._result = {}

        self._requested = requested

        # Инициализируем пустые массивы
        for key in self._requested:
            value = self._requested[key]
            if value.endswith('[]'):
                value = value[:-2]
                self._result[value] = []
        # Считываем по командам
        while True:
            line = self._stream.readline()

            if not line:
                # Больше считывать нечего
                return self._result

            if line.startswith('//'):
                # Комментарий
                self._on_comment(line)
                continue

            # Нам встретилась команда. Затираем перенос строки
            line = line.lstrip().rstrip('\r\n')
            # И считываем её до тех пор, пока не встретим ';'
            while line[-1] != ';':
                data = self._stream.readline()
                # Если файл закончился раньше, чем пришла точка с запятой
                # То считаем эту строчку битой и не пытаемся парсить
                if len(data) == 0:
                    break
                line += data.lstrip().rstrip('\r\n')

            # Проверяем, что строка корректна
            if line[-1] != ';':
                # Иначе возвращаемся в начало
                continue
            # И в конце затираем ;
            line = line[:-1]

            # Разбиваем на команду и аргументы
            cmd, args = line.split(' ', 1)

            # Проверяем, есть ли обработчик на такую команду
            if cmd in self._handlers:
                self._handlers[cmd](args)


