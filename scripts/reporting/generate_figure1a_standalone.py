#!/usr/bin/env python3
"""
单独的 Figure 1a — 南川河流域研究区图.
- 使用真实 GIS 数据 (4项污染物面源 + 点源)
- 不再是 2-panel 的左半, 而是独立的较大版本
- 增强: 用 网格土地利用类型t.shp 做更精细的土地利用底色
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch
from pathlib import Path

plt.rcParams.update({
    'font.family': 'DejaVu Sans',
    'font.size': 11,
    'axes.labelsize': 11,
    'axes.titlesize': 12,
    'axes.titleweight': 'bold',
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'legend.fontsize': 9.5,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'savefig.facecolor': 'white',
})

OUT_DIR = Path('D:/shanxi/output/figures/figure1a_watershed_standalone')
OUT_DIR.mkdir(parents=True, exist_ok=True)

print("Loading GIS data...")
gdf_area = gpd.read_file('D:/shanxi/gis/4项污染物面源单位面积排放量.shp')
gdf_pt   = gpd.read_file('D:/shanxi/gis/点源排放数据.shp')
gdf_lu   = gpd.read_file('D:/shanxi/gis/网格土地利用类型t.shp')
print(f"  area grids: {len(gdf_area)}")
print(f"  point sources: {len(gdf_pt)}")
print(f"  land-use grids: {len(gdf_lu)}")

print("Reprojecting to WGS84...")
gdf_area_wgs = gdf_area.to_crs('EPSG:4326')
gdf_pt_wgs   = gdf_pt.to_crs('EPSG:4326') if gdf_pt.crs != 'EPSG:4326' else gdf_pt
gdf_lu_wgs   = gdf_lu.to_crs('EPSG:4326')

print("Computing watershed boundary...")
boundary_geom = gdf_area_wgs.geometry.union_all()
boundary_geom = boundary_geom.buffer(0.001).buffer(-0.001)
boundary = gpd.GeoSeries([boundary_geom], crs='EPSG:4326')

# ─── Layout ───
# Single panel, square-ish for inclusion as standalone Fig 1a in journal article
fig, ax = plt.subplots(figsize=(11, 9))

# Watershed body fill
boundary.plot(ax=ax, facecolor='#FAF8EE', edgecolor='#5D4037',
              linewidth=2.0, alpha=0.95, zorder=2)

# Land-use coloring — group fine categories into 5 macro classes
print("Plotting land-use background...")

# DLMC → (group_en, color)  -- 5 macro groups
LU_GROUPS = {
    # Forest
    '乔木林地'    : ('Forest',         '#3E7C3A'),
    '灌木林地'    : ('Forest',         '#3E7C3A'),
    '其他林地'    : ('Forest',         '#3E7C3A'),
    # Grassland
    '其他草地'    : ('Grassland',      '#C4D5A0'),
    '天然牧草地'  : ('Grassland',      '#C4D5A0'),
    # Agricultural
    '旱地'        : ('Agricultural',   '#E8D08C'),
    '水浇地'      : ('Agricultural',   '#E8D08C'),
    '果园'        : ('Agricultural',   '#E8D08C'),
    '设施农用地'  : ('Agricultural',   '#E8D08C'),
    # Built-up
    '农村宅基地'  : ('Built-up',       '#B5A99C'),
    '农村道路'    : ('Built-up',       '#B5A99C'),
    '公路用地'    : ('Built-up',       '#B5A99C'),
    '铁路用地'    : ('Built-up',       '#B5A99C'),
    '城镇村道路用地'      : ('Built-up', '#B5A99C'),
    '城镇住宅用地'        : ('Built-up', '#B5A99C'),
    '工业用地'            : ('Built-up', '#B5A99C'),
    '采矿用地'            : ('Built-up', '#B5A99C'),
    '商业服务业设施用地'  : ('Built-up', '#B5A99C'),
    '机关团体新闻出版用地': ('Built-up', '#B5A99C'),
    '特殊用地'            : ('Built-up', '#B5A99C'),
    '空闲地'              : ('Built-up', '#B5A99C'),
    # Water
    '河流水面'    : ('Water',          '#5DADE2'),
    '湖泊水面'    : ('Water',          '#5DADE2'),
    '坑塘水面'    : ('Water',          '#5DADE2'),
    '水库水面'    : ('Water',          '#5DADE2'),
    '内陆滩涂'    : ('Water',          '#88C0DC'),
    '沟渠'        : ('Water',          '#5DADE2'),
    # Bare / other (light tan)
    '裸土地'      : ('Bare/Other',     '#DBC9A8'),
    '裸岩石砾地'  : ('Bare/Other',     '#DBC9A8'),
}
GROUP_ORDER = ['Forest', 'Grassland', 'Agricultural', 'Built-up', 'Water', 'Bare/Other']
GROUP_COLOR = {
    'Forest':       '#3E7C3A',
    'Grassland':    '#C4D5A0',
    'Agricultural': '#E8D08C',
    'Built-up':     '#B5A99C',
    'Water':        '#5DADE2',
    'Bare/Other':   '#DBC9A8',
}

# Find DLMC column
lu_col_data = None; lu_col = None
for c in ['DLMC', 'dlmc']:
    if c in gdf_lu_wgs.columns:
        lu_col = c; lu_col_data = gdf_lu_wgs; break
if lu_col is None and 'DLMC' in gdf_area_wgs.columns:
    lu_col_data = gdf_area_wgs; lu_col = 'DLMC'

plotted_groups = set()
if lu_col_data is not None:
    # Map DLMC → group_en
    lu_col_data = lu_col_data.copy()
    lu_col_data['_group'] = lu_col_data[lu_col].map(
        lambda c: LU_GROUPS.get(c, ('Bare/Other', GROUP_COLOR['Bare/Other']))[0])
    sample = lu_col_data.sample(min(20000, len(lu_col_data)), random_state=42)
    for grp in GROUP_ORDER:
        sub = sample[sample['_group'] == grp]
        if len(sub) > 0:
            sub.plot(ax=ax, color=GROUP_COLOR[grp], alpha=0.65,
                     edgecolor='none', zorder=3)
            plotted_groups.add(grp)
    print(f"  Land-use groups plotted: {plotted_groups}")

# Watershed boundary line on top of land-use (brighter)
boundary.plot(ax=ax, facecolor='none', edgecolor='#5D4037',
              linewidth=2.2, zorder=8)

# Point sources
ps_color  = {'畜禽散养':'#9C27B0', '规模畜禽养殖':'#B71C1C',
             '工业源':'#1565C0',   '集中式':'#2E7D32'}
ps_marker = {'畜禽散养':'o', '规模畜禽养殖':'s', '工业源':'^', '集中式':'*'}
ps_label  = {'畜禽散养':'Household livestock (n=50)',
             '规模畜禽养殖':'Large-scale livestock (n=34)',
             '工业源':'Industrial source (n=15)',
             '集中式':'Centralized treatment facility (n=1)'}
ps_size   = {'畜禽散养':35, '规模畜禽养殖':70, '工业源':80, '集中式':260}

for cat in ['畜禽散养', '规模畜禽养殖', '工业源', '集中式']:
    sub = gdf_pt_wgs[gdf_pt_wgs['类别'] == cat]
    if len(sub) > 0:
        ax.scatter(sub.geometry.x, sub.geometry.y,
                   marker=ps_marker[cat],
                   c=ps_color[cat],
                   s=ps_size[cat],
                   alpha=0.92,
                   edgecolor='black',
                   linewidth=0.7,
                   label=ps_label[cat],
                   zorder=12)

# Outlet (流域南端中部 — 监测断面)
total_bounds = gdf_area_wgs.total_bounds
outlet_x = (total_bounds[0] + total_bounds[2]) / 2
outlet_y = total_bounds[1] + 0.015
ax.plot(outlet_x, outlet_y, marker='v', color='#D32F2F',
        markersize=22, markeredgecolor='black', markeredgewidth=1.5, zorder=15,
        label='Outlet WQ station')
# 把注释框移到流域内部 (上方), 避免与右下角图例冲突
ax.annotate('Zhongyang outlet station\n(automated WQ,\n5,928 hourly records 2022)',
            xy=(outlet_x, outlet_y),
            xytext=(outlet_x - 0.18, outlet_y + 0.10),
            fontsize=9.5, ha='left', va='center',
            arrowprops=dict(arrowstyle='->', color='#D32F2F', lw=1.5,
                            connectionstyle='arc3,rad=0.2'),
            bbox=dict(boxstyle='round,pad=0.45',
                      facecolor='#FFF8E1', edgecolor='#D32F2F',
                      linewidth=1.2, alpha=0.95),
            zorder=20)

# ─── Scale bar (top-right area, under North arrow) ───
xmin, ymin, xmax, ymax = gdf_area_wgs.total_bounds
# Place scale bar upper-right, below north arrow, away from legend
sx = xmax - 0.13
sy = ymax - 0.005
ax.plot([sx, sx + 0.0902], [sy, sy], color='black', linewidth=4, solid_capstyle='butt', zorder=18)
ax.plot([sx, sx + 0.0451], [sy, sy], color='black', linewidth=4, solid_capstyle='butt', zorder=18)
ax.plot([sx + 0.0451, sx + 0.0902], [sy, sy], color='white', linewidth=3, solid_capstyle='butt', zorder=19)
ax.text(sx, sy - 0.012, '0', ha='center', fontsize=9, zorder=20)
ax.text(sx + 0.0451, sy - 0.012, '5', ha='center', fontsize=9, zorder=20)
ax.text(sx + 0.0902, sy - 0.012, '10 km', ha='center', fontsize=9, zorder=20)

# ─── North arrow (top-right corner) ───
nx = xmax - 0.013; ny = ymax - 0.06
ax.annotate('', xy=(nx, ny + 0.035), xytext=(nx, ny - 0.012),
            arrowprops=dict(arrowstyle='-|>', lw=2.5, color='black',
                            mutation_scale=22),
            zorder=20)
ax.text(nx, ny + 0.045, 'N', ha='center', va='bottom',
        fontsize=14, fontweight='bold', zorder=21)

# ─── Watershed-level info box ───
info_text = ('Nanchuan River Basin\n'
             '• Area: 1,438 km²\n'
             '• River length: 47.8 km\n'
             '• Mean rainfall: 553 mm yr$^{-1}$\n'
             '• Loess Plateau hilly-gully region\n'
             '• Yellow River middle reaches')
ax.text(0.015, 0.985, info_text, transform=ax.transAxes,
        fontsize=9.5, ha='left', va='top',
        bbox=dict(boxstyle='round,pad=0.55', facecolor='white',
                  edgecolor='#5D4037', linewidth=1.0, alpha=0.93),
        zorder=20)

# ─── Land-use legend (bottom-left) ───
lu_handles = []
for grp in GROUP_ORDER:
    if grp in plotted_groups:
        lu_handles.append(mpatches.Patch(color=GROUP_COLOR[grp], label=grp, alpha=0.65))
if lu_handles:
    lu_legend = ax.legend(handles=lu_handles, loc='lower left',
                           bbox_to_anchor=(0.015, 0.015),
                           fontsize=9, ncol=1,
                           title='Land use', title_fontsize=10,
                           framealpha=0.93, edgecolor='gray')
    ax.add_artist(lu_legend)

# ─── Point-source legend (bottom-right) ───
ps_handles = ax.get_legend_handles_labels()
ax.legend(handles=ps_handles[0], labels=ps_handles[1],
          loc='lower right', bbox_to_anchor=(0.985, 0.015),
          fontsize=9, title='Point sources & monitoring', title_fontsize=9.5,
          framealpha=0.93, edgecolor='gray')

ax.set_xlim(xmin - 0.025, xmax + 0.025)
ax.set_ylim(ymin - 0.03, ymax + 0.025)
ax.set_xlabel('Longitude (°E)', fontsize=11)
ax.set_ylabel('Latitude (°N)', fontsize=11)
ax.grid(True, alpha=0.25, linestyle=':', linewidth=0.6, zorder=1)
ax.set_aspect('auto')

plt.savefig(OUT_DIR / 'figure1a_watershed.png')
plt.close()
print(f"\n✓ Saved {OUT_DIR/'figure1a_watershed.png'}")

# ─── Save raw data ───
print("Saving CSV data...")
gdf_pt_wgs[['序号','名称','经度','纬度','类别']].rename(
    columns={'序号':'id','名称':'name','经度':'lon','纬度':'lat','类别':'category_zh'}
).to_csv(OUT_DIR / 'point_sources.csv', index=False, encoding='utf-8-sig')

# Boundary vertices
b_geom = boundary.geometry.iloc[0]
if b_geom.geom_type == 'Polygon':
    rings = [list(b_geom.exterior.coords)]
elif b_geom.geom_type == 'MultiPolygon':
    rings = [list(g.exterior.coords) for g in b_geom.geoms]
else:
    rings = []
boundary_rows = [{'polygon_id': k, 'lon': x, 'lat': y}
                  for k, ring in enumerate(rings) for x, y in ring]
pd.DataFrame(boundary_rows).to_csv(OUT_DIR / 'watershed_boundary.csv', index=False)

# Land-use category counts (with macro group)
if lu_col_data is not None:
    lu_counts = lu_col_data[lu_col].value_counts().reset_index()
    lu_counts.columns = ['category_zh', 'grid_count']
    lu_counts['group_en'] = lu_counts['category_zh'].map(
        lambda c: LU_GROUPS.get(c, ('Bare/Other', '#DBC9A8'))[0])
    lu_counts.to_csv(OUT_DIR / 'landuse_categories.csv', index=False, encoding='utf-8-sig')

readme = """Figure folder: figure1a_watershed_standalone
======================================================

Files in this folder:
  - figure1a_watershed.png    : standalone Figure 1a (panel a only)
  - point_sources.csv         : 100 georeferenced point sources
  - watershed_boundary.csv    : watershed boundary polygon (EPSG:4326)
  - landuse_categories.csv    : land-use category counts and colors

Data sources (D:/shanxi/gis/):
  - 4项污染物面源单位面积排放量.shp : 53,155 area-source grids (EPSG:4525)
  - 点源排放数据.shp                : 100 point sources (EPSG:4326)
  - 网格土地利用类型t.shp           : 53,155 land-use grid polygons (EPSG:4525)

Composition:
  - Watershed boundary derived from area-source grids (dissolved + buffered)
  - Land-use background from sampled grids (15,000 random sample for performance)
  - Point sources colored by category, sized by impact (large livestock/industrial = larger)
  - Outlet station shown as red triangle with annotation
  - Scale bar (10 km), north arrow, info box (watershed metadata)

Reproducibility:
  python scripts/reporting/generate_figure1a_standalone.py
"""
(OUT_DIR / 'README.txt').write_text(readme, encoding='utf-8')
print("✓ Saved CSVs and README")
print(f"\nDone — output in: {OUT_DIR}")
