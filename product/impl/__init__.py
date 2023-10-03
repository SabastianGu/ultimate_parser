from inspect import isclass
from pkgutil import iter_modules
from pathlib import Path
from importlib import import_module

from scene_parser import print_debug
from scene_parser.product import ProductBase


def get_product_parsers() -> []:
    result = []

    scan_dir = Path(__file__).resolve().parent
    print_debug(f'Сканируем {scan_dir}')
    for (_, module_name, _) in iter_modules([str(scan_dir)]):

        print_debug(f'Просматриваем {__name__}.{module_name}')
        module = import_module(f"{__name__}.{module_name}")

        for attribute_name in dir(module):
            attribute = getattr(module, attribute_name)

            if isclass(attribute) and issubclass(attribute, ProductBase):
                if attribute.__name__ != 'ProductBase':
                    print_debug(f'Найден класс {attribute.__name__}')
                    print_debug(f'\tИмя продукта: {attribute.get_product_name()}')
                    print_debug(f'\tПоддерживаемые расширения: {",".join(attribute.get_supported_extensions())}')
                    result.append(attribute)

    print_debug('')
    return result