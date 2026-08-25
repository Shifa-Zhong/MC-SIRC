#!/usr/bin/env python3
"""Generate the EJRH study-area KML/KMZ from the archived basin grid polygons."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET
import zipfile

import geopandas as gpd
from shapely.geometry import MultiPolygon, Polygon


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "gis" / "网格土地利用类型t.shp"
KML = ROOT / "paper" / "Nanchuan_River_Basin_Study_Area.kml"
KMZ = ROOT / "paper" / "Nanchuan_River_Basin_Study_Area.kmz"
NS = "http://www.opengis.net/kml/2.2"
ET.register_namespace("", NS)


def q(name: str):
    return f"{{{NS}}}{name}"


def coordinate_text(ring):
    return " ".join(f"{x:.7f},{y:.7f},0" for x, y in ring.coords)


def add_polygon(parent, polygon: Polygon):
    element = ET.SubElement(parent, q("Polygon"))
    ET.SubElement(element, q("tessellate")).text = "1"
    outer = ET.SubElement(element, q("outerBoundaryIs"))
    ring = ET.SubElement(outer, q("LinearRing"))
    ET.SubElement(ring, q("coordinates")).text = coordinate_text(polygon.exterior)
    for interior in polygon.interiors:
        inner = ET.SubElement(element, q("innerBoundaryIs"))
        ring = ET.SubElement(inner, q("LinearRing"))
        ET.SubElement(ring, q("coordinates")).text = coordinate_text(interior)


def main():
    frame = gpd.read_file(SOURCE)
    if frame.crs is None:
        raise RuntimeError("Study-area shapefile has no coordinate reference system")
    outline_projected = frame.geometry.union_all().buffer(0).simplify(20, preserve_topology=True)
    area_km2 = outline_projected.area / 1_000_000
    outline = gpd.GeoSeries([outline_projected], crs=frame.crs).to_crs(4326).iloc[0]
    if isinstance(outline, Polygon):
        polygons = [outline]
    elif isinstance(outline, MultiPolygon):
        polygons = list(outline.geoms)
    else:
        polygons = [geometry for geometry in outline.geoms if isinstance(geometry, Polygon)]

    root = ET.Element(q("kml"))
    document = ET.SubElement(root, q("Document"))
    ET.SubElement(document, q("name")).text = "Nanchuan River Basin study area"
    style = ET.SubElement(document, q("Style"), id="basin")
    line = ET.SubElement(style, q("LineStyle"))
    ET.SubElement(line, q("color")).text = "ff9a4a21"
    ET.SubElement(line, q("width")).text = "2"
    poly_style = ET.SubElement(style, q("PolyStyle"))
    ET.SubElement(poly_style, q("color")).text = "55338bd6"

    placemark = ET.SubElement(document, q("Placemark"))
    ET.SubElement(placemark, q("name")).text = "Nanchuan River Basin"
    ET.SubElement(placemark, q("description")).text = (
        f"Study-area outline dissolved from the 1-km inventory grid overlay; projected area "
        f"{area_km2:.2f} km². Coordinates are WGS 84."
    )
    ET.SubElement(placemark, q("styleUrl")).text = "#basin"
    geometry_parent = placemark
    if len(polygons) > 1:
        geometry_parent = ET.SubElement(placemark, q("MultiGeometry"))
    for polygon in polygons:
        add_polygon(geometry_parent, polygon)

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    KML.parent.mkdir(parents=True, exist_ok=True)
    tree.write(KML, encoding="utf-8", xml_declaration=True)
    with zipfile.ZipFile(KMZ, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(KML, "doc.kml")
    print(f"{KML} | {KMZ} | area={area_km2:.2f} km2 | polygons={len(polygons)}")


if __name__ == "__main__":
    main()
