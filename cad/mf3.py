"""Minimal, correct 3MF writer.

trimesh 5.0's exporter writes objects into <resources> but leaves <build>
empty, so slicers open a plate with nothing on it. It also discards names.
This writes both, and keeps the names.
"""
import zipfile

CT = ('<?xml version="1.0" encoding="UTF-8"?>\n'
      '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
      '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
      '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
      '</Types>')

RELS = ('<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Target="/3D/3dmodel.model" Id="rel0" '
        'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>'
        '</Relationships>')


def write_3mf(path, items):
    """items: list of (name, mesh, x, y). Mesh must already sit at z=0."""
    res, build = [], []
    for i, (name, m, tx, ty) in enumerate(items, start=1):
        v = "".join(f'<vertex x="{a:.4f}" y="{b:.4f}" z="{c:.4f}"/>'
                    for a, b, c in m.vertices)
        t = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>'
                    for a, b, c in m.faces)
        res.append(f'<object id="{i}" type="model" name="{name}">'
                   f'<mesh><vertices>{v}</vertices>'
                   f'<triangles>{t}</triangles></mesh></object>')
        build.append(f'<item objectid="{i}" '
                     f'transform="1 0 0 0 1 0 0 0 1 {tx:.4f} {ty:.4f} 0"/>')
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<model unit="millimeter" xml:lang="en-US" '
           'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
           '<metadata name="Application">ToolCell generator</metadata>'
           f'<resources>{"".join(res)}</resources>'
           f'<build>{"".join(build)}</build></model>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CT)
        z.writestr("_rels/.rels", RELS)
        z.writestr("3D/3dmodel.model", xml)
    return len(items)


def verify(path):
    """Returns (objects, build_items). They must be equal."""
    with zipfile.ZipFile(path) as z:
        xml = z.read("3D/3dmodel.model").decode()
    return xml.count("<object id="), xml.count("<item objectid=")
