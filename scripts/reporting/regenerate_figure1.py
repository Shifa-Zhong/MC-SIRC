#!/usr/bin/env python3
"""
重新生成 Figure 1, 用真实 GIS 数据替代示意图
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch
import matplotlib.patches as mpatches
from pathlib import Path
from shapely.ops import unary_union

plt.rcParams.update({
    'font.family': 'DejaVu Sans',
    'font.size': 10,
    'axes.labelsize': 10,
    'axes.titlesize': 11,
    'axes.titleweight': 'bold',
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 9,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'savefig.facecolor': 'white',
})

OUT_DIR = Path('D:/shanxi/output/figures/figure1_watershed_framework')
OUT_DIR.mkdir(parents=True, exist_ok=True)

print("Loading GIS data...")
# 面源 (用作流域边界 - 这是研究区的所有网格)
print("  Loading area source grids (this may take a moment)...")
gdf_area = gpd.read_file('D:/shanxi/gis/4项污染物面源单位面积排放量.shp')
print(f"  Area grids: {len(gdf_area)}, CRS: {gdf_area.crs}")

# 点源
gdf_pt = gpd.read_file('D:/shanxi/gis/点源排放数据.shp')
print(f"  Point sources: {len(gdf_pt)}, CRS: {gdf_pt.crs}")

# 转到 EPSG:4326 (lat/lon) 统一
print("  Reprojecting to WGS84...")
gdf_area_wgs = gdf_area.to_crs('EPSG:4326')
gdf_pt_wgs = gdf_pt.to_crs('EPSG:4326') if gdf_pt.crs != 'EPSG:4326' else gdf_pt

# 流域 boundary: 把所有网格 dissolve, 用 buffer + simplify 减少计算量
print("  Computing watershed boundary from grids (dissolve)...")
# 简化: 直接用 unary_union 然后 simplify
boundary_geom = gdf_area_wgs.geometry.union_all()
print(f"  Boundary type: {boundary_geom.geom_type}")
boundary_geom = boundary_geom.buffer(0.001).buffer(-0.001)  # close small gaps
# Convert to GeoSeries for plotting
boundary = gpd.GeoSeries([boundary_geom], crs='EPSG:4326')

print("\nGenerating Figure 1...")
fig, axes = plt.subplots(1, 2, figsize=(15, 7), gridspec_kw={'width_ratios':[1.1, 1]})

# ─── Panel (a): 真实流域图 ───
ax = axes[0]
# 流域底色
boundary.plot(ax=ax, facecolor='#F5F5DC', edgecolor='#8B4513', linewidth=1.5, alpha=0.7)

# 加入地形/土地利用着色: 按 DLMC 分类
if 'DLMC' in gdf_area_wgs.columns:
    # 简化: 抽取主要地类
    print("  Plotting land use background (sampled grids)...")
    landuse_colors = {
        '乔木林地':'#5B8C5A', '灌木林地':'#A8C5A0', '草地':'#D5E5A0',
        '果园':'#D8B068', '旱地':'#E8D08C', '水浇地':'#7FB3D5',
        '城市':'#888888', '村庄':'#C0A080', '水域':'#5DADE2'
    }
    # Sample grids for performance — too many to plot all
    sample = gdf_area_wgs.sample(min(8000, len(gdf_area_wgs)), random_state=42)
    for cat, color in landuse_colors.items():
        sub = sample[sample['DLMC'] == cat]
        if len(sub) > 0:
            sub.plot(ax=ax, color=color, alpha=0.55, edgecolor='none')

# 点源按类别画
ps_color_map = {
    '畜禽散养': '#DDA0DD',
    '规模畜禽养殖': '#B22222',
    '工业源': '#4682B4',
    '集中式': '#228B22',
}
ps_marker_map = {
    '畜禽散养': 'o',
    '规模畜禽养殖': 's',
    '工业源': '^',
    '集中式': '*',
}
ps_label_map = {
    '畜禽散养': 'Household livestock (n=50)',
    '规模畜禽养殖': 'Large livestock (n=34)',
    '工业源': 'Industrial (n=15)',
    '集中式': 'Centralized facility (n=1)',
}
for cat in ['畜禽散养', '规模畜禽养殖', '工业源', '集中式']:
    sub = gdf_pt_wgs[gdf_pt_wgs['类别'] == cat]
    if len(sub) > 0:
        ms = 50 if cat == '集中式' else (40 if cat in ['工业源','规模畜禽养殖'] else 22)
        ax.scatter(sub.geometry.x, sub.geometry.y, marker=ps_marker_map[cat],
                   c=ps_color_map[cat], s=ms, alpha=0.85,
                   edgecolor='black', linewidth=0.5, label=ps_label_map[cat], zorder=10)

# 出口位置 (集中式设施附近, 即流域出口)
# 用集中式作为 outlet 近似
central = gdf_pt_wgs[gdf_pt_wgs['类别'] == '集中式']
if len(central) > 0:
    outlet_x = central.geometry.x.mean()
    outlet_y = central.geometry.y.mean()
    # 实际 outlet 可能在最下游处 - 用网格的最低点近似
    pass
# 更可靠: 取 area grids 的 minx/miny 作为流域下游入河
total_bounds = gdf_area_wgs.total_bounds  # [minx, miny, maxx, maxy]
# Outlet 位置用网格南端中心
outlet_x = (total_bounds[0] + total_bounds[2]) / 2
outlet_y = total_bounds[1] + 0.02
ax.plot(outlet_x, outlet_y, 'v', color='#C73E1D', markersize=18, zorder=15,
        markeredgecolor='black', markeredgewidth=1)
ax.annotate('Outlet station\n(automated WQ\nmonitoring)', xy=(outlet_x, outlet_y),
            xytext=(outlet_x+0.06, outlet_y+0.06), fontsize=8.5, ha='left',
            arrowprops=dict(arrowstyle='->', color='#C73E1D', lw=1.5),
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#FFE4B5', edgecolor='#C73E1D', alpha=0.9))

# 标尺
xmin, ymin, xmax, ymax = gdf_area_wgs.total_bounds
# scale bar
sx = xmin + 0.03
sy = ymin + 0.01
# Approx: 1° latitude ≈ 111 km, so 0.05° ≈ 5.5 km
ax.plot([sx, sx + 0.045], [sy, sy], 'k-', linewidth=3)
ax.text(sx + 0.0225, sy - 0.008, '5 km', ha='center', fontsize=8)

# North arrow
nx = xmax - 0.03; ny = ymax - 0.04
ax.annotate('N', xy=(nx, ny + 0.015), ha='center', fontsize=12, fontweight='bold')
ax.annotate('', xy=(nx, ny + 0.025), xytext=(nx, ny - 0.015),
            arrowprops=dict(arrowstyle='->', lw=2, color='black'))

ax.set_xlim(xmin - 0.02, xmax + 0.02)
ax.set_ylim(ymin - 0.04, ymax + 0.02)
ax.set_xlabel('Longitude (°E)', fontsize=9)
ax.set_ylabel('Latitude (°N)', fontsize=9)
ax.grid(True, alpha=0.3, linestyle=':', linewidth=0.5)

# Legend
ax.legend(loc='upper left', fontsize=7.5, framealpha=0.9, ncol=1)
ax.set_title('(a) Nanchuan River Basin: emission inventory and outlet monitoring', loc='left', fontsize=10.5)

# ─── Panel (b): Framework flowchart (保持原版) ───
ax = axes[1]
ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.set_aspect('equal')
ax.spines[:].set_visible(False); ax.set_xticks([]); ax.set_yticks([])
stages = [
    ('Emission inventory\n(53,155 grids + 100 pt)', 1.5, 8.5, '#FFE4B5'),
    ('River-entry estimation\n(Tables 2, S7)', 1.5, 6.7, '#E0FFFF'),
    ('Bayesian MAP + MCMC\n(Tables 4–5, S8, S16)', 1.5, 4.9, '#FFE4E1'),
    ('Monte Carlo uncertainty\n(Tables S10–S11)', 1.5, 3.1, '#F0FFF0'),
    ('Spatial decay model\n(Tables 7, S13–S15)', 1.5, 1.3, '#E6E6FA'),
]
for label, x, y, color in stages:
    rect = Rectangle((x, y-0.6), 6, 1.2, facecolor=color, edgecolor='#333', linewidth=1.2)
    ax.add_patch(rect)
    ax.text(x+3, y, label, ha='center', va='center', fontsize=9.5, fontweight='bold')
for y in [7.9, 6.1, 4.3, 2.5]:
    ax.annotate('', xy=(4.5, y-0.6), xytext=(4.5, y),
                arrowprops=dict(arrowstyle='->', lw=2, color='#444'))
ax.text(8.5, 5, 'Monitored\nload\n(Table S5)', ha='center', va='center',
        fontsize=9, fontweight='bold',
        bbox=dict(boxstyle='round,pad=0.4', facecolor='#FFE4B5', edgecolor='#C73E1D', linewidth=1.5))
ax.annotate('', xy=(7.5, 4.9), xytext=(8.5, 4.5),
            arrowprops=dict(arrowstyle='->', lw=1.5, color='#C73E1D', linestyle='dashed'))
ax.text(7.6, 4.0, 'Top-down\nconstraint', ha='left', va='top', fontsize=8, color='#C73E1D', style='italic')
ax.set_title('(b) MC-SIRC five-stage analytical framework', loc='left', fontsize=10.5)

plt.tight_layout()
plt.savefig(OUT_DIR / 'figure1_watershed_framework.png')
plt.close()
print(f"  ✓ Saved {OUT_DIR/'figure1_watershed_framework.png'}")

# ─── 保存原始数据 ───
print("Saving CSV data...")
# 点源
gdf_pt_wgs[['序号','名称','经度','纬度','类别']].rename(
    columns={'序号':'id', '名称':'name', '经度':'lon', '纬度':'lat', '类别':'category_zh'}
).to_csv(OUT_DIR / 'panel_a_point_sources.csv', index=False, encoding='utf-8-sig')

# 流域 boundary 顶点
b_geom = boundary.geometry.iloc[0]
if b_geom.geom_type == 'Polygon':
    rings = [list(b_geom.exterior.coords)]
elif b_geom.geom_type == 'MultiPolygon':
    rings = [list(g.exterior.coords) for g in b_geom.geoms]
else:
    rings = []
boundary_rows = []
for k, ring in enumerate(rings):
    for x, y in ring:
        boundary_rows.append({'polygon_id': k, 'lon': x, 'lat': y})
pd.DataFrame(boundary_rows).to_csv(OUT_DIR / 'panel_a_watershed_boundary.csv', index=False)

# Framework stages
pd.DataFrame([
    {'order': 1, 'stage': 'Emission inventory', 'inputs': '53,155 grids + 100 point sources'},
    {'order': 2, 'stage': 'River-entry estimation', 'inputs': 'Tables 2, S7'},
    {'order': 3, 'stage': 'Bayesian MAP+MCMC', 'inputs': 'Tables 4-5, S8, S16'},
    {'order': 4, 'stage': 'Monte Carlo uncertainty', 'inputs': 'Tables S10-S11'},
    {'order': 5, 'stage': 'Spatial decay model', 'inputs': 'Tables 7, S13-S15'},
]).to_csv(OUT_DIR / 'panel_b_framework_stages.csv', index=False)

# 删除示意图旧的 control_units csv
old_csv = OUT_DIR / 'panel_a_control_units.csv'
if old_csv.exists():
    old_csv.unlink()
    print(f"  Removed old schematic CSV: {old_csv.name}")

# 更新 README
readme = """Figure folder: figure1_watershed_framework
============================================================

Files in this folder:
  - figure1_watershed_framework.png : the rendered figure (Setup A)
  - panel_a_point_sources.csv       : 100 georeferenced point sources from gis/点源排放数据.shp
  - panel_a_watershed_boundary.csv  : watershed boundary polygon (dissolved from
                                      gis/4项污染物面源单位面积排放量.shp)
  - panel_b_framework_stages.csv    : five-stage workflow

Data sources:
  GIS shapefiles in D:/shanxi/gis/:
    - 4项污染物面源单位面积排放量.shp : 53,155 area-source grids (EPSG:4525)
    - 点源排放数据.shp                : 100 point sources with lat/lon (EPSG:4326)
    - 网格土地利用类型t.shp           : 53,155 land use grid polygons (EPSG:4525)

Reproducibility:
  python scripts/reporting/regenerate_figure1.py

Notes:
  Panel (a) uses real Nanchuan watershed extent (~37.11–37.47°N, 110.85–111.92°E)
  derived from the area-source grid shapefile. Background coloring shades major
  land-use categories (forest, shrubland, orchard, dryland, etc.). Outlet station
  position is approximate (southern edge of watershed extent).
"""
(OUT_DIR / 'README.txt').write_text(readme, encoding='utf-8')
print("  ✓ Updated README.txt")
print("\nDone.")
