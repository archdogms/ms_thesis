# -*- coding: utf-8 -*-
from __future__ import print_function

import io
import json
import os
import shutil
import traceback

import arcpy


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
TABLES = os.path.join(ROOT, "output", "tables")
GIS = os.path.join(ROOT, "data", "gis")
OUT = os.path.join(ROOT, "output", "arcgis_thesis")
GDB = os.path.join(OUT, "thesis_maps.gdb")
LAYERS = os.path.join(OUT, "layers")
LOG_PATH = os.path.join(OUT, "arcgis_build_log.txt")
SR = arcpy.SpatialReference(4326)


def ensure_dir(path):
    if not os.path.isdir(path):
        os.makedirs(path)


def log(lines, message):
    lines.append(message)
    print(message)


def delete_if_exists(path):
    if arcpy.Exists(path):
        arcpy.Delete_management(path)


def save_layer(feature_class, name, lines):
    layer_name = name + "_layer"
    layer_file = os.path.join(LAYERS, name + ".lyr")
    delete_if_exists(layer_name)
    if os.path.exists(layer_file):
        os.remove(layer_file)
    arcpy.MakeFeatureLayer_management(feature_class, layer_name)
    arcpy.SaveToLayerFile_management(layer_name, layer_file, "ABSOLUTE")
    log(lines, "  layer: {0}".format(layer_file))
    return layer_file


def create_geojson_polygon_layer(rel_path, fc_name, lines):
    src = os.path.join(ROOT, rel_path)
    out_fc = os.path.join(GDB, fc_name)
    delete_if_exists(out_fc)
    arcpy.CreateFeatureclass_management(GDB, fc_name, "POLYGON", spatial_reference=SR)
    arcpy.AddField_management(out_fc, "name", "TEXT", field_length=80)
    arcpy.AddField_management(out_fc, "source", "TEXT", field_length=80)

    with io.open(src, "r", encoding="utf-8") as handle:
        data = json.load(handle)

    def polygon_from_geometry(geometry):
        parts = arcpy.Array()
        gtype = geometry.get("type")
        coords = geometry.get("coordinates", [])
        polygons = [coords] if gtype == "Polygon" else coords
        for polygon in polygons:
            for ring in polygon:
                arr = arcpy.Array()
                for pair in ring:
                    arr.add(arcpy.Point(float(pair[0]), float(pair[1])))
                if len(arr) > 0:
                    parts.add(arr)
        return arcpy.Polygon(parts, SR)

    fields = ["SHAPE@", "name", "source"]
    cursor = arcpy.da.InsertCursor(out_fc, fields)
    try:
        for feature in data.get("features", []):
            props = feature.get("properties", {})
            shape = polygon_from_geometry(feature.get("geometry", {}))
            cursor.insertRow([shape, props.get("name", u""), props.get("source", u"geojson")])
    finally:
        del cursor

    count = int(arcpy.GetCount_management(out_fc).getOutput(0))
    log(lines, "polygon: {0} ({1} features)".format(fc_name, count))
    save_layer(out_fc, fc_name, lines)
    return out_fc


def create_xy_layer(csv_name, x_field, y_field, fc_name, lines):
    src = os.path.join(TABLES, csv_name)
    out_fc = os.path.join(GDB, fc_name)
    temp_layer = fc_name + "_xy"
    source_count = int(arcpy.GetCount_management(src).getOutput(0))
    delete_if_exists(out_fc)
    delete_if_exists(temp_layer)
    arcpy.MakeXYEventLayer_management(src, x_field, y_field, temp_layer, SR)
    arcpy.CopyFeatures_management(temp_layer, out_fc)
    count = int(arcpy.GetCount_management(out_fc).getOutput(0))
    message = "points: {0} ({1} features; source rows {2})".format(fc_name, count, source_count)
    if count != source_count:
        message += " [check invalid or out-of-range XY values]"
    log(lines, message)
    save_layer(out_fc, fc_name, lines)
    return out_fc


def template_mxd():
    candidates = [
        r"E:\ArcGis\Desktop10.8\MapTemplates\Standard Page Sizes\ISO (A) Page Sizes\ISO A4 Landscape.mxd",
        r"E:\ArcGis\Desktop10.8\MapTemplates\Standard Page Sizes\North American (ANSI) Page Sizes\ANSI C Landscape.mxd",
        r"C:\Program Files (x86)\ArcGIS\Desktop10.8\MapTemplates\Standard Page Sizes\ISO (A) Page Sizes\ISO A4 Landscape.mxd",
        r"C:\Program Files\ArcGIS\Desktop10.8\MapTemplates\Standard Page Sizes\ISO (A) Page Sizes\ISO A4 Landscape.mxd",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def build_mxd(name, layer_names, extent_fc, lines):
    tmpl = template_mxd()
    if not tmpl:
        log(lines, "mxd skipped: no ArcMap A4 template was found")
        return None

    mxd_path = os.path.join(OUT, name + ".mxd")
    png_path = os.path.join(OUT, name + ".png")
    shutil.copyfile(tmpl, mxd_path)

    mxd = arcpy.mapping.MapDocument(mxd_path)
    df = arcpy.mapping.ListDataFrames(mxd)[0]
    for layer_name in layer_names:
        layer_file = os.path.join(LAYERS, layer_name + ".lyr")
        if os.path.exists(layer_file):
            arcpy.mapping.AddLayer(df, arcpy.mapping.Layer(layer_file), "TOP")

    if extent_fc and arcpy.Exists(extent_fc):
        df.extent = arcpy.Describe(extent_fc).extent
        df.scale = df.scale * 1.08

    mxd.save()
    arcpy.mapping.ExportToPNG(mxd, png_path, resolution=180)
    del mxd
    log(lines, "mxd: {0}".format(mxd_path))
    log(lines, "preview: {0}".format(png_path))
    return mxd_path


def write_readme(lines):
    readme = os.path.join(OUT, "README.md")
    text = u"""# ArcGIS thesis map package

This folder was generated by `tools/prepare_arcgis_thesis_package.py` with ArcGIS Desktop 10.8 / arcpy.

Contents:

- `thesis_maps.gdb`: FileGDB containing thesis spatial layers.
- `layers/*.lyr`: ArcMap layer files for quick loading.
- `arcgis_*_preview.mxd`: ArcMap layout previews.
- `arcgis_*_preview.png`: proof exports generated by ArcGIS.

Notes:

- Coordinate system: WGS 1984 (EPSG:4326).
- Administrative base: seven town/street polygons from `data/gis/nanhai_towns_440605_precise.geojson`; the district boundary is generated from their union to avoid duplicate or incomplete edge lines.
- The final thesis PNGs are still rendered by `tools/render_thesis_figures_unified.py`, because charts, process diagrams and composite figures need a unified publication layout.
- Use the MXD previews as ArcMap starting points for manual cartographic refinement if a later Word/PDF version needs ArcGIS-native map exports.
"""
    with io.open(readme, "w", encoding="utf-8") as handle:
        handle.write(text)
    with io.open(LOG_PATH, "w", encoding="utf-8") as handle:
        handle.write(u"\n".join([unicode(line) for line in lines]))


def cleanup_arcgis_csv_sidecars(lines):
    schema_ini = os.path.join(TABLES, "schema.ini")
    if os.path.exists(schema_ini):
        os.remove(schema_ini)
        log(lines, "cleanup: removed output/tables/schema.ini")


def main():
    lines = []
    ensure_dir(OUT)
    ensure_dir(LAYERS)
    arcpy.env.overwriteOutput = True
    if arcpy.Exists(GDB):
        arcpy.Delete_management(GDB)
    arcpy.CreateFileGDB_management(OUT, "thesis_maps.gdb")
    log(lines, "gdb: {0}".format(GDB))

    boundary = create_geojson_polygon_layer(os.path.join("data", "gis", "nanhai_boundary_440605_precise.geojson"), "nanhai_boundary", lines)
    create_geojson_polygon_layer(os.path.join("data", "gis", "nanhai_towns_440605_precise.geojson"), "nanhai_towns", lines)
    create_xy_layer("indices_anchors.csv", "lng", "lat", "culture_anchors_points", lines)
    create_xy_layer("poi_cleaned.csv", "lng", "lat", "poi_points", lines)
    create_xy_layer("grid_indices_kg.csv", "clng", "clat", "grid_indices_points", lines)
    create_xy_layer("official_resources_20260510.csv", "lng", "lat", "official_resources_points", lines)
    create_xy_layer("official_grid_coverage_20260510.csv", "clng", "clat", "official_grid_points", lines)
    create_xy_layer("diagnostic_split_grid_20260510.csv", "clng", "clat", "diagnostic_grid_points", lines)

    build_mxd(
        "arcgis_culture_tourism_preview",
        ["nanhai_boundary", "nanhai_towns", "poi_points", "culture_anchors_points"],
        boundary,
        lines,
    )
    build_mxd(
        "arcgis_grid_preview",
        ["nanhai_boundary", "nanhai_towns", "grid_indices_points", "diagnostic_grid_points"],
        boundary,
        lines,
    )
    build_mxd(
        "arcgis_official_preview",
        ["nanhai_boundary", "nanhai_towns", "official_grid_points", "official_resources_points"],
        boundary,
        lines,
    )
    cleanup_arcgis_csv_sidecars(lines)
    log(lines, "done")
    write_readme(lines)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise
