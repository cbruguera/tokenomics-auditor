"""
monte_carlo.py — 1,000-path price simulation
tokenomics-analyzer | Phase 3.1 core script

Models token price over 120 months using log-normal GBM with:
  - Scenario-specific demand drift (Base / Bear / Stress)
  - Supply dilution headwind from emission.py output
  - Correlated demand shocks (price-demand correlation = 0.70)
  - Tail events: 5% annual probability of −90% demand shock

Run:
  python monte_carlo.py <token_slug> [--model models/<token_slug>.yaml]

Outputs (to analysis/<token_slug>/):
  price_bands.png    — P10/P25/P50/P75/P90 price bands, all 3 scenarios
  mc_paths.csv       — monthly percentile statistics per scenario
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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils import load_params, log_params

# ── Scenario drift definitions ─────────────────────────────────────────────────
# Returns the annual demand growth rate for a given month and scenario.
# Price drift = demand_growth / 12 (monthly), minus dilution headwind.

def annual_demand_growth(t, scenario_name, params):
    p = params
    if scenario_name == 'base':
        yr = t // 12
        return p['base_demand_growth_y1_y3'] if yr < 3 else p['base_demand_growth_y4plus']
    elif scenario_name == 'bear':
        yr = t // 12
        if yr == 0:
            return p['bear_demand_y1']
        elif yr == 1:
            return p['bear_demand_y2']
        elif yr == 2:
            return p['bear_demand_y3']
        else:
            return 0.0
    elif scenario_name == 'stress':
        shock_start = int(p['stress_shock_month'])
        shock_end = shock_start + int(p['stress_shock_duration_months'])
        if shock_start <= t < shock_end:
            # Monthly price drop that compounds to -stress_shock_price_drop% over the duration
            drop = p['stress_shock_price_drop']
            monthly_drop = (1 - drop) ** (1 / p['stress_shock_duration_months'])
            return (monthly_drop - 1) * 12  # annualized
        else:
            return 0.0
    return 0.0


def run_simulation(params, dilution_series=None, n_steps=120):
    """
    Run Monte Carlo price simulation across all scenarios.

    Args:
        params:          parameter dict from load_params()
        dilution_series: optional np.array of monthly dilution % from emission.py
                         (base scenario), used as price headwind. If None, ignored.
        n_steps:         number of monthly steps (default 120)

    Returns:
        results: dict scenario_name → {
            'paths':      (n_runs × n_steps) price array,
            'p10/p25/p50/p75/p90': percentile arrays
        }
    """
    np.random.seed(int(params['seed']))

    n_runs = int(params['n_runs'])
    sigma_annual = params['price_vol_annual']
    sigma_monthly = sigma_annual / np.sqrt(12)
    rho = params['demand_price_correlation']

    tail_prob_monthly = 1 - (1 - params['tail_event_prob_annual']) ** (1 / 12)
    tail_drop = params['tail_event_magnitude']

    scenarios = ['base', 'bear', 'stress']
    results = {}

    for scen in scenarios:
        # Correlated random draws: shape (n_runs, n_steps)
        z_demand = np.random.randn(n_runs, n_steps)
        z_noise = np.random.randn(n_runs, n_steps)
        z_price = rho * z_demand + np.sqrt(max(1 - rho ** 2, 0)) * z_noise

        # Tail event mask: rare but severe demand shocks
        tail_mask = np.random.rand(n_runs, n_steps) < tail_prob_monthly
        tail_shock = np.where(tail_mask, np.log(1 - tail_drop + 1e-9), 0.0)

        # Monthly drift per step
        drift = np.array([annual_demand_growth(t, scen, params) / 12 for t in range(n_steps)])

        # Dilution headwind: each 1% of monthly dilution ≈ 0.5% price headwind
        headwind = np.zeros(n_steps)
        if dilution_series is not None and len(dilution_series) >= n_steps:
            headwind = np.array(dilution_series[:n_steps]) * 0.005  # 0.5× dilution pct

        # GBM log-price increments
        log_increments = (
            (drift - headwind - 0.5 * sigma_monthly ** 2)     # deterministic drift
            + sigma_monthly * z_price                          # stochastic
            + tail_shock                                       # tail events
        )  # shape: (n_runs, n_steps)

        # Cumulative price paths starting at initial_price_usd
        log_paths = np.cumsum(log_increments, axis=1)
        log_paths = np.hstack([np.zeros((n_runs, 1)), log_paths[:, :-1]])
        paths = params['initial_price_usd'] * np.exp(log_paths)

        # Percentile bands
        pcts = {
            'p10': np.percentile(paths, 10, axis=0),
            'p25': np.percentile(paths, 25, axis=0),
            'p50': np.percentile(paths, 50, axis=0),
            'p75': np.percentile(paths, 75, axis=0),
            'p90': np.percentile(paths, 90, axis=0),
        }

        results[scen] = {'paths': paths, **pcts}

    return results


def save_outputs(results, params, output_dir, token_slug):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    name = params.get('token_name', token_slug)
    symbol = params.get('token_symbol', token_slug.upper())
    n_steps = results['base']['p50'].shape[0]
    months = np.arange(n_steps)

    SCENARIO_CONFIG = {
        'base':   {'label': 'Base',   'color': '#2563eb'},
        'bear':   {'label': 'Bear',   'color': '#dc2626'},
        'stress': {'label': 'Stress', 'color': '#7c3aed'},
    }

    # ── price_bands.png ────────────────────────────────────────────────────────
    fig, axes = plt.subplots(1, 3, figsize=(16, 6), sharey=False)
    fig.suptitle(f'{name} ({symbol}) — Monte Carlo Price Simulation ({params["n_runs"]:,} paths)',
                 fontsize=13, fontweight='bold')

    for ax, scen_name in zip(axes, ['base', 'bear', 'stress']):
        r = results[scen_name]
        cfg = SCENARIO_CONFIG[scen_name]
        color = cfg['color']

        ax.fill_between(months, r['p10'], r['p90'], alpha=0.15, color=color, label='P10–P90')
        ax.fill_between(months, r['p25'], r['p75'], alpha=0.30, color=color, label='P25–P75')
        ax.plot(months, r['p50'], color=color, linewidth=2.0, label='P50 (median)')
        ax.axhline(params['initial_price_usd'], color='#6b7280', linestyle=':', linewidth=1, label='Launch price')

        # Annotate P50 at key months
        for m in (12, 36, 60):
            if m < n_steps:
                ax.annotate(f'${r["p50"][m]:.2f}',
                            xy=(m, r['p50'][m]),
                            xytext=(5, 5), textcoords='offset points',
                            fontsize=7, color=color)

        ax.set_title(f'{cfg["label"]} Scenario', fontsize=11)
        ax.set_xlabel('Month')
        ax.set_ylabel('Price (USD)')
        ax.legend(fontsize=8, loc='upper right')
        ax.set_xlim(0, n_steps - 1)
        ax.set_ylim(bottom=0)
        ax.grid(alpha=0.3)

        # Format y-axis
        max_val = r['p90'].max()
        if max_val >= 100:
            ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'${x:.0f}'))
        else:
            ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'${x:.2f}'))

    plt.tight_layout()
    plt.savefig(out / 'price_bands.png', dpi=100, bbox_inches='tight')
    plt.close()
    print(f'  price_bands.png')

    # ── mc_paths.csv ───────────────────────────────────────────────────────────
    rows = []
    for scen_name in ('base', 'bear', 'stress'):
        r = results[scen_name]
        for t in range(n_steps):
            rows.append({
                'scenario': scen_name,
                'month': t,
                'p10': round(r['p10'][t], 6),
                'p25': round(r['p25'][t], 6),
                'p50': round(r['p50'][t], 6),
                'p75': round(r['p75'][t], 6),
                'p90': round(r['p90'][t], 6),
                'mean': round(results[scen_name]['paths'][:, t].mean(), 6),
            })
    pd.DataFrame(rows).to_csv(out / f'{token_slug}_mc_paths.csv', index=False)
    print(f'  {token_slug}_mc_paths.csv')

    # ── Summary ────────────────────────────────────────────────────────────────
    print(f'\n── Monte Carlo Summary ({params["n_runs"]:,} paths, seed={params["seed"]}) ────────')
    for scen_name in ('base', 'bear', 'stress'):
        r = results[scen_name]
        p50_12 = r['p50'][min(12, n_steps-1)]
        p50_36 = r['p50'][min(36, n_steps-1)]
        p10_36 = r['p10'][min(36, n_steps-1)]
        near_zero = (results[scen_name]['paths'][:, min(36, n_steps-1)] < 0.01 * params['initial_price_usd']).mean()
        print(f'  {scen_name.capitalize():6s}  P50@12m=${p50_12:.3f}  P50@36m=${p50_36:.3f}'
              f'  P10@36m=${p10_36:.3f}  near-zero@36m={near_zero*100:.1f}%')


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Monte Carlo price simulation — tokenomics-analyzer')
    parser.add_argument('token_slug', help='Token slug, e.g. nova-protocol')
    parser.add_argument('--model', help='Path to TokenModel YAML')
    args = parser.parse_args()

    slug = args.token_slug
    model_path = args.model or f'models/{slug}.yaml'

    print(f'\n── Loading parameters: {slug} ───────────────────────────────────────')
    params, sources = load_params(slug, model_path)
    log_params(params, sources)

    # Load dilution series from emission output if available
    dilution_series = None
    supply_csv = Path(f'analysis/{slug}/{slug}_supply_data.csv')
    if supply_csv.exists():
        df = pd.read_csv(supply_csv)
        dilution_series = df[df['scenario'] == 'base']['monthly_dilution_pct'].values
        print(f'  Loaded dilution series from emission output ({len(dilution_series)} months)')
    else:
        print(f'  No emission output found — running without dilution headwind')

    n_steps = int(params['n_steps'])
    print(f'\n── Running Monte Carlo ({params["n_runs"]:,} paths × {n_steps} months × 3 scenarios) ──')
    results = run_simulation(params, dilution_series=dilution_series, n_steps=n_steps)

    output_dir = f'analysis/{slug}'
    print(f'── Saving outputs → {output_dir}/ ──────────────────────────────────')
    save_outputs(results, params, output_dir, slug)
    print(f'\nDone.\n')

    return results, params


if __name__ == '__main__':
    main()
