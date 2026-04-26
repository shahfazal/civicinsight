import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import RegularPolygon
import numpy as np
import json
from pathlib import Path

output_dir = Path('test_charts/choropleths')
output_dir.mkdir(parents=True, exist_ok=True)

manifest = {}

# Zone names
ZONES = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L']

# Hex grid centers (col, row) in offset layout
HEX_POSITIONS = {
    'A': (1, 3), 'B': (2, 3), 'C': (3, 3),
    'D': (0.5, 2), 'E': (1.5, 2), 'F': (2.5, 2), 'G': (3.5, 2),
    'H': (1, 1), 'I': (2, 1), 'J': (3, 1),
    'K': (1.5, 0), 'L': (2.5, 0)
}

# Political colors
POLITICAL = {
    'Extrême gauche': '#C62828',
    'Gauche': '#E91E63',
    'Centre': '#FFC107',
    'Divers': '#9E9E9E',
    'Droite': '#2196F3',
    'Extrême droite': '#1A1A1A'
}

# Transport colors (no political associations)
TRANSPORT = {
    'Train': '#2E7D32',
    'Bus': '#E65100',
    'Vélo': '#6A1B9A',
    'Voiture': '#4E342E'
}

HEX_SIZE = 0.45


def draw_hex_map(ax, zone_colors, zone_labels=None, zone_circles=None, title=''):
    """Draw a hex grid choropleth."""
    for zone, (col, row) in HEX_POSITIONS.items():
        color = zone_colors.get(zone, '#EEEEEE')
        x = col * 1.0
        y = row * 0.87

        hex_patch = RegularPolygon(
            (x, y), numVertices=6, radius=HEX_SIZE,
            orientation=np.radians(30),
            facecolor=color, edgecolor='white', linewidth=2
        )
        ax.add_patch(hex_patch)

        # Zone label
        label = zone_labels.get(zone, f'Zone {zone}') if zone_labels else f'Zone {zone}'
        ax.text(x, y, label, ha='center', va='center',
                fontsize=8, fontweight='bold',
                color='white' if color in ['#1A1A1A', '#C62828', '#2196F3', '#6A1B9A', '#2E7D32'] else '#333333')

        # Circle overlay
        if zone_circles and zone in zone_circles:
            size = zone_circles[zone]
            ax.scatter(x, y + 0.25, s=size, color='white',
                      edgecolors='#333333', linewidth=1.5, zorder=5)

    ax.set_xlim(-0.5, 4.5)
    ax.set_ylim(-0.6, 3.5)
    ax.set_aspect('equal')
    ax.axis('off')
    ax.set_title(title, fontsize=13, fontweight='bold', pad=15)


def add_category_legend(ax, categories, title='Légende'):
    patches = [mpatches.Patch(color=color, label=label)
               for label, color in categories.items()]
    ax.legend(handles=patches, title=title,
              loc='lower right', fontsize=9, title_fontsize=10)


def add_circle_legend(ax):
    for size, label in [(50, 'Plus abordable'), (150, 'Moyen'), (300, 'Plus cher')]:
        ax.scatter([], [], s=size, color='white', edgecolors='#333333',
                  linewidth=1.5, label=label)
    ax.legend(title='Prix médian au m²', loc='lower left', fontsize=9, title_fontsize=10)


# --- Chart 1: Political blocs ---
political_assignment = {
    'A': 'Gauche', 'B': 'Droite', 'C': 'Extrême droite',
    'D': 'Gauche', 'E': 'Centre', 'F': 'Centre', 'G': 'Droite',
    'H': 'Extrême gauche', 'I': 'Divers', 'J': 'Droite',
    'K': 'Gauche', 'L': 'Extrême droite'
}
zone_colors_1 = {z: POLITICAL[cat] for z, cat in political_assignment.items()}

fig, ax = plt.subplots(figsize=(12, 9))
draw_hex_map(ax, zone_colors_1, title='Résultats électoraux par zone — Bloc politique vainqueur')
add_category_legend(ax, POLITICAL, title='Bloc politique')
plt.tight_layout()
plt.savefig(output_dir / 'choropleth_01_political.png', dpi=150, bbox_inches='tight')
plt.close()
print("Generated choropleth_01_political.png")

manifest['choropleth_01_political.png'] = {
    'description': 'Hard boundaries, political colors, prior knowledge risk',
    'zones': [{'name': f'Zone {z}', 'category': cat, 'color': POLITICAL[cat]}
              for z, cat in political_assignment.items()],
    'legend': POLITICAL
}

# --- Chart 2: Transport (no political priors) ---
transport_assignment = {
    'A': 'Train', 'B': 'Bus', 'C': 'Train',
    'D': 'Vélo', 'E': 'Voiture', 'F': 'Bus', 'G': 'Train',
    'H': 'Bus', 'I': 'Vélo', 'J': 'Voiture',
    'K': 'Train', 'L': 'Bus'
}
zone_colors_2 = {z: TRANSPORT[cat] for z, cat in transport_assignment.items()}

fig, ax = plt.subplots(figsize=(12, 9))
draw_hex_map(ax, zone_colors_2, title='Mode de transport dominant par zone')
add_category_legend(ax, TRANSPORT, title='Transport')
plt.tight_layout()
plt.savefig(output_dir / 'choropleth_02_transport.png', dpi=150, bbox_inches='tight')
plt.close()
print("Generated choropleth_02_transport.png")

manifest['choropleth_02_transport.png'] = {
    'description': 'Hard boundaries, non-political colors, no prior knowledge risk',
    'zones': [{'name': f'Zone {z}', 'category': cat, 'color': TRANSPORT[cat]}
              for z, cat in transport_assignment.items()],
    'legend': TRANSPORT
}

# --- Chart 3: Circle size only ---
prices = {'A': 800, 'B': 3200, 'C': 6500, 'D': 1200, 'E': 2800, 'F': 4100,
          'G': 5500, 'H': 900, 'I': 3600, 'J': 7200, 'K': 1800, 'L': 4800}

def price_to_circle_size(price):
    return 50 + (price / 8000) * 300

zone_circles_3 = {z: price_to_circle_size(p) for z, p in prices.items()}
zone_colors_3 = {z: '#EEEEEE' for z in ZONES}

fig, ax = plt.subplots(figsize=(12, 9))
draw_hex_map(ax, zone_colors_3, zone_circles=zone_circles_3,
             title='Prix médian au m² par zone (taille du cercle)')
add_circle_legend(ax)
plt.tight_layout()
plt.savefig(output_dir / 'choropleth_03_circles.png', dpi=150, bbox_inches='tight')
plt.close()
print("Generated choropleth_03_circles.png")

manifest['choropleth_03_circles.png'] = {
    'description': 'Circle size encoding only, no color variation',
    'zones': [{'name': f'Zone {z}', 'price': prices[z],
               'circle_size_px': round(price_to_circle_size(prices[z]))}
              for z in ZONES]
}

# --- Chart 4: Political + circles ---
fig, ax = plt.subplots(figsize=(12, 9))
draw_hex_map(ax, zone_colors_1, zone_circles=zone_circles_3,
             title='Bloc politique vainqueur et prix médian au m² par zone')
add_category_legend(ax, POLITICAL, title='Bloc politique')
add_circle_legend(ax)
plt.tight_layout()
plt.savefig(output_dir / 'choropleth_04_political_circles.png', dpi=150, bbox_inches='tight')
plt.close()
print("Generated choropleth_04_political_circles.png")

manifest['choropleth_04_political_circles.png'] = {
    'description': 'Two dimensions: political color + circle size for price',
    'zones': [{'name': f'Zone {z}', 'category': political_assignment[z],
               'price': prices[z]} for z in ZONES]
}

# --- Chart 5: Color gradient ---
import matplotlib.colors as mcolors

cmap = plt.cm.Blues
min_price, max_price = min(prices.values()), max(prices.values())

def price_to_gradient_color(price):
    norm = (price - min_price) / (max_price - min_price)
    rgba = cmap(0.2 + norm * 0.75)
    return mcolors.to_hex(rgba)

zone_colors_5 = {z: price_to_gradient_color(p) for z, p in prices.items()}
zone_labels_5 = {z: f'Zone {z}' for z in ZONES}

fig, ax = plt.subplots(figsize=(12, 9))
draw_hex_map(ax, zone_colors_5, zone_labels=zone_labels_5,
             title='Prix médian au m² par zone (gradient de couleur)')

sm = plt.cm.ScalarMappable(cmap=cmap,
     norm=plt.Normalize(vmin=min_price, vmax=max_price))
sm.set_array([])
cbar = plt.colorbar(sm, ax=ax, orientation='vertical', fraction=0.03, pad=0.04)
cbar.set_label('Prix médian (€/m²)', fontsize=10)
cbar.set_ticks([min_price, (min_price+max_price)/2, max_price])
cbar.set_ticklabels([f'{min_price:,} €', f'{(min_price+max_price)//2:,} €', f'{max_price:,} €'])

plt.tight_layout()
plt.savefig(output_dir / 'choropleth_05_gradient.png', dpi=150, bbox_inches='tight')
plt.close()
print("Generated choropleth_05_gradient.png")

manifest['choropleth_05_gradient.png'] = {
    'description': 'Single dimension color gradient, lighter=cheaper darker=expensive',
    'zones': [{'name': f'Zone {z}', 'price': prices[z]} for z in ZONES],
    'scale': {'min': min_price, 'max': max_price, 'encoding': 'lighter=cheaper'}
}

# --- Chart 6: Gradient + printed labels ---
zone_labels_6 = {z: f'{prices[z]:,}€' for z in ZONES}

fig, ax = plt.subplots(figsize=(12, 9))
draw_hex_map(ax, zone_colors_5, zone_labels=zone_labels_6,
             title='Prix médian au m² par zone (gradient + valeurs)')

sm2 = plt.cm.ScalarMappable(cmap=cmap,
      norm=plt.Normalize(vmin=min_price, vmax=max_price))
sm2.set_array([])
cbar2 = plt.colorbar(sm2, ax=ax, orientation='vertical', fraction=0.03, pad=0.04)
cbar2.set_label('Prix médian (€/m²)', fontsize=10)
cbar2.set_ticks([min_price, (min_price+max_price)/2, max_price])
cbar2.set_ticklabels([f'{min_price:,} €', f'{(min_price+max_price)//2:,} €', f'{max_price:,} €'])

plt.tight_layout()
plt.savefig(output_dir / 'choropleth_06_gradient_labels.png', dpi=150, bbox_inches='tight')
plt.close()
print("Generated choropleth_06_gradient_labels.png")

manifest['choropleth_06_gradient_labels.png'] = {
    'description': 'Gradient + printed price labels inside zones',
    'zones': [{'name': f'Zone {z}', 'price': prices[z]} for z in ZONES],
    'scale': {'min': min_price, 'max': max_price, 'encoding': 'lighter=cheaper'}
}

# Save manifest
manifest_path = output_dir / 'ground_truth.json'
with open(manifest_path, 'w', encoding='utf-8') as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)

print(f"\nGenerated 6 choropleth maps in {output_dir}/")
print(f"Ground truth saved to {manifest_path}")
