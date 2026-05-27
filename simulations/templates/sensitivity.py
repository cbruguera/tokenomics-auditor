"""
sensitivity.py — Parameter sensitivity and equilibrium mapping
tokenomics-analyzer | Phase 3.1 core script

Sweeps key parameter pairs across ±50% of their base values (11 × 11 = 121
grid points per pair) and measures three outcome metrics at each point:
  1. Max monthly dilution in months 0–36
  2. Circulating supply at month 36 as % of total supply
  3. Number of dilution events (>5% monthly) in months 0–36

Identifies the "viable operating region": the parameter subspace where
the model is stable across all three metrics simultaneously.

Run:
  python sensitivity.py <token_slug> [--model models/<token_slug>.yaml]

Outputs (to analysis/<token_slug>/):
  sensitivity_heatmap.png   — 3 outcome heatmaps for primary parameter pair
  equilibrium_map.png       — viable / unstable binary map, top 2 pairs
  sensitivity_data.csv      — full grid results
"""

import sys
import argparse
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from pathlib import Path
from itertools import product

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils import load_params, log_params

# Import emission helpers rather than re-implementing them
sys.path.insert(0, str(Path(__file__).resolve().parent))
from emission import vesting_schedule, emission_schedule, run_simulation as run_emission


# ── Metrics ────────────────────────────────────────────────────────────────────

def compute_metrics(params, n_steps=36):
    """
    Run emission simulation and return the three sensitivity metrics.
    Uses base scenario only (sensitivity testing at base conditions).
    """
    results = run_emission(params, n_steps=n_steps)
    base = results['base']

    dilution = base['dilution'] * 100  # convert to pct
    max_dilution = dilution.max()
    n_events = int((dilution > params['dilution_event_threshold'] * 100).sum())

    total = params['total_supply']
    circ_36 = base['circulating'][n_steps - 1]
    circ_36_pct = (circ_36 / total * 100) if total > 0 else 0.0

    return max_dilution, circ_36_pct, n_events


# ── Parameter pairs to sweep ───────────────────────────────────────────────────

def select_parameter_pairs(params):
    """
    Choose the 3 most informative parameter pairs for this token.
    Always include the universal pair. Add others based on token features.
    """
    pairs = []

    # Pair 1 (universal): emission rate vs initial circulating %
    if params.get('emission_rate_annual_pct') is not None:
        pairs.append((
            'emission_rate_annual_pct',
            'initial_circulating_pct',
            'Emission Rate (annual %)',
            'Initial Circulating (% of total)',
        ))
    else:
        pairs.append((
            'initial_circulating_pct',
            'dist_team',
            'Initial Circulating (% of total)',
            'Team Allocation (%)',
        ))

    # Pair 2: team vesting cliff vs team allocation (if team > 15%)
    if params.get('dist_team', 0) > 0.15:
        pairs.append((
            'vest_team_cliff',
            'dist_team',
            'Team Vesting Cliff (months)',
            'Team Allocation (fraction)',
        ))
    else:
        pairs.append((
            'dist_investors',
            'vest_investors_cliff',
            'Investor Allocation (fraction)',
            'Investor Vesting Cliff (months)',
        ))

    # Pair 3: ecosystem allocation vs cliff (governance/utility protocols)
    pairs.append((
        'dist_ecosystem',
        'vest_ecosystem_cliff',
        'Ecosystem Allocation (fraction)',
        'Ecosystem Vesting Cliff (months)',
    ))

    return pairs[:3]


def sweep_pair(params, param_a, param_b, n_grid=11, n_steps=36):
    """
    Sweep param_a × param_b across ±50% of their base values.
    Returns grid of (max_dilution, circ_36_pct, n_events).
    """
    base_a = params.get(param_a)
    base_b = params.get(param_b)

    # For zero or missing base values, infer a meaningful sweep range
    # from the parameter name: months → [0, 24], fractions → [0, 0.30], rates → [0, 0.20]
    def default_range(key, base):
        if base and base > 0:
            return max(base * 0.5, 0.001), base * 1.5
        if 'cliff' in key or 'dur' in key:
            return 0.0, 24.0
        if 'dist_' in key:
            return 0.0, 0.30
        if 'rate' in key or 'pct' in key:
            return 0.0, 0.20
        return 0.001, 1.0

    a_lo, a_hi = default_range(param_a, base_a)
    b_lo, b_hi = default_range(param_b, base_b)

    a_vals = np.linspace(a_lo, a_hi, n_grid)
    b_vals = np.linspace(b_lo, b_hi, n_grid)

    max_dil = np.zeros((n_grid, n_grid))
    circ_36 = np.zeros((n_grid, n_grid))
    n_ev = np.zeros((n_grid, n_grid), dtype=int)

    for i, a in enumerate(a_vals):
        for j, b in enumerate(b_vals):
            test_params = params.copy()
            test_params[param_a] = float(a)
            test_params[param_b] = float(b)
            # Recompute initial_circulating from pct if we're sweeping that
            if param_a == 'initial_circulating_pct' or param_b == 'initial_circulating_pct':
                test_params['initial_circulating'] = (
                    test_params['total_supply'] * test_params['initial_circulating_pct']
                )
            try:
                md, c36, ne = compute_metrics(test_params, n_steps=n_steps)
                max_dil[i, j] = md
                circ_36[i, j] = c36
                n_ev[i, j] = ne
            except Exception:
                max_dil[i, j] = np.nan
                circ_36[i, j] = np.nan
                n_ev[i, j] = 0

    return a_vals, b_vals, max_dil, circ_36, n_ev


# ── Viable region ──────────────────────────────────────────────────────────────

def viable_mask(max_dil, circ_36, n_ev, threshold_pct=5.0, max_circ_pct=70.0, max_events=3):
    """
    True where the model is in the 'viable operating region':
    - Max monthly dilution < threshold_pct
    - Circulating at 36m < max_circ_pct % of total
    - Fewer than max_events dilution events
    """
    return (max_dil < threshold_pct) & (circ_36 < max_circ_pct) & (n_ev < max_events)


# ── Output ─────────────────────────────────────────────────────────────────────

def save_outputs(sweep_results, params, output_dir, token_slug):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    name = params.get('token_name', token_slug)
    symbol = params.get('token_symbol', token_slug.upper())

    # ── sensitivity_heatmap.png — primary pair only ────────────────────────────
    primary = sweep_results[0]
    a_vals, b_vals, max_dil, circ_36, n_ev = (
        primary['a_vals'], primary['b_vals'],
        primary['max_dil'], primary['circ_36'], primary['n_ev'],
    )
    label_a, label_b = primary['label_a'], primary['label_b']

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    fig.suptitle(f'{name} ({symbol}) — Parameter Sensitivity: {label_a} × {label_b}',
                 fontsize=12, fontweight='bold')

    datasets = [
        (max_dil,   'Max Monthly Dilution (%)',              'YlOrRd'),
        (circ_36,   'Circulating @ 36m (% of total)',        'YlOrRd'),
        (n_ev,      'Dilution Events in 36m (count)',         'YlOrRd'),
    ]

    for ax, (data, title, cmap) in zip(axes, datasets):
        im = ax.imshow(data, aspect='auto', cmap=cmap, origin='lower')
        plt.colorbar(im, ax=ax, shrink=0.85)

        # Mark viable zone with green contour
        mask = viable_mask(max_dil, circ_36, n_ev)
        if mask.any():
            ax.contour(mask.astype(float), levels=[0.5], colors=['#16a34a'], linewidths=2)

        # Mark current parameter position with star
        n = len(a_vals)
        center = n // 2
        ax.plot(center, center, 'g*', markersize=14, label='Current params', zorder=5)

        n_a, n_b = len(a_vals), len(b_vals)
        tick_step = max(1, n_a // 5)
        ax.set_xticks(range(0, n_b, tick_step))
        ax.set_xticklabels([f'{v:.2g}' for v in b_vals[::tick_step]], rotation=30, fontsize=8)
        ax.set_yticks(range(0, n_a, tick_step))
        ax.set_yticklabels([f'{v:.2g}' for v in a_vals[::tick_step]], fontsize=8)
        ax.set_xlabel(label_b, fontsize=9)
        ax.set_ylabel(label_a, fontsize=9)
        ax.set_title(title, fontsize=10)

    axes[0].legend(fontsize=8, loc='upper right')
    plt.tight_layout()
    plt.savefig(out / 'sensitivity_heatmap.png', dpi=100, bbox_inches='tight')
    plt.close()
    print(f'  sensitivity_heatmap.png')

    # ── equilibrium_map.png — viable zone for top 2 pairs ─────────────────────
    n_pairs = min(2, len(sweep_results))
    fig, axes = plt.subplots(1, n_pairs, figsize=(7 * n_pairs, 5.5))
    if n_pairs == 1:
        axes = [axes]
    fig.suptitle(f'{name} ({symbol}) — Viable Operating Region', fontsize=12, fontweight='bold')

    for ax, sr in zip(axes, sweep_results[:n_pairs]):
        mask = viable_mask(sr['max_dil'], sr['circ_36'], sr['n_ev'])
        viable_pct = mask.mean() * 100

        cmap = matplotlib.colors.ListedColormap(['#fca5a5', '#86efac'])  # red=unstable, green=viable
        ax.imshow(mask.astype(int), aspect='auto', cmap=cmap, origin='lower', vmin=0, vmax=1)

        # Star for current params
        n_a = len(sr['a_vals'])
        ax.plot(n_a // 2, n_a // 2, 'k*', markersize=16, label=f'Current params', zorder=5)

        tick_step = max(1, n_a // 5)
        ax.set_xticks(range(0, len(sr['b_vals']), tick_step))
        ax.set_xticklabels([f'{v:.2g}' for v in sr['b_vals'][::tick_step]], rotation=30, fontsize=8)
        ax.set_yticks(range(0, n_a, tick_step))
        ax.set_yticklabels([f'{v:.2g}' for v in sr['a_vals'][::tick_step]], fontsize=8)
        ax.set_xlabel(sr['label_b'], fontsize=9)
        ax.set_ylabel(sr['label_a'], fontsize=9)
        ax.set_title(f'{sr["label_a"]} × {sr["label_b"]}\n'
                     f'Viable region: {viable_pct:.0f}% of parameter space', fontsize=10)
        ax.legend(fontsize=8)

    # Add legend patches
    from matplotlib.patches import Patch
    legend_els = [Patch(facecolor='#86efac', label='Viable'), Patch(facecolor='#fca5a5', label='Unstable')]
    axes[-1].legend(handles=legend_els, loc='lower right', fontsize=9)

    plt.tight_layout()
    plt.savefig(out / 'equilibrium_map.png', dpi=100, bbox_inches='tight')
    plt.close()
    print(f'  equilibrium_map.png')

    # ── sensitivity_data.csv ───────────────────────────────────────────────────
    rows = []
    for sr in sweep_results:
        for i, a in enumerate(sr['a_vals']):
            for j, b in enumerate(sr['b_vals']):
                rows.append({
                    'param_a': sr['param_a'],
                    'param_b': sr['param_b'],
                    'value_a': round(float(a), 6),
                    'value_b': round(float(b), 6),
                    'max_monthly_dilution_pct': round(float(sr['max_dil'][i, j]), 4),
                    'circulating_36m_pct': round(float(sr['circ_36'][i, j]), 4),
                    'n_dilution_events': int(sr['n_ev'][i, j]),
                    'viable': bool(viable_mask(
                        np.array([[sr['max_dil'][i, j]]]),
                        np.array([[sr['circ_36'][i, j]]]),
                        np.array([[sr['n_ev'][i, j]]]),
                    )[0, 0]),
                })
    pd.DataFrame(rows).to_csv(out / f'{token_slug}_sensitivity_data.csv', index=False)
    print(f'  {token_slug}_sensitivity_data.csv')

    # ── Summary ────────────────────────────────────────────────────────────────
    print(f'\n── Sensitivity Summary ───────────────────────────────────────────────')
    for sr in sweep_results:
        mask = viable_mask(sr['max_dil'], sr['circ_36'], sr['n_ev'])
        viable_pct = mask.mean() * 100
        # Is the center point (current params) viable?
        n = len(sr['a_vals'])
        c = n // 2
        center_viable = bool(mask[c, c])
        print(f'  {sr["label_a"]} × {sr["label_b"]}')
        print(f'    Viable region: {viable_pct:.0f}% of parameter space  |  '
              f'Current position: {"✓ viable" if center_viable else "✗ outside viable zone"}')


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Sensitivity analysis — tokenomics-analyzer')
    parser.add_argument('token_slug', help='Token slug, e.g. nova-protocol')
    parser.add_argument('--model', help='Path to TokenModel YAML')
    parser.add_argument('--grid', type=int, default=11, help='Grid size per axis (default 11)')
    args = parser.parse_args()

    slug = args.token_slug
    model_path = args.model or f'models/{slug}.yaml'

    print(f'\n── Loading parameters: {slug} ───────────────────────────────────────')
    params, sources = load_params(slug, model_path)
    log_params(params, sources)

    if not params.get('total_supply'):
        print('WARNING: total_supply unknown — using 1,000,000,000 as placeholder')
        params['total_supply'] = 1_000_000_000
        params['initial_circulating'] = params['initial_circulating'] or 150_000_000

    # Select parameter pairs to sweep
    pairs = select_parameter_pairs(params)
    n_grid = args.grid
    print(f'\n── Running sensitivity sweeps ({n_grid}×{n_grid} grid × {len(pairs)} pairs) ──')

    sweep_results = []
    for param_a, param_b, label_a, label_b in pairs:
        print(f'  Sweeping: {label_a} × {label_b} ...')
        a_vals, b_vals, max_dil, circ_36, n_ev = sweep_pair(
            params, param_a, param_b, n_grid=n_grid, n_steps=36
        )
        sweep_results.append({
            'param_a': param_a, 'param_b': param_b,
            'label_a': label_a, 'label_b': label_b,
            'a_vals': a_vals, 'b_vals': b_vals,
            'max_dil': max_dil, 'circ_36': circ_36, 'n_ev': n_ev,
        })

    output_dir = f'analysis/{slug}'
    print(f'\n── Saving outputs → {output_dir}/ ──────────────────────────────────')
    save_outputs(sweep_results, params, output_dir, slug)
    print(f'\nDone.\n')

    return sweep_results, params


if __name__ == '__main__':
    main()
