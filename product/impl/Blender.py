import struct
import blendfile
import json
import binascii
import olefile
import bpy

from scene_parser.exception.invalid_magic import InvalidMagicException
from scene_parser import print_debug
from scene_parser.product import ProductBase


def get_ext_by_(id) -> tuple:
    if id is None:
        return id, None
    try:
        id = int(id)
    except ValueError:
        return id, None
    if id == 0:
        return id, 'tagra'
    if id == 1:
        return id, 'iris'
    if id == 2:
        return id, 'hamx'
    if id == 3:
        return id, 'ftype'
    if id == 4:
        return id, 'jpeg90'
    if id == 5:
        return id, 'movie'
    if id == 7:
        return id, 'iriz'
    if id == 14:
        return id, 'tga_raw'
    if id == 15:
        return id, 'avi_raw'
    if id == 16:
        return id, 'avi_jpeg'
    if id == 17:
        return id, 'png'
    if id == 20:
        return id, 'bmp'
    if id == 21:
        return id, 'hdr'
    if id == 22:
        return id, 'tiff'
    if id == 23:
        return id, 'open_exr'
    if id == 24:
        return id, 'ffmpeg'
    if id == 25:
        return id, 'frameserver'
    if id == 26:
        return id, 'cineon'
    if id == 27:
        return id, 'dpx'
    if id == 29:
        return id, 'dds'
    if id == 30:
        return id, 'jp2'
    if id == 31:
        return id, 'h264'
    if id == 32:
        return id, 'xvid'
    if id == 33:
        return id, 'theora'
    if id == 34:
        return id, 'psd'
    return id, None


def get_engine_by_(id):
    if id is None:
        return id, None
    try:
        id = int(id)
    except ValueError:
        return id, None
    return id, None


# Код для парсинга новых blend файлов
def extract_from_new_blend(filepath):
        with bpy.data.libraries.load(filepath) as (data_from, data_to):
            pass


        render_settings = bpy.context.scene.render
        engine = None
        for scene in bpy.data.scenes:
            if scene.render.engine != 'BLENDER_EEVEE':
                engine = scene.render.engine
                break
        if engine == "":
            engine = 'CYCLES'
        
        version_string = bpy.app.version_string.split()
        product = version_string[0]
        version = version_string[1] if len(version_string) >= 2 else '3.5'

        # Get the frame range settings
        frame_start = bpy.context.scene.frame_start
        frame_end = bpy.context.scene.frame_end
        frame_step = bpy.context.scene.frame_step

        # Get the resolution settings
        resolution_x = render_settings.resolution_x
        resolution_y = render_settings.resolution_y

        #the render engine
       # engine = render_settings.engine

        # Get the output settings
        output_path = render_settings.filepath
        output_format = render_settings.views_format
        output_extension = '.' + output_format.lower()

        # camera list
        cameras = [obj.name for obj in bpy.data.objects if obj.type == 'CAMERA']
        execution_time = '0.20'

        #result dictionary
        prefix = 'BLENDER_'
        if engine == None:
            render_value = 'CYCLES'
        elif prefix in engine:
            render_value = engine[len(prefix):]
        result = {
            "product": 'blender',
            "version": product,
            "firstFrame": frame_start,
            "lastFrame": frame_end,
            "nthFrame": frame_step,
            "width": resolution_x,
            "height": resolution_y,
            "render": render_value,
            "outputName": output_path,
            "ext": output_extension,
            "cameras": cameras,
            "execution_time": execution_time
        }

        return result

class Blender(ProductBase):
    @staticmethod
    def get_product_name() -> str:
        return 'Blender'

    @staticmethod
    def get_supported_extensions() -> list:
        return ['blend']

    def __init__(self, file):
        ProductBase.__init__(self, file)

    # Здесь хранится результат парсинга
    _result = None


    ### Also, may try repairing existing code with snippets from https://formats.kaitai.io/blender_blend/python.html.

    def extract(self) -> dict:
        try:
            blend = blendfile.open_blend(self._file)
            print(blend)

            scene = None
            self._result = {
            'product': 'blender'
            }

            for block in blend.blocks:
                if block.code == b'SC':
                    scene = block
                    break

            version = str(blend.header.version)
            self._result['version'] = version[0] + '.' + version[1:]

            self._result['firstFrame'] = scene.get((b'r', b'sfra'))
            self._result['lastFrame'] = scene.get((b'r', b'efra'))
            self._result['nthFrame'] = scene.get((b'r', b'frame_step'), 1)
            self._result['width'] = scene.get((b'r', b'xsch'))
            self._result['height'] = scene.get((b'r', b'ysch'))
            self._result['render'] = scene.get((b'r', b'engine'), None)
            if self._result['render'] is not None:
                self._result['render'] = self._result['render'].replace('BLENDER_', '')

            output = scene.get((b'r', b'pic'))
            self._result['outputName'] = output.split("\\")[-1]

            imtype = scene.get((b'r', b'im_format', b'imtype'), None)
            if imtype is None:
                imtype = scene.get((b'r', b'imtype'), None)
            self._result['ext_id'], self._result['ext'] = get_ext_by_(imtype)
            if self._result['ext'] is not None:
                self._result.pop('ext_id')

            self._result['cameras'] = []
            for block in blend.blocks:
                if block.code == b'OB':
                    if block.get(b'type') == 11:
                        name = block.get((b'id', b'name'))[2:]
                        self._result['cameras'].append(name)

        except Exception:
            #Нужно добавить bpy вот в этом самом месте
            self._result = extract_from_new_blend(self._file)
            if self._result is None:
                raise InvalidMagicException
        return self._result
        

    def extract_from_hex(self: str) -> dict:
    # Convert hex string to byte string
        byte_string = bytes.fromhex(self)
        print(byte_string)
    # Parse byte string as blend file
        blend = blendfile.from_string(byte_string)

        scene = None
        result = {
            'product': 'blender'
    }

        for block in blend.blocks:
            if block.code == b'SC':
                scene = block
            break

        version = str(blend.header.version)
        result['version'] = version[0] + '.' + version[1:]

        result['firstFrame'] = scene.get((b'r', b'sfra'))
        result['lastFrame'] = scene.get((b'r', b'efra'))
        result['nthFrame'] = scene.get((b'r', b'frame_step'), 1)
        result['width'] = scene.get((b'r', b'xsch'))
        result['height'] = scene.get((b'r', b'ysch'))
        result['render'] = scene.get((b'r', b'engine'), None)
        if result['render'] is not None:
            result['render'] = result['render'].replace('BLENDER_', '')

        output = scene.get((b'r', b'pic'))
        result['outputName'] = output.split("\\")[-1]

        imtype = scene.get((b'r', b'im_format', b'imtype'), None)
        if imtype is None:
            imtype = scene.get((b'r', b'imtype'), None)
        result['ext_id'], result['ext'] = get_ext_by_(imtype)
        if result['ext'] is not None:
            result.pop('ext_id')

        result['cameras'] = []
        for block in blend.blocks:
            if block.code == b'OB':
                if block.get(b'type') == 11:
                    name = block.get((b'id', b'name'))[2:]
                    result['cameras'].append(name)

    # Convert result to JSON
        json_string = json.dumps(result)

    # Parse JSON to a dictionary
        result_dict = json.loads(json_string)

        return result_dict