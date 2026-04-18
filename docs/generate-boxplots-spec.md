# Synthetic Box Plot Generator for Gemma 4 Testing

**Goal:** Generate 6 synthetic box plots to test 4 specific failure modes identified in zero-shot evaluation.

**Domain:** French school grades (0-20 scale)
- Y-axis: 0 to 20 (Note sur 20)
- X-axis categories: Maths, Français, Histoire, Sciences, Arts, Sport
- Outlier labels: student names (e.g., "Hugo", "Léa")
- Tooltip format: "(Maths, median: 12.5)"

---

## Failure Modes to Test

1. **Outlier detection** — points above/below whiskers
2. **Tooltip attribution** — printed labels on 1-2 boxes only, rest must be estimated
3. **Tooltip proximity confusion** — tooltip for box A overlaps visually with box B
4. **Y-axis estimation accuracy** — boxes at known positions, measure drift
5. **Relative box sizes** — varying IQR widths (narrow vs wide distributions)

---

## 6 Chart Variations

### Chart 1: Clean Baseline (no tooltips, no outliers)
- 6 subjects, random distributions
- No hover tooltips
- No outliers
- Tests: pure Y-axis estimation, reading order

### Chart 2: Outliers Only (no tooltips)
- 6 subjects
- 2-3 outlier points per chart (above AND below whiskers)
- Outlier points labeled with student names
- No hover tooltips
- Tests: outlier detection, outlier labeling

### Chart 3: Tooltips on 2 Boxes (center boxes)
- 6 subjects
- Full tooltip visible on Maths and Histoire only
- Other 4 boxes have no labels
- Tests: tooltip attribution, estimation of non-tooltip boxes

### Chart 4: Tooltip Proximity Confusion
- 6 subjects
- Tooltip for Maths box positioned to overlap/bleed into Français box area
- Both boxes have similar Y ranges (easy to confuse)
- Tests: spatial anchoring under ambiguity

### Chart 5: Extreme Size Variation
- 6 subjects
- 2 very narrow boxes (IQR ~1 grade point) — Arts, Sport
- 2 very wide boxes (IQR ~8 grade points) — Maths, Histoire  
- 2 medium boxes — Français, Sciences
- No tooltips
- Tests: relative IQR estimation

### Chart 6: Full Complexity
- 6 subjects
- Outliers on 3 boxes
- Tooltips on 2 boxes (not adjacent — Maths and Sport)
- Tooltip for Maths positioned close to Français
- Wide variation in box sizes
- Tests: all failure modes simultaneously

---

## Technical Spec

### Dependencies
```python
matplotlib
numpy
random
```

### Output Format
- PNG images, 1400x700px
- Save to `test_charts/boxplots/` directory
- Filename pattern: `boxplot_{id}_{description}.png`
- JSON manifest with ground truth

### Color Palette (match elections viz style)
```python
COLORS = {
    'Maths': '#E91E63',
    'Français': '#FF6B9D', 
    'Histoire': '#FFC107',
    'Sciences': '#9E9E9E',
    'Arts': '#2196F3',
    'Sport': '#1A1A1A'
}
```

### Manifest Format
```json
{
  "boxplot_01_baseline.png": {
    "subjects": [
      {
        "name": "Maths",
        "min": 8.5,
        "q1": 11.0,
        "median": 13.5,
        "q3": 15.5,
        "max": 18.0,
        "outliers": [],
        "tooltip_visible": false
      }
    ]
  }
}
```

---

## Python Script

```python
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import json
import random
from pathlib import Path

random.seed(42)
np.random.seed(42)

SUBJECTS = ['Maths', 'Français', 'Histoire', 'Sciences', 'Arts', 'Sport']
COLORS = ['#E91E63', '#FF6B9D', '#FFC107', '#9E9E9E', '#2196F3', '#333333']
STUDENT_NAMES = ['Hugo', 'Léa', 'Thomas', 'Emma', 'Lucas', 'Chloé', 'Nathan', 'Inès']

output_dir = Path('test_charts/boxplots')
output_dir.mkdir(parents=True, exist_ok=True)

manifest = {}


def make_grades(median, iqr, n=30):
    """Generate grade distribution around a median with given IQR."""
    q1 = median - iqr / 2
    q3 = median + iqr / 2
    data = np.random.normal(median, iqr / 1.35, n)
    data = np.clip(data, 0, 20)
    return sorted(data.tolist())


def box_stats(data):
    """Return box plot statistics."""
    q1 = float(np.percentile(data, 25))
    median = float(np.percentile(data, 50))
    q3 = float(np.percentile(data, 75))
    iqr = q3 - q1
    lower_fence = max(0, q1 - 1.5 * iqr)
    upper_fence = min(20, q3 + 1.5 * iqr)
    outliers = [x for x in data if x < lower_fence or x > upper_fence]
    whisker_low = min([x for x in data if x >= lower_fence], default=q1)
    whisker_high = max([x for x in data if x <= upper_fence], default=q3)
    return {
        'q1': round(q1, 2),
        'median': round(median, 2),
        'q3': round(q3, 2),
        'lower_fence': round(lower_fence, 2),
        'upper_fence': round(upper_fence, 2),
        'whisker_low': round(whisker_low, 2),
        'whisker_high': round(whisker_high, 2),
        'outliers': [round(o, 2) for o in outliers]
    }


def draw_boxplot(ax, pos, data, color, stats, tooltip=None, tooltip_offset=(0.3, 0), outlier_labels=None):
    """Draw a single box plot manually for full control."""
    q1, median, q3 = stats['q1'], stats['median'], stats['q3']
    wl, wh = stats['whisker_low'], stats['whisker_high']
    outliers = stats['outliers']

    # Box
    box = mpatches.FancyBboxPatch(
        (pos - 0.3, q1), 0.6, q3 - q1,
        boxstyle="square,pad=0",
        linewidth=1.5, edgecolor=color,
        facecolor=color, alpha=0.3
    )
    ax.add_patch(box)

    # Median line
    ax.plot([pos - 0.3, pos + 0.3], [median, median], color=color, linewidth=2.5)

    # Whiskers
    ax.plot([pos, pos], [wl, q1], color=color, linewidth=1.5)
    ax.plot([pos, pos], [q3, wh], color=color, linewidth=1.5)

    # Whisker caps
    ax.plot([pos - 0.15, pos + 0.15], [wl, wl], color=color, linewidth=1.5)
    ax.plot([pos - 0.15, pos + 0.15], [wh, wh], color=color, linewidth=1.5)

    # Outliers
    for i, o in enumerate(outliers):
        ax.scatter(pos, o, color=color, s=40, zorder=5)
        if outlier_labels and i < len(outlier_labels):
            ax.annotate(outlier_labels[i], (pos, o),
                        xytext=(pos + 0.2, o),
                        fontsize=8, color='#333333')

    # Tooltip
    if tooltip:
        tx, ty = pos + tooltip_offset[0], tooltip_offset[1]
        label = f"({SUBJECTS[pos-1]}, median: {median})"
        ax.annotate(label, (pos, median),
                    xytext=(tx, ty),
                    fontsize=8,
                    bbox=dict(boxstyle='round,pad=0.3', facecolor=color, alpha=0.8),
                    arrowprops=dict(arrowstyle='->', color='#333333'))


def generate_chart(filename, configs, title, show_tooltips_on=None, proximity_confusion=False):
    """
    configs: list of (median, iqr) per subject
    show_tooltips_on: list of subject indices with visible tooltips
    """
    fig, ax = plt.subplots(figsize=(14, 7))

    ground_truth = {'title': title, 'subjects': []}

    for i, (subject, color, (median, iqr)) in enumerate(zip(SUBJECTS, COLORS, configs)):
        data = make_grades(median, iqr)
        stats = box_stats(data)

        has_tooltip = show_tooltips_on and i in show_tooltips_on

        # Proximity confusion: offset tooltip of box 0 toward box 1
        t_offset = (0.35, median + 1)
        if proximity_confusion and i == 0:
            t_offset = (0.6, median - 0.5)  # bleeds toward next box

        outlier_labels = None
        if stats['outliers']:
            outlier_labels = random.sample(STUDENT_NAMES, min(len(stats['outliers']), 2))

        draw_boxplot(ax, i + 1, data, color, stats,
                     tooltip=has_tooltip,
                     tooltip_offset=t_offset,
                     outlier_labels=outlier_labels)

        ground_truth['subjects'].append({
            'name': subject,
            'color': color,
            **stats,
            'tooltip_visible': bool(has_tooltip)
        })

    ax.set_xlim(0, len(SUBJECTS) + 1)
    ax.set_ylim(-1, 22)
    ax.set_xticks(range(1, len(SUBJECTS) + 1))
    ax.set_xticklabels(SUBJECTS, fontsize=11)
    ax.set_ylabel('Note sur 20', fontsize=12)
    ax.set_title(title, fontsize=13, fontweight='bold')
    ax.yaxis.grid(True, linestyle='--', alpha=0.5)
    ax.set_axisbelow(True)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    plt.tight_layout()
    path = output_dir / filename
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Generated {filename}")
    return ground_truth


# Chart 1: Clean baseline
manifest['boxplot_01_baseline.png'] = generate_chart(
    'boxplot_01_baseline.png',
    configs=[(13, 4), (11, 3), (14, 5), (10, 6), (15, 2), (12, 4)],
    title='Résultats scolaires par matière - Classe 3B'
)

# Chart 2: Outliers only
manifest['boxplot_02_outliers.png'] = generate_chart(
    'boxplot_02_outliers.png',
    configs=[(13, 3), (11, 2), (14, 4), (10, 2), (15, 2), (12, 3)],
    title='Résultats scolaires par matière - Classe 4A (avec valeurs extrêmes)'
)

# Chart 3: Tooltips on 2 center boxes (index 0=Maths, 2=Histoire)
manifest['boxplot_03_tooltips_center.png'] = generate_chart(
    'boxplot_03_tooltips_center.png',
    configs=[(13, 4), (11, 3), (14, 5), (10, 6), (15, 2), (12, 4)],
    title='Résultats scolaires par matière - Classe 5C',
    show_tooltips_on=[0, 2]
)

# Chart 4: Tooltip proximity confusion (tooltip for Maths bleeds toward Français)
manifest['boxplot_04_proximity.png'] = generate_chart(
    'boxplot_04_proximity.png',
    configs=[(12, 3), (13, 3), (14, 4), (10, 5), (15, 2), (11, 4)],
    title='Résultats scolaires par matière - Classe 6D',
    show_tooltips_on=[0],
    proximity_confusion=True
)

# Chart 5: Extreme size variation
manifest['boxplot_05_size_variation.png'] = generate_chart(
    'boxplot_05_size_variation.png',
    configs=[(13, 8), (12, 1), (11, 7), (14, 1), (10, 6), (15, 2)],
    title='Résultats scolaires par matière - Classe 2E (dispersion variable)'
)

# Chart 6: Full complexity
manifest['boxplot_06_full_complexity.png'] = generate_chart(
    'boxplot_06_full_complexity.png',
    configs=[(13, 5), (12, 2), (14, 6), (10, 3), (15, 1), (11, 5)],
    title='Résultats scolaires par matière - Classe 1F (complet)',
    show_tooltips_on=[0, 5],
    proximity_confusion=True
)

# Save manifest
manifest_path = output_dir / 'ground_truth.json'
with open(manifest_path, 'w', encoding='utf-8') as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)

print(f"\nGenerated 6 box plots in {output_dir}/")
print(f"Ground truth saved to {manifest_path}")
```

---

## Testing Protocol

For each chart, compare Gemma output against `ground_truth.json`:

| Check | How to measure |
|-------|---------------|
| Outlier detection | Did it mention the outlier point and student name? |
| Tooltip attribution | Did it assign tooltip values to correct subject? |
| Proximity confusion | Did tooltip for Maths bleed into Français values? |
| Y-axis estimation | Abs(Gemma estimate - ground truth median). Target: <1 grade point |
| Box size reading | Did it identify which subjects have wide vs narrow IQR? |
