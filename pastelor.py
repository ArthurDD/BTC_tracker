# Based on code from snyppets http://sebsauvage.net/python/snyppets/
# underconstruction
# Taken from https://gist.github.com/roastedneutrons/1549683

from PIL import Image, ImageDraw
import itertools

nColors = 256
vert = 8
horiz = 16
patchSize = 30
delimSize = 10
txtSize = 0


def htmlColor(rgb):
    return '#%02x%02x%02x' % rgb


def floatrange(start, stop, steps):
    if int(steps) == 1:
        return [stop]
    return [start + float(i) * (stop - start) / (float(steps) - 1) for i in range(steps)]


def HSL_to_RGB(h, s, l):
    def Hue_2_RGB(v1, v2, vH):
        while vH < 0.0:
            vH += 1.0
        while vH > 1.0:
            vH -= 1.0
        if 6 * vH < 1.0:
            return v1 + (v2 - v1) * 6.0 * vH
        if 2 * vH < 1.0:
            return v2
        if 3 * vH < 2.0:
            return v1 + (v2 - v1) * ((2.0 / 3.0) - vH) * 6.0
        return v1

    if not (0 <= s <= 1):
        raise (ValueError, "s (saturation) parameter must be between 0 and 1.")
    if not (0 <= l <= 1):
        raise (ValueError, "l (lightness) parameter must be between 0 and 1.")

    r, b, g = (l * 255,) * 3
    if s != 0.0:
        if l < 0.5:
            var_2 = l * (1.0 + s)
        else:
            var_2 = (l + s) - (s * l)
        var_1 = 2.0 * l - var_2
        r = 255 * Hue_2_RGB(var_1, var_2, h + (1.0 / 3.0))
        g = 255 * Hue_2_RGB(var_1, var_2, h)
        b = 255 * Hue_2_RGB(var_1, var_2, h - (1.0 / 3.0))

    return int(round(r)), int(round(g)), int(round(b))


def ceilCubeRoot(n):
    if n < 0: return 0
    i = 0
    while i ** 3 < n:
        i += 1
    return i


def nForHSL(n):
    return 8, 8, 4


def generate_pastel_colours():
    n = 256
    hn, sn, ln = nForHSL(n)
    Hs = floatrange(0, 1, hn + 1)[:-1]
    Ss = floatrange(1, 0.5, sn)
    Ls = floatrange(0.75, 0.87, ln)
    HSLs = itertools.product(Hs, Ss, Ls)
    return ['#%02x%02x%02x' % HSL_to_RGB(h, s, l) for h, s, l in HSLs]


def display_colours():
    w = delimSize * (horiz + 1) + patchSize * horiz
    h = delimSize * (vert + 1) + patchSize * vert + txtSize * vert
    im = Image.new('RGB', (w, h), (255, 255, 255))

    colors = generatePastelColors()

    k = 0
    imDraw = ImageDraw.Draw(im)
    for i in range(horiz):
        for j in range(vert):
            x1 = delimSize * (i + 1) + patchSize * i
            y1 = delimSize * (j + 1) + patchSize * j + txtSize * j
            x2 = x1 + patchSize
            y2 = y1 + patchSize
            imDraw.rectangle((x1, y1, x2, y2), fill=(colors[k]))
            k += 1

    im.show()


