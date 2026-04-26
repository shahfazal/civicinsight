import matplotlib.pyplot as plt
import numpy as np
import json
import random
from pathlib import Path

# French-style number formatting
def format_french(num):
    return f"{num:,.1f}".replace(",", " ").replace(".", ",")

# Color palette (match elections viz)
COLORS = ['#E91E63', '#FF6B9D', '#FFC107', '#9E9E9E', '#2196F3', '#1A1A1A']

def generate_stacked_bar(
    num_bars=5,
    num_segments=6,
    distribution='random',  # 'even', 'dominant', 'random', 'tiny'
    output_path='stacked_bar_test.png'
):
    """
    Generate a horizontal 100% stacked bar chart.

    Args:
        num_bars: Number of horizontal bars (categories)
        num_segments: Number of colored segments per bar
        distribution: How to distribute segment widths
        output_path: Where to save PNG

    Returns:
        dict: Ground truth data for validation
    """

    # Generate segment widths based on distribution type
    if distribution == 'even':
        # Equal segments
        segments = [100 / num_segments] * num_segments

    elif distribution == 'dominant':
        # One dominant segment (60%), rest split remainder
        segments = [60.0] + [(40.0 / (num_segments - 1))] * (num_segments - 1)
        random.shuffle(segments)

    elif distribution == 'tiny':
        # Include some very small segments (<5%)
        segments = [40.0, 25.0, 15.0, 10.0, 7.0, 3.0][:num_segments]
        # Pad if needed
        while len(segments) < num_segments:
            segments.append(random.uniform(2, 5))
        # Normalize to 100%
        total = sum(segments)
        segments = [(s / total) * 100 for s in segments]

    else:  # 'random'
        # Random distribution
        segments = [random.uniform(5, 30) for _ in range(num_segments)]
        total = sum(segments)
        segments = [(s / total) * 100 for s in segments]

    # Generate bar data (same segment distribution for all bars, small variance)
    bar_data = []
    bar_labels = []

    for i in range(num_bars):
        # Add small random variance per bar (±2%)
        bar_segments = [max(1, s + random.uniform(-2, 2)) for s in segments]
        # Re-normalize to 100%
        total = sum(bar_segments)
        bar_segments = [(s / total) * 100 for s in bar_segments]

        bar_data.append(bar_segments)

        # Generate French-style labels
        price_range = random.randint(800, 4000)
        bar_labels.append(f"Prix {format_french(price_range)}-{format_french(price_range + 200)} €/m²")

    # Create plot
    fig, ax = plt.subplots(figsize=(12, 8))

    # Plot stacked bars
    left = np.zeros(num_bars)
    base_labels = ['Extrême gauche', 'Gauche', 'Centre', 'Divers', 'Droite', 'Extrême droite']
    segment_labels = (base_labels * ((num_segments // len(base_labels)) + 1))[:num_segments]

    for seg_idx in range(num_segments):
        widths = [bar[seg_idx] for bar in bar_data]
        ax.barh(
            range(num_bars),
            widths,
            left=left,
            color=COLORS[seg_idx % len(COLORS)],
            label=segment_labels[seg_idx]
        )
        left += widths

    # Styling
    ax.set_xlabel('Part des communes (%)', fontsize=12)
    ax.set_yticks(range(num_bars))
    ax.set_yticklabels(bar_labels)
    ax.set_xlim(0, 100)
    ax.set_xticks([0, 20, 40, 60, 80, 100])
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.05), ncol=num_segments)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    # Generate ground truth
    ground_truth = {
        'num_bars': num_bars,
        'num_segments': num_segments,
        'distribution': distribution,
        'bars': [
            {
                'label': bar_labels[i],
                'segments': [
                    {
                        'label': segment_labels[j],
                        'value': round(bar_data[i][j], 1),
                        'color': COLORS[j % len(COLORS)]
                    }
                    for j in range(num_segments)
                ]
            }
            for i in range(num_bars)
        ]
    }

    return ground_truth


def generate_test_suite():
    """Generate full test suite of 15 variations."""

    output_dir = Path('test_charts')
    output_dir.mkdir(exist_ok=True)

    manifest = {}

    # Test 1-3: Vary number of bars (3, 5, 8)
    for i, num_bars in enumerate([3, 5, 8]):
        filename = f'stacked_bar_bars_{num_bars}_{i+1:03d}.png'
        path = output_dir / filename
        truth = generate_stacked_bar(
            num_bars=num_bars,
            num_segments=6,
            distribution='random',
            output_path=str(path)
        )
        manifest[filename] = truth
        print(f"Generated {filename}")

    # Test 4-6: Vary number of segments (3, 6, 10)
    for i, num_segs in enumerate([3, 6, 10]):
        filename = f'stacked_bar_segs_{num_segs}_{i+4:03d}.png'
        path = output_dir / filename
        truth = generate_stacked_bar(
            num_bars=5,
            num_segments=num_segs,
            distribution='random',
            output_path=str(path)
        )
        manifest[filename] = truth
        print(f"Generated {filename}")

    # Test 7-10: Distribution types
    for i, dist in enumerate(['even', 'dominant', 'random', 'tiny']):
        filename = f'stacked_bar_dist_{dist}_{i+7:03d}.png'
        path = output_dir / filename
        truth = generate_stacked_bar(
            num_bars=5,
            num_segments=6,
            distribution=dist,
            output_path=str(path)
        )
        manifest[filename] = truth
        print(f"Generated {filename}")

    # Test 11-15: Random variations
    for i in range(5):
        filename = f'stacked_bar_random_{i+11:03d}.png'
        path = output_dir / filename
        truth = generate_stacked_bar(
            num_bars=random.randint(4, 7),
            num_segments=random.randint(4, 8),
            distribution=random.choice(['even', 'dominant', 'random', 'tiny']),
            output_path=str(path)
        )
        manifest[filename] = truth
        print(f"Generated {filename}")

    # Save manifest
    manifest_path = output_dir / 'ground_truth.json'
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"\nGenerated 15 test charts in {output_dir}/")
    print(f"Ground truth saved to {manifest_path}")

    return manifest


if __name__ == '__main__':
    generate_test_suite()
