import struct
from typing import Optional

from scene_parser.exception.invalid_magic import InvalidMagicException
from scene_parser import print_debug
from scene_parser.product import ProductBase


class Houdini(ProductBase):
    @staticmethod
    def get_product_name() -> str:
        return 'Houdini'

    @staticmethod
    def get_supported_extensions() -> []:
        return ['hip', 'hiplc']

    def __init__(self, file):
        ProductBase.__init__(self, file)

    # Поток, из которого читаем
    _stream = None

    # Здесь хранится результат парсинга
    _result = None

    # Переменные
    _variables = None

    # Допустимая магия файла
    _magic = [
        '070707',
        'HouLC\x1a'
    ]

    def _parse_variables(self, data):
        self._variables = {}
        for line in data.split('\n'):
            if line.startswith('set -g '):
                key_value = line[7:]
                key, value = key_value.split('=', 2)
                key = key.strip()
                value = value.strip()[1:-1]

                self._variables[key] = value

    def _parse_array(self, data):
        result = []

        i = 0
        value = ''
        while i < len(data):
            if data[i] == '\t':
                result.append(value)
                value = ''
            elif data[i:i+2] == '[ ':
                i += 2
                count = 1
                arr = ""
                while count != 0:
                    if i >= len(data):
                        return result
                    if data[i] == '[':
                        i += 1
                        count += 1
                    elif data[i:i+3] == ' ] ':
                        i += 2
                        count -= 1
                    else:
                        arr += data[i]
                    i += 1
                value = self._parse_array(arr)
                result.append(value)
                value = ''
            elif data[i:i+2] == ' ]':
                return result
            else:
                value += data[i]
            i += 1

        if isinstance(value, str) and len(value) > 1:
            if value[0] == '"' and value[-1] == '"':
                value = value[1:-1]

        result.append(value)
        return result

    def _eval(self, data):
        result = ''
        i = 0
        while i < len(data):
            if data[i] == '$':
                i += 1
                name = ''
                while data[i].isalnum():
                    name += data[i]
                    i += 1

                if name in self._variables:
                    result += self._variables[name]

                result += data[i]
            else:
                result += data[i]
            i += 1
        return result

    def _parse_render_path(self, path) -> Optional[str]:
        if 'hick' in path or 'htoa' in path:
            return 'arnold'
        return None

    def _parse_parms(self, node_name, data):

        parms = {}

        for line in data.split('\n'):
            if line == '{' or line == '' or line == '}':
                continue
            # Достаём имя
            pos = line.find('\t')
            name = line[:pos]
            line = line[pos+1:]

            # Достаем мета-данные
            pos = line.find(']\t(\t')
            meta = line[2:pos]
            line = line[pos+4:-2]

            # Разбираем данные
            data = self._parse_array(line)

            # Записываем в словарь
            parms[name] = data

        # Добываем необходимое
        result = {}

        result['renderNodeName'] = f'/out/{node_name}'

        self._variables['OS'] = node_name

        if 'soho_pipecmd' in parms:
            if parms['soho_pipecmd']:
                result['render'] = parms['soho_pipecmd'][0]
                if not isinstance(result['render'], str):
                    result['render_raw'] = result['render']
                    if isinstance(result['render'], list):
                        arr = result['render']
                        if len(arr) == 2 and arr[0] == 'soho_pipecmd':
                            result['render'] = self._parse_render_path(arr[1])
                        else    :
                            result['render'] = '<corrupted>'
                    else:
                        result['render'] = '<corrupted>'
            else:
                result['render'] = node_name.rstrip('1')
        else:
            result['render'] = node_name

        if 'f' in parms:
            print_debug(parms['f'])
            if isinstance(parms['f'][0], list):
                result['firstFrame'] = int(parms['f'][0][1])
            else:
                result['firstFrame'] = int(parms['f'][0])
            if isinstance(parms['f'][1], list):
                result['lastFrame'] = int(parms['f'][1][1])
            else:
                result['lastFrame'] = int(parms['f'][1])
            if isinstance(parms['f'][2], list):
                result['nthFrame'] = int(parms['f'][2][1])
            else:
                result['nthFrame'] = int(parms['f'][2])
            for i in range(1, 10):
                fmt = '{:0' + str(i) + '}'
                self._variables[f'F{i}'] = fmt.format(result['firstFrame'])
        else:
            result['firstFrame'] = None
            result['lastFrame'] = None
            result['nthFrame'] = None

        if 'res_override' in parms:
            if isinstance(parms['res_override'][0], list):
                result['width'] = parms['res_override'][0][1]
            else:
                result['width'] = parms['res_override'][0]

            if isinstance(parms['res_override'][1], list):
                result['height'] = parms['res_override'][1][1]
            else:
                result['height'] = parms['res_override'][1]

            try:
                result['width'] = int(result['width'])
                result['height'] = int(result['height'])
            except:
                pass
        else:
            result['width'] = None
            result['height'] = None

        if 'vm_picture' in parms:
            try:
                out = self._eval(parms['vm_picture'][0])
                out = out.split('/')[-1].split('\\')[-1]
                ext = out.split('.')[-1]
                out = "".join(out.split('.')[:-1])
                result['outputFile'] = out
                result['ext'] = ext
            except:
                result['outputFile'] = self._eval(parms['vm_picture'][0])
                result['ext'] = None
        else:
            result['outputFile'] = None
            result['ext'] = None

        return result

    def _read_header(self, magic) -> tuple:
        if magic == '070707':
            dev = self._stream.read(6)
            ino = self._stream.read(6)
            mode = self._stream.read(6)
            uid = self._stream.read(6)
            gid = self._stream.read(6)
            nlink = self._stream.read(6)
            rdev = self._stream.read(6)
            mtime = self._stream.read(11)
            namesize = int(self._stream.read(6), 8)
            filesize = int(self._stream.read(11), 8)
            # print(f'found name length: {namesize} bytes')
            filename = self._stream.read(namesize)
            # print(f'{filename} of size {filesize}')
            return filesize, filename
        elif magic == 'HouLC\x1a':
            flags = self._stream.read(28)
            filesize = None
            filename = ''
            c = ''
            while c != '\0':
                c = self._stream.read(1)
                filename += c
            return filesize, filename
        else:
            raise InvalidMagicException

    def _read_file(self, magic, filesize=None) -> str:
        if filesize is not None:
            return self._stream.read(filesize)
        else:
            data = ''
            delimiter = self._stream.read(6)
            while delimiter != magic:
                c = self._stream.read(1)
                if len(c) == 0:
                    return data
                data += delimiter[0]
                delimiter = delimiter[1:] + c
            self._stream.seek(self._stream.tell() - 6)
            return data

    def _skip_file(self, magic, filesize=None) -> None:
        if filesize is not None:
            self._stream.seek(self._stream.tell() + filesize)
        else:
            self._read_file(magic, filesize)

    def extract(self) -> dict:
        self._stream = open(self._file, 'r', errors='backslashreplace')

        self._result = {
            'product': 'houdini',
            'renderNodes': []
        }

        magic = self._stream.read(6)

        if magic == 'HouLC\x1a':
            print_debug('Houdini Limited Commercial')
            self._result['limitedCommercial'] = True
        elif magic == '070707':
            print_debug('Houdini Core/FX')
            self._result['limitedCommercial'] = False
        else:
            raise InvalidMagicException

        while magic in self._magic:

            filesize, filename = self._read_header(magic)

            if filename == '.variables\0':
                print_debug('Найден файл .variables')
                f = self._read_file(magic, filesize)
                self._parse_variables(f)
                if '_HIP_SAVEVERSION' in self._variables:
                    self._result['version'] = self._variables['_HIP_SAVEVERSION']
                else:
                    self._result['version'] = None
            elif filename.startswith('out/') and '.parm' in filename:
                node_name = filename[4:-6]
                print_debug(node_name)
                print_debug(f'Найдены параметры рендер-ноды {node_name}')
                f = self._read_file(magic, filesize)
                render_node = self._parse_parms(node_name, f)
                if render_node['render'] is not None:
                    self._result['renderNodes'].append(render_node)
            else:
                self._skip_file(magic, filesize)

            magic = self._stream.read(6)
            # print(f'>{magic}<')

        return self._result