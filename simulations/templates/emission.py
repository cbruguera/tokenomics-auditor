"""
emission.py — Supply curve simulation
tokenomics-analyzer | Phase 3.1 core script

Models token supply dynamics over 120 months:
  - Vesting unlocks per allocation category (team, investors, ecosystem)
  - Protocol inflation / emission schedule
  - Burn rate (if present)
  - Staking dynamics (tokens locked vs circulating)

Run:
  python emission.py <token_slug> [--model models/<token_slug>.yaml]

Outputs (to analysis/<token_slug>/):
  supply.png        — supply composition + scenario comparison
  dilution.png      — monthly dilution events
  supply_data.csv   — full monthly breakdown across scenarios
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
from utils import load_params, log_params, fmt_tokens

# ── Scenarios ─────────────────────────────────────────────────────────────────
SCENARIOS = {
    'base': {
        'label': 'Base',
        'color': '#2563eb',
        'staking_target': 0.50,
        'burn_multiplier': 1.0,
    },
    'bear': {
        'label': 'Bear',
        'color': '#dc2626',
        'staking_target': 0.25,
        'burn_multiplier': 0.4,
    },
    'stress': {
        'label': 'Stress',
        'color': '#7c3aed',
        'staking_target': 0.10,
        'burn_multiplier': 0.1,
    },
}


# ── Simulation functions ───────────────────────────────────────────────────────

def vesting_schedule(total_supply, alloc_frac, cliff_m, duration_m, n_steps):
    """
    Monthly unlock amounts for a single vesting allocation.
    Tokens vest linearly from month cliff_m over duration_m months.
    No cliff lump-sum: the cliff is when linear vesting starts.
    """
    total = total_supply * alloc_frac
    schedule = np.zeros(n_steps)
    if duration_m > 0 and total > 0:
        start = int(cliff_m)
        end = min(start + int(duration_m), n_steps)
        if end > start:
            schedule[start:end] = total / duration_m
    return schedule


def emission_schedule(total_supply, schedule_type, annual_rate_pct, n_steps, p):
    """
    Monthly new token emission from protocol inflation.
    Returns zero array if schedule_type is 'none' or rate is 0.
    """
    out = np.zeros(n_steps)
    if not schedule_type or schedule_type == 'none' or not annual_rate_pct:
        return out

    monthly_rate = (annual_rate_pct / 100.0) / 12.0

    if schedule_type in ('fixed', 'linear-inflation'):
        out[:] = total_supply * monthly_rate

    elif schedule_type == 'exponential-decay':
        decay = p['emission_decay_factor']
        for t in range(n_steps):
            out[t] = total_supply * monthly_rate * (decay ** t)

    elif schedule_type == 'halving':
        interval = p['halving_interval_months']
        for t in range(n_steps):
            out[t] = total_supply * monthly_rate * (0.5 ** (t // interval))

    elif schedule_type == 'deflationary':
        pass  # no new emission; burns reduce supply

    else:
        out[:] = total_supply * monthly_rate  # unknown → treat as fixed

    return out


def run_simulation(params, n_steps=120):
    """
    Run supply curve simulation across Base, Bear, Stress scenarios.
    Returns dict of scenario_name → result arrays.
    """
    p = params
    total = p['total_supply']
    initial_circ = p['initial_circulating'] or total * 0.15

    # Vesting unlock schedules
    team_vest = vesting_schedule(total, p['dist_team'], p['vest_team_cliff'], p['vest_team_dur'], n_steps)
    inv_vest = vesting_schedule(total, p['dist_investors'], p['vest_investors_cliff'], p['vest_investors_dur'], n_steps)
    eco_vest = vesting_schedule(total, p['dist_ecosystem'], p['vest_ecosystem_cliff'], p['vest_ecosystem_dur'], n_steps)
    total_vesting = team_vest + inv_vest + eco_vest

    # Protocol emission
    emission = emission_schedule(total, p.get('emission_schedule'), p.get('emission_rate_annual_pct'), n_steps, p)

    # Burn rate: conservative 2% annual of circulating if any burn mechanism exists
    has_burn = p.get('burn_mechanism') not in ('none', None, 'unknown')
    annual_burn_pct = 2.0 if has_burn else 0.0

    results = {}
    for scen_name, scen in SCENARIOS.items():
        circ = np.zeros(n_steps)
        locked = np.zeros(n_steps)
        staked = np.zeros(n_steps)
        new_tokens = np.zeros(n_steps)
        burned = np.zeros(n_steps)
        total_arr = np.zeros(n_steps)

        circ[0] = initial_circ
        locked[0] = max(0.0, total - initial_circ)
        staking_rate = p['initial_staking_rate']
        staked[0] = circ[0] * staking_rate
        total_arr[0] = total

        for t in range(1, n_steps):
            # Unlock: can't release more than what's still locked
            unlock_t = min(total_vesting[t], locked[t - 1])
            emit_t = emission[t]
            burn_t = circ[t - 1] * (annual_burn_pct / 100.0 / 12.0) * scen['burn_multiplier']

            # Staking: gradual equilibration toward scenario target
            # Stress: fast exit (5% per month); others: 2% per month
            speed = 0.05 if scen_name == 'stress' else 0.02
            staking_rate = np.clip(staking_rate + speed * (scen['staking_target'] - staking_rate), 0.0, 0.95)

            circ[t] = max(0.0, circ[t - 1] + unlock_t + emit_t - burn_t)
            locked[t] = max(0.0, locked[t - 1] - unlock_t)
            staked[t] = circ[t] * staking_rate
            new_tokens[t] = unlock_t + emit_t
            burned[t] = burn_t
            total_arr[t] = max(0.0, total_arr[t - 1] + emit_t - burn_t)

        dilution = np.where(circ > 0, new_tokens / circ, 0.0)

        results[scen_name] = {
            'circulating': circ,
            'locked': locked,
            'staked': staked,
            'new_tokens': new_tokens,
            'burned': burned,
            'total_supply': total_arr,
            'dilution': dilution,
        }

    # Attach vesting breakdown for downstream use
    results['_vesting'] = {
        'total': total_vesting,
        'team': team_vest,
        'investors': inv_vest,
        'ecosystem': eco_vest,
    }

    return results


# ── Output ─────────────────────────────────────────────────────────────────────

def save_outputs(results, params, output_dir, token_slug):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    name = params.get('token_name', token_slug)
    symbol = params.get('token_symbol', token_slug.upper())
    n_steps = len(results['base']['circulating'])
    months = np.arange(n_steps)
    threshold = params['dilution_event_threshold']

    # ── supply.png ─────────────────────────────────────────────────────────────
    fig, (ax_top, ax_bot) = plt.subplots(2, 1, figsize=(12, 8))
    fig.suptitle(f'{name} ({symbol}) — Supply Dynamics', fontsize=13, fontweight='bold')

    base = results['base']
    freely = np.maximum(0.0, base['circulating'] - base['staked'])

    ax_top.stackplot(
        months,
        base['staked'], base['locked'], freely,
        labels=['Staked', 'Locked / Unvested', 'Freely Circulating'],
        colors=['#3b82f6', '#f59e0b', '#10b981'],
        alpha=0.8,
    )
    ax_top.plot(months, base['total_supply'], 'k--', linewidth=1.5, label='Total Supply', zorder=5)
    ax_top.set_title('Base Scenario — Supply Composition', fontsize=11)
    ax_top.set_ylabel('Tokens')
    ax_top.legend(loc='upper left', fontsize=9)
    ax_top.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: fmt_tokens(x)))
    ax_top.set_xlim(0, n_steps - 1)
    ax_top.grid(axis='y', alpha=0.3)

    for scen_name, scen in SCENARIOS.items():
        ax_bot.plot(months, results[scen_name]['circulating'],
                    color=scen['color'], label=scen['label'], linewidth=2)
    ax_bot.set_title('Circulating Supply — Scenario Comparison', fontsize=11)
    ax_bot.set_xlabel('Month')
    ax_bot.set_ylabel('Circulating Supply')
    ax_bot.legend(fontsize=9)
    ax_bot.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: fmt_tokens(x)))
    ax_bot.set_xlim(0, n_steps - 1)
    ax_bot.grid(axis='y', alpha=0.3)

    plt.tight_layout()
    plt.savefig(out / 'supply.png', dpi=100, bbox_inches='tight')
    plt.close()
    print(f'  supply.png')

    # ── dilution.png ───────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(12, 5))
    dilution_pct = results['base']['dilution'] * 100
    bar_colors = ['#dc2626' if d > threshold * 100 else '#3b82f6' for d in dilution_pct]
    ax.bar(months, dilution_pct, color=bar_colors, alpha=0.8, width=0.9)
    ax.axhline(threshold * 100, color='#dc2626', linestyle='--', linewidth=1.5,
               label=f'Dilution threshold ({threshold*100:.0f}%)')

    events = np.where(dilution_pct > threshold * 100)[0]
    if len(events):
        ax.text(0.98, 0.96, f'{len(events)} dilution event{"s" if len(events) > 1 else ""}',
                transform=ax.transAxes, ha='right', va='top',
                color='#dc2626', fontweight='bold', fontsize=10)
    ax.set_xlabel('Month')
    ax.set_ylabel('New Supply / Circulating (%)')
    ax.set_title(f'{name} ({symbol}) — Monthly Dilution Events (Base Scenario)', fontsize=11)
    ax.legend(fontsize=9)
    ax.set_xlim(-0.5, n_steps - 0.5)
    ax.grid(axis='y', alpha=0.3)

    plt.tight_layout()
    plt.savefig(out / 'dilution.png', dpi=100, bbox_inches='tight')
    plt.close()
    print(f'  dilution.png')

    # ── supply_data.csv ────────────────────────────────────────────────────────
    vest = results['_vesting']
    rows = []
    for scen_name in ('base', 'bear', 'stress'):
        r = results[scen_name]
        for t in range(n_steps):
            rows.append({
                'scenario': scen_name,
                'month': t,
                'total_supply': round(r['total_supply'][t], 2),
                'circulating': round(r['circulating'][t], 2),
                'locked': round(r['locked'][t], 2),
                'staked': round(r['staked'][t], 2),
                'team_unlock': round(vest['team'][t], 2),
                'investor_unlock': round(vest['investors'][t], 2),
                'ecosystem_unlock': round(vest['ecosystem'][t], 2),
                'total_vesting_unlock': round(vest['total'][t], 2),
                'new_emission': round(r['new_tokens'][t] - min(vest['total'][t], r['locked'][t - 1] if t > 0 else 0), 2),
                'burned': round(r['burned'][t], 2),
                'monthly_dilution_pct': round(r['dilution'][t] * 100, 4),
            })
    csv_path = out / f'{token_slug}_supply_data.csv'
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    print(f'  {token_slug}_supply_data.csv')

    # ── Summary ────────────────────────────────────────────────────────────────
    b = results['base']
    total = params['total_supply']
    print(f'\n── Emission Summary ──────────────────────────────────────────────────')
    print(f'  Initial circulating:  {fmt_tokens(b["circulating"][0])}  ({b["circulating"][0]/total*100:.1f}% of total)')
    print(f'  Circulating @ 12m:   {fmt_tokens(b["circulating"][12])}  ({b["circulating"][12]/total*100:.1f}%)')
    print(f'  Circulating @ 36m:   {fmt_tokens(b["circulating"][36])}  ({b["circulating"][36]/total*100:.1f}%)')
    print(f'  Circulating @ 60m:   {fmt_tokens(b["circulating"][min(60, n_steps-1)])}  ({b["circulating"][min(60, n_steps-1)]/total*100:.1f}%)')
    if len(events):
        print(f'  Dilution events:     {len(events)} months exceed {threshold*100:.0f}% threshold (first: month {events[0]})')
    else:
        print(f'  Dilution events:     None above {threshold*100:.0f}% threshold')


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Supply curve simulation — tokenomics-analyzer')
    parser.add_argument('token_slug', help='Token slug, e.g. nova-protocol')
    parser.add_argument('--model', help='Path to TokenModel YAML')
    args = parser.parse_args()

    slug = args.token_slug
    model_path = args.model or f'models/{slug}.yaml'

    print(f'\n── Loading parameters: {slug} ───────────────────────────────────────')
    params, sources = load_params(slug, model_path)
    log_params(params, sources)

    if not params.get('total_supply'):
        print('WARNING: total_supply unknown — using 1,000,000,000 as placeholder')
        params['total_supply'] = 1_000_000_000
        if not params.get('initial_circulating'):
            params['initial_circulating'] = 150_000_000

    n_steps = int(params['n_steps'])
    print(f'── Running emission simulation ({n_steps} months × 3 scenarios) ──────')
    results = run_simulation(params, n_steps=n_steps)

    output_dir = f'analysis/{slug}'
    print(f'── Saving outputs → {output_dir}/ ──────────────────────────────────')
    save_outputs(results, params, output_dir, slug)
    print(f'\nDone.\n')

    return results, params


if __name__ == '__main__':
    main()
