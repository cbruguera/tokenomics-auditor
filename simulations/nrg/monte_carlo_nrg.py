"""
monte_carlo_nrg.py — NRG (Holoverse) price simulation
tokenomics-analyzer | Token-specific script

1,000-path Monte Carlo price simulation for NRG token using:
  - Scenario-specific demand drift (Base / Bear / Stress)
  - Supply dilution headwind from emission_nrg.py output
  - Holoverse-specific demand drivers: universe mint adoption curve
  - Base case assumption: 500 mints/year → scales with demand growth

Run from agent/ directory:
  python simulations/nrg/emission_nrg.py    (first, to generate dilution series)
  python simulations/nrg/monte_carlo_nrg.py

Outputs → analysis/nrg/
  price_bands.png    P10/P25/P50/P75/P90 price bands, 3 scenarios
  nrg_mc_paths.csv   monthly percentile statistics per scenario
"""

import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from pathlib import Path

# ── Simulation parameters ──────────────────────────────────────────────────────

INITIAL_PRICE = 1.00      # USD — normalized at launch
N_RUNS = 1000
N_STEPS = 120             # months
SEED = 42

PRICE_VOL_ANNUAL = 1.20   # 120% annualized crypto baseline
DEMAND_PRICE_CORR = 0.70  # price-demand correlation

TAIL_PROB_ANNUAL = 0.05   # 5% chance of -90% demand shock per year
TAIL_MAGNITUDE = 0.90     # -90%

# Scenario demand drift parameters
SCENARIOS = {
    'base': {
        'label': 'Base',
        'color': '#2563eb',
        # Y1-Y3: +20% annual demand (500 universe mints in Y1 growing to 2,000 by Y3)
        # Y4+: +10% annual
        'demand_fn': lambda t: 0.20 if t < 36 else 0.10,
    },
    'bear': {
        'label': 'Bear',
        'color': '#dc2626',
        # Flat Y1 → -30% Y2 → -50% Y3 → flat thereafter
        'demand_fn': lambda t: 0.0 if t < 12 else (-0.30 if t < 24 else (-0.50 if t < 36 else 0.0)),
    },
    'stress': {
        'label': 'Stress',
        'color': '#7c3aed',
        # -80% price shock over 6 months starting month 12
        'shock_start': 12,
        'shock_end': 18,
        'shock_monthly_drop': (1 - 0.80) ** (1/6),  # compounds to -80% over 6 months
        'demand_fn': None,
    },
}

SCENARIO_CONFIG = {
    'base':   {'label': 'Base',   'color': '#2563eb'},
    'bear':   {'label': 'Bear',   'color': '#dc2626'},
    'stress': {'label': 'Stress', 'color': '#7c3aed'},
}


def annual_demand_growth(t, scen_name):
    if scen_name == 'stress':
        s = SCENARIOS['stress']
        if s['shock_start'] <= t < s['shock_end']:
            return (s['shock_monthly_drop'] - 1) * 12  # annualized
        return 0.0
    return SCENARIOS[scen_name]['demand_fn'](t)


def run_simulation(dilution_series=None):
    np.random.seed(SEED)

    sigma_monthly = PRICE_VOL_ANNUAL / np.sqrt(12)
    rho = DEMAND_PRICE_CORR
    tail_monthly = 1 - (1 - TAIL_PROB_ANNUAL) ** (1/12)

    results = {}

    for scen_name in ('base', 'bear', 'stress'):
        z_demand = np.random.randn(N_RUNS, N_STEPS)
        z_noise = np.random.randn(N_RUNS, N_STEPS)
        z_price = rho * z_demand + np.sqrt(max(1 - rho**2, 0)) * z_noise

        tail_mask = np.random.rand(N_RUNS, N_STEPS) < tail_monthly
        tail_shock = np.where(tail_mask, np.log(1 - TAIL_MAGNITUDE + 1e-9), 0.0)

        drift = np.array([annual_demand_growth(t, scen_name) / 12 for t in range(N_STEPS)])

        headwind = np.zeros(N_STEPS)
        if dilution_series is not None and len(dilution_series) >= N_STEPS:
            headwind = np.array(dilution_series[:N_STEPS]) * 0.005  # 0.5× dilution pct headwind

        log_increments = (
            (drift - headwind - 0.5 * sigma_monthly**2)
            + sigma_monthly * z_price
            + tail_shock
        )

        log_paths = np.cumsum(log_increments, axis=1)
        log_paths = np.hstack([np.zeros((N_RUNS, 1)), log_paths[:, :-1]])
        paths = INITIAL_PRICE * np.exp(log_paths)

        results[scen_name] = {
            'paths': paths,
            'p10': np.percentile(paths, 10, axis=0),
            'p25': np.percentile(paths, 25, axis=0),
            'p50': np.percentile(paths, 50, axis=0),
            'p75': np.percentile(paths, 75, axis=0),
            'p90': np.percentile(paths, 90, axis=0),
        }

    return results


def save_outputs(results, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    months = np.arange(N_STEPS)

    # ── price_bands.png ────────────────────────────────────────────────────────
    fig, axes = plt.subplots(1, 3, figsize=(16, 6), sharey=False)
    fig.suptitle(f'NRG (Holoverse) — Monte Carlo Price Simulation ({N_RUNS:,} paths)',
                 fontsize=13, fontweight='bold')

    for ax, scen_name in zip(axes, ['base', 'bear', 'stress']):
        r = results[scen_name]
        cfg = SCENARIO_CONFIG[scen_name]
        c = cfg['color']

        ax.fill_between(months, r['p10'], r['p90'], alpha=0.15, color=c, label='P10–P90')
        ax.fill_between(months, r['p25'], r['p75'], alpha=0.30, color=c, label='P25–P75')
        ax.plot(months, r['p50'], color=c, linewidth=2.0, label='P50 (median)')
        ax.axhline(INITIAL_PRICE, color='#6b7280', linestyle=':', linewidth=1, label='Launch price')

        for m in (12, 36, 60):
            if m < N_STEPS:
                ax.annotate(f'${r["p50"][m]:.2f}',
                            xy=(m, r['p50'][m]),
                            xytext=(5, 5), textcoords='offset points',
                            fontsize=7, color=c)

        ax.set_title(f'{cfg["label"]} Scenario', fontsize=11)
        ax.set_xlabel('Month')
        ax.set_ylabel('Price (USD)')
        ax.legend(fontsize=8, loc='upper right')
        ax.set_xlim(0, N_STEPS - 1)
        ax.set_ylim(bottom=0)
        ax.grid(alpha=0.3)

        max_val = r['p90'].max()
        if max_val >= 100:
            ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'${x:.0f}'))
        elif max_val >= 1:
            ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'${x:.2f}'))
        else:
            ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'${x:.3f}'))

    plt.tight_layout()
    plt.savefig(out / 'price_bands.png', dpi=100, bbox_inches='tight')
    plt.close()
    print('  price_bands.png saved')

    # ── nrg_mc_paths.csv ───────────────────────────────────────────────────────
    rows = []
    for scen_name in ('base', 'bear', 'stress'):
        r = results[scen_name]
        for t in range(N_STEPS):
            rows.append({
                'scenario': scen_name,
                'month': t,
                'p10': round(r['p10'][t], 6),
                'p25': round(r['p25'][t], 6),
                'p50': round(r['p50'][t], 6),
                'p75': round(r['p75'][t], 6),
                'p90': round(r['p90'][t], 6),
                'mean': round(r['paths'][:, t].mean(), 6),
            })
    pd.DataFrame(rows).to_csv(out / 'nrg_mc_paths.csv', index=False)
    print('  nrg_mc_paths.csv saved')

    print(f'\n── Monte Carlo Summary ({N_RUNS:,} paths, seed={SEED}) ──────────────────')
    for scen_name in ('base', 'bear', 'stress'):
        r = results[scen_name]
        p50_12 = r['p50'][min(12, N_STEPS-1)]
        p50_36 = r['p50'][min(36, N_STEPS-1)]
        p10_36 = r['p10'][min(36, N_STEPS-1)]
        near_zero = (r['paths'][:, min(36, N_STEPS-1)] < 0.01 * INITIAL_PRICE).mean()
        print(f'  {scen_name.capitalize():7s}  P50@12m=${p50_12:.3f}  P50@36m=${p50_36:.3f}'
              f'  P10@36m=${p10_36:.3f}  near-zero@36m={near_zero*100:.1f}%')


if __name__ == '__main__':
    print('\n── Running NRG Monte Carlo Price Simulation ────────────────────────────')

    dilution_series = None
    supply_csv = Path('analysis/nrg/nrg_supply_data.csv')
    if supply_csv.exists():
        df = pd.read_csv(supply_csv)
        dilution_series = df[df['scenario'] == 'base']['monthly_dilution_pct'].values
        print(f'  Loaded dilution series from emission output ({len(dilution_series)} months)')
    else:
        print('  No emission output found — running without dilution headwind')
        print('  Run emission_nrg.py first for full accuracy.')

    results = run_simulation(dilution_series=dilution_series)

    out_dir = 'analysis/nrg'
    print(f'── Saving outputs → {out_dir}/ ─────────────────────────────────────────')
    save_outputs(results, out_dir)
    print('\nDone.\n')
