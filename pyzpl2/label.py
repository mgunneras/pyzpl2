#!/usr/bin/env python

#import Image
from PIL import Image
import re
import PIL.ImageOps
import sys
import math
import webbrowser
import urllib
import io

class Label:
    '''
    Used to build a ZPL2 label.

    all dimensions are given in millimeters and automatically converted to
    printer dot units.
    '''

    def __init__(self, height, width=110.0, dpmm=12.0):
        """
        Creates one (or more) ZPL2 labels.

        *height* and *width* are given in millimeters
        *dpmm* refers to dots per millimeter (e.g. 12 for 300dpi)
        """
        self.height = height
        self.width = width
        self.dpmm = dpmm

        self.code = "^XA"

    def origin(self, x,y):
        """
        new block located at x and y (in millimeters)
        """
        self.code += "^FO%i,%i" % (x*self.dpmm, y*self.dpmm)

    def endorigin(self):
        self.code += '^FS'

    def textblock(self, width, justification='C', lines=1):
        """
        new text block

        width of textblock in millimeters
        """
        assert justification in ['L','R','C','J']
        self.code += "^FB%i,%i,%i,%s,%i" % (width*self.dpmm, lines, 0, justification, 0)

    def write_text(self, text, char_height=None, char_width=None, font='0', orientation='N',
                   line_width=None, max_line=1, line_spaces=0, justification='L', hanging_indent=0):
        if char_height and char_width and font and orientation:
            assert re.match(r'[A-Z0-9]', font), "invalid font"
            assert orientation in 'NRIB', "invalid orientation"
            self.code += "^A%c%c,%i,%i" % (font, orientation, char_height*self.dpmm,
                                           char_width*self.dpmm)
        if line_width:
            assert justification in "LCRJ", "invalid justification"
            self.code += "^FB%i,%i,%i,%c,%i" % (line_width*self.dpmm, max_line, line_spaces,
                                                justification, hanging_indent)
        self.code += "^FD%s" % text

    def set_default_font(self, height, width, font='0'):
        """
        sets default font from here onward

        height and width are given in milimeters
        """
        assert re.match(r'[A-Z0-9]', font), "invalid font"
        self.code += "^CF%c,%i,%i" % (font, height*self.dpmm, width*self.dpmm)

    def _convert_image(self, image, width, height, compression_type='A'):
        '''
        converts *image* (of type PIL.Image) to a ZPL2 format

        compression_type can be one of ['A', 'B', 'C']

        returns data
        '''
        image = image.resize((int(width*self.dpmm), int(height*self.dpmm))).convert('1')
        # invert, otherwise we get reversed B/W
        for x in range(image.size[0]):
            for y in range(image.size[1]):
                image.putpixel((x,y), 255-image.getpixel((x,y)))

        if compression_type == "A":
            return image.tobytes().encode('hex').upper()
        # TODO this is not working
        #elif compression_type == "B":
        #    return image.tostring()
        else:
            raise Exception("unsupported compression type")


    def upload_graphic(self, name, image, width, height=0):
        """in millimeter"""
        if not height:
            height = int(float(image.size[1])/image.size[0]*width)

        assert 1 <= len(name) <= 8, "filename must have length [1:8]"

        totalbytes = math.ceil(width*self.dpmm/8.0)*height*self.dpmm
        bytesperrow = math.ceil(width*self.dpmm/8.0)

        data = self._convert_image(image, width, height)

        self.code += "~DG%s.GRF,%i,%i,%s" % (name, totalbytes, bytesperrow, data)

        return height

    def write_graphic(self, image, width, height=0, compression_type="A"):
        """
        embeddes image with given width

        image has to be of type PIL.Image
        if height is not given, it will be chosen proportionally
        """
        if not height:
            height = int(float(image.size[1])/image.size[0]*width)

        totalbytes = math.ceil(width*self.dpmm/8.0)*height*self.dpmm
        bytesperrow = math.ceil(width*self.dpmm/8.0)

        data = self._convert_image(image, width, height, compression_type=compression_type)

        if compression_type == "A":
            self.code += "^GFA,%i,%i,%i,%s" % (len(data), totalbytes, bytesperrow, data)
        # TODO this is not working:
        elif compression_type == "B":
            self.code += "^GFB,%i,%i,%i,%s" % (len(data), totalbytes, bytesperrow, data)
        else:
            raise Exception("Unsupported compression type.")

        return height

    def draw_box(self, width, height, thickness=1, color='B', rounding=0):
        assert color in 'BW', "invalid color"
        assert rounding <= 8, "invalid rounding"
        self.code += "^GB,%i,%i,%i,%c,%i" % (width, height, thickness, color, rounding)

    def draw_ellipse(self, width, height, thickness=1, color='B'):
        assert color in 'BW', "invalid color"
        self.code += "^GE,%i,%i,%i,%c" % (width, height, thickness, color)

    def print_graphic(self, name, scale_x=1, scale_y=1):
        self.code += "^XG%s,%i,%i" % (name, scale_x, scale_y)

    def run_script(self, filename):
        self.code += "^XF%s^FS"

    def write_field_number(self, number, name=None, char_height=None, char_width=None, font='0',
                           orientation='N', line_width=None, max_line=1, line_spaces=0,
                           justification='L', hanging_indent=0):
        if char_height and char_width and font and orientation:
            assert re.match(r'[A-Z0-9]', font), "invalid font"
            assert orientation in 'NRIB', "invalid orientation"
            self.code += "^A%c%c,%i,%i" % (font, orientation, char_height*self.dpmm,
                                           char_width*self.dpmm)
        if line_width:
            assert justification in "LCRJ", "invalid justification"
            self.code += "^FB%i,%i,%i,%c,%i" % (line_width*self.dpmm, max_line, line_spaces,
                                                justification, hanging_indent)
        self.code += "^FN%i" % number
        if name:
            assert re.match("^[a-zA-Z0-9 ]+$", name), "name may only contain alphanumerical " + \
                                                   "characters and spaces"
            self.code += '"%s"' % name

    def set_barcode_field_defaults(self, module_width=2, bar_width_ratio=3.0,
            bar_code_height=5):
        """
        module_width and bar_width_ratio are set in dot size.
        bar_code_height is set in mm.
        """
        assert module_width in range(1, 11), "module width should be 1 - 10"
        assert bar_width_ratio > 2.0 and bar_width_ratio < 3.0, "invaild ratio"
        self.code += "^BY%i,%.1f,%i" % (module_width, bar_width_ratio,
                bar_code_height*self.dpmm)

    def write_barcode_code39(self, value, orientation='N', mod43='N', height=5,
            interpretation_below='Y', interpretation_above='N'):
        height_dots = height*self.dpmm
        assert orientation in "NRIB", "invalid orientation"
        assert mod43 in "YN", "invalid mod43 (Y/N)"
        assert interpretation_above in "YN", "invalid interpretation_above"
        assert interpretation_below in "YN", "invalid interpretation_below"
        assert height_dots > 1 and height_dots < 32000, "invalid height"
        self.code += "^B3%c,%c,%i,%c,%c" % (orientation, mod43, height_dots,
                interpretation_above, interpretation_below)
        self.code += "^FD%s" % value

    def dumpZPL(self):
        return self.code+"^XZ"

    def saveFormat(self, name):
        self.code= self.code[:3] + ("^DF%s^FS" % name) + self.code[3:]

    def preview(self, index=0):
        '''
        Opens rendered preview using Labelary API.

        Not all commands are supported, see http://labelary.com for more information.
        '''
        try:
            Image.open(io.BytesIO(
                urllib.urlopen('http://api.labelary.com/v1/printers/%idpmm/labels/%fx%f/%i/' %
                    (self.dpmm, self.width/25.4, self.height/25.4, index),
                    self.dumpZPL()).read())).show()
        except IOError:
            raise Exception("Invalid preview received, mostlikely bad ZPL2 code uploaded.")

if __name__ == "__main__":
    l = Label(30,60)
    height = 0
    l.origin(0,0)
    l.write_text("Problem?", char_height=4, char_width=3, line_width=60, justification='C', font="0")
    l.endorigin()

    height += 5
    image_width = 8
    l.origin((l.width-image_width)/2, height)
    image_height = l.write_graphic(Image.open('trollface-large.png'), image_width)
    l.endorigin()

    l.origin(0, height+image_height+2)
    l.write_text('Happy Troloween!', char_height=5, char_width=4, line_width=60,
                 justification='C')
    l.endorigin()


    l.origin(20, height+image_height+10)
    l.write_barcode_code39('ABC123', interpretation_above='Y')
    l.endorigin()


    print l.dumpZPL()
    l.preview()
