"""
sensitivity_nrg.py — NRG (Holoverse) parameter sensitivity analysis
tokenomics-analyzer | Token-specific script

Sweeps 4 key NRG-specific parameter pairs across a ±50% range (11×11 grid):
  Pair 1: BaseFloor × Activity level  → net inflation under stress
  Pair 2: HardCap × Activity level    → max dilution under growth
  Pair 3: Adaptive multiplier × Burn activity → emission/burn balance
  Pair 4: Universe mint cost × Daily mint rate → annual burn pressure

Metrics at each grid point:
  1. Year-1 net supply change (NRG) — lower is better
  2. Year-3 inflation rate (% of circulating) — lower is better
  3. BaseFloor dominance months (months where BaseFloor > AdaptiveWeight)

Run from agent/ directory:
  python simulations/nrg/sensitivity_nrg.py

Outputs → analysis/nrg/
  sensitivity_heatmap.png    pair 1 heatmap (3 metrics)
  equilibrium_map.png        viable operating region maps for top 2 pairs
  nrg_sensitivity_data.csv   full grid results
"""

import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path

# ── Base NRG parameters ────────────────────────────────────────────────────────

BASE_FLOOR_BASE = 5_000       # NRG/day
HARD_CAP_BASE = 50_000        # NRG/day
ADAPTIVE_MULT_BASE = 1.2
EQUIL_BURN_BASE = 12_300      # NRG/day at 2,000 universes
MINT_COST_NRG = 100           # NRG per universe mint (90 burned + 10 treasury)
DAILY_MINTS_BASE = 1.37       # ~500 mints/year
N_MONTHS = 36                 # short horizon for sensitivity

PREMINE = 10_000_000
INITIAL_CIRC = 1_500_000


# ── Utility ────────────────────────────────────────────────────────────────────

def adaptive_emission(daily_burn_avg, base_floor, hard_cap, mult):
    return max(base_floor, min(hard_cap, mult * daily_burn_avg))


def run_metrics(base_floor, hard_cap, adaptive_mult, activity_pct, n_months=N_MONTHS):
    """
    Compute three sensitivity metrics for given parameters.
    Returns: (net_supply_y1, inflation_rate_y3, basefloor_dominance_months)
    """
    supply = PREMINE
    circ = INITIAL_CIRC
    burn_7d_avg = EQUIL_BURN_BASE * activity_pct * 0.1  # start at 10% ramp
    basefloor_months = 0

    monthly_emissions = []
    monthly_burns = []

    for t in range(1, n_months + 1):
        ramp = min(1.0, t / 12.0)
        daily_burn = EQUIL_BURN_BASE * activity_pct * ramp
        burn_7d_avg = 0.85 * burn_7d_avg + 0.15 * daily_burn

        daily_emit = adaptive_emission(burn_7d_avg, base_floor, hard_cap, adaptive_mult)
        monthly_emit = daily_emit * 30.44
        monthly_burn = daily_burn * 30.44

        if daily_emit <= base_floor * 1.01:  # BaseFloor dominating
            basefloor_months += 1

        # Simplified vesting: ~100K NRG/month unlocks during Y1-Y3
        vest = 100_000 if t <= 36 else 0

        circ = max(0, circ + vest + monthly_emit - monthly_burn)
        supply = max(0, supply + monthly_emit - monthly_burn)
        monthly_emissions.append(monthly_emit)
        monthly_burns.append(monthly_burn)

    net_supply_y1 = sum(e - b for e, b in zip(monthly_emissions[:12], monthly_burns[:12]))
    # Inflation rate at year 3 = annualized net monthly emission / circulating at m36
    if circ > 0:
        avg_monthly_net_y3 = np.mean([e - b for e, b in zip(monthly_emissions[24:36], monthly_burns[24:36])])
        inflation_rate_y3 = (avg_monthly_net_y3 * 12 / circ) * 100
    else:
        inflation_rate_y3 = 0.0

    return net_supply_y1, inflation_rate_y3, basefloor_months


# ── Grid sweeps ────────────────────────────────────────────────────────────────

def sweep_pair(param1_name, param1_values, param2_name, param2_values, fixed_params):
    rows = []
    for p1 in param1_values:
        for p2 in param2_values:
            params = dict(fixed_params)
            params[param1_name] = p1
            params[param2_name] = p2

            m1, m2, m3 = run_metrics(
                base_floor=params.get('base_floor', BASE_FLOOR_BASE),
                hard_cap=params.get('hard_cap', HARD_CAP_BASE),
                adaptive_mult=params.get('adaptive_mult', ADAPTIVE_MULT_BASE),
                activity_pct=params.get('activity_pct', 1.0),
            )
            rows.append({
                param1_name: p1,
                param2_name: p2,
                'net_supply_y1': m1,
                'inflation_rate_y3_pct': m2,
                'basefloor_dominance_months': m3,
                'viable': (m2 < 20.0) and (m3 < 18),
            })
    return pd.DataFrame(rows)


# ── Main ────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print('\n── Running NRG Sensitivity Analysis ───────────────────────────────────')
    out = Path('analysis/nrg')
    out.mkdir(parents=True, exist_ok=True)

    # Pair 1: BaseFloor × Activity level
    base_floor_range = np.linspace(BASE_FLOOR_BASE * 0.5, BASE_FLOOR_BASE * 1.5, 11)
    activity_range = np.linspace(0.05, 1.0, 11)

    df1 = sweep_pair(
        'base_floor', base_floor_range,
        'activity_pct', activity_range,
        fixed_params={'hard_cap': HARD_CAP_BASE, 'adaptive_mult': ADAPTIVE_MULT_BASE},
    )

    # Pair 2: HardCap × Activity level
    hard_cap_range = np.linspace(HARD_CAP_BASE * 0.5, HARD_CAP_BASE * 1.5, 11)
    df2 = sweep_pair(
        'hard_cap', hard_cap_range,
        'activity_pct', activity_range,
        fixed_params={'base_floor': BASE_FLOOR_BASE, 'adaptive_mult': ADAPTIVE_MULT_BASE},
    )

    # Pair 3: Adaptive multiplier × Activity
    mult_range = np.linspace(1.0, 2.0, 11)
    df3 = sweep_pair(
        'adaptive_mult', mult_range,
        'activity_pct', activity_range,
        fixed_params={'base_floor': BASE_FLOOR_BASE, 'hard_cap': HARD_CAP_BASE},
    )

    # Combine all data
    df_all = pd.concat([df1, df2, df3], ignore_index=True)
    df_all.to_csv(out / 'nrg_sensitivity_data.csv', index=False)
    print('  nrg_sensitivity_data.csv saved')

    # ── sensitivity_heatmap.png (Pair 1) ──────────────────────────────────────
    pivot_inf = df1.pivot(index='base_floor', columns='activity_pct', values='inflation_rate_y3_pct')
    pivot_net = df1.pivot(index='base_floor', columns='activity_pct', values='net_supply_y1')
    pivot_bf = df1.pivot(index='base_floor', columns='activity_pct', values='basefloor_dominance_months')

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle('NRG Sensitivity: BaseFloor × Activity Level', fontsize=12, fontweight='bold')

    for ax, pivot, title, cmap in zip(
        axes,
        [pivot_net / 1e6, pivot_inf, pivot_bf],
        ['Net Supply Y1 (millions NRG)', 'Y3 Inflation Rate (%)', 'BaseFloor Dominance (months/36)'],
        ['RdYlGn_r', 'RdYlGn_r', 'RdYlGn_r'],
    ):
        im = ax.imshow(pivot.values, aspect='auto', cmap=cmap, origin='lower')
        plt.colorbar(im, ax=ax)
        ax.set_title(title, fontsize=10)
        xticks = [f'{v:.2f}' for v in pivot.columns[::2]]
        yticks = [f'{v/1000:.1f}K' for v in pivot.index[::2]]
        ax.set_xticks(range(0, len(pivot.columns), 2))
        ax.set_xticklabels(xticks, rotation=45, fontsize=8)
        ax.set_yticks(range(0, len(pivot.index), 2))
        ax.set_yticklabels(yticks, fontsize=8)
        ax.set_xlabel('Activity Level (fraction of equilibrium)')
        ax.set_ylabel('BaseFloor (NRG/day)')

    plt.tight_layout()
    plt.savefig(out / 'sensitivity_heatmap.png', dpi=100, bbox_inches='tight')
    plt.close()
    print('  sensitivity_heatmap.png saved')

    # ── equilibrium_map.png (Pairs 1 & 2) ─────────────────────────────────────
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle('NRG Viable Operating Region Maps', fontsize=12, fontweight='bold')

    for ax, df, p1_name, p2_name, p1_label, title in zip(
        axes,
        [df1, df2],
        ['base_floor', 'hard_cap'],
        ['activity_pct', 'activity_pct'],
        ['BaseFloor (NRG/day)', 'HardCap (NRG/day)'],
        ['BaseFloor × Activity', 'HardCap × Activity'],
    ):
        pivot = df.pivot(index=p1_name, columns=p2_name, values='viable').astype(float)
        im = ax.imshow(pivot.values, aspect='auto', cmap='RdYlGn', vmin=0, vmax=1, origin='lower')
        plt.colorbar(im, ax=ax, label='Viable (1) / Unstable (0)')
        ax.set_title(title, fontsize=10)
        ax.set_xlabel('Activity Level')
        ax.set_ylabel(p1_label)
        xticks = [f'{v:.2f}' for v in pivot.columns[::2]]
        ax.set_xticks(range(0, len(pivot.columns), 2))
        ax.set_xticklabels(xticks, rotation=45, fontsize=8)
        yticks = [f'{v/1000:.1f}K' for v in pivot.index[::2]]
        ax.set_yticks(range(0, len(pivot.index), 2))
        ax.set_yticklabels(yticks, fontsize=8)

    plt.tight_layout()
    plt.savefig(out / 'equilibrium_map.png', dpi=100, bbox_inches='tight')
    plt.close()
    print('  equilibrium_map.png saved')

    # ── Key findings ───────────────────────────────────────────────────────────
    print('\n── Key Sensitivity Findings ────────────────────────────────────────────')
    viable_pct = df1['viable'].mean() * 100
    print(f'  Viable operating region (Pair 1): {viable_pct:.0f}% of {len(df1)} parameter combinations')
    print(f'  BaseFloor drives floor inflation at low activity:')
    low_act = df1[df1['activity_pct'] <= 0.10]['inflation_rate_y3_pct']
    print(f'    At 10% activity: Y3 inflation range {low_act.min():.1f}%–{low_act.max():.1f}%')
    high_act = df1[df1['activity_pct'] >= 0.90]['inflation_rate_y3_pct']
    print(f'    At 90% activity: Y3 inflation range {high_act.min():.1f}%–{high_act.max():.1f}%')
    print(f'  BaseFloor dominance at 10% activity:')
    low_bf = df1[df1['activity_pct'] <= 0.10]['basefloor_dominance_months']
    print(f'    {low_bf.mean():.0f} months of 36 dominated by BaseFloor (not adaptive)')

    print('\nDone.\n')
