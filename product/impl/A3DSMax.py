import struct

import olefile

from scene_parser.exception.invalid_magic import InvalidMagicException
from scene_parser.parser.max_document_summary import MaxDocumentSummaryParser
from scene_parser.parser.max_chunk_parser import MaxChunkParser
from scene_parser import print_debug
from scene_parser.product import ProductBase


class A3DSMax(ProductBase):
    @staticmethod
    def get_product_name() -> str:
        return 'Autodesk 3DS Max'

    @staticmethod
    def get_supported_extensions() -> []:
        return ['max']

    def __init__(self, file):
        ProductBase.__init__(self, file)

    # OLE-архив, из которого открываем потоки
    _ole = None

    # Поток, из которого читаем
    _stream = None

    # Здесь хранится результат парсинга
    _result = None

    def extract(self) -> dict:
        self._result = {
            'product': '3dsmax'
        }
        try:
            self._ole = olefile.OleFileIO(self._file)
        except OSError:
            raise InvalidMagicException
        self._stream = self._ole.openstream('\x05DocumentSummaryInformation')

        p = MaxDocumentSummaryParser(self._stream)

        self._result['version'] = p.get_version()
        self._result['cameras'] = p.get_cameras()
        self._result['width'], self._result['height'] = p.get_resolution()
        self._result['firstFrame'], self._result['lastFrame'], self._result['nthFrame'] = p.get_duration()

        out = p.get_render_output()
        try:
            out = out.split('\\')[-1].split('/')[-1]
            self._result["outputName"] = out.split('.')[0]
            self._result["ext"] = out.split('.')[-1]
        except:
            self._result["outputName"] = None
            self._result["ext"] = None

        self._result['plugins'] = p.get_plugins()

        self._result['render'] = p.get_renderer_name()

        self._result['gammaIn'], self._result['gammaOut'] = p.get_render_gamma()
        if self._result['gammaIn'] is not None or self._result['gammaOut'] is not None:
            self._result['gammaCorrection'] = True
        else:
            self._result['gammaCorrection'] = False

        self._ole.close()
        return self._result
