"""
emission_nrg.py — NRG (Holoverse) supply curve simulation
tokenomics-analyzer | Token-specific script

Models NRG supply dynamics over 120 months with Holoverse-specific mechanics:
  - Pre-mine of 10,000,000 NRG; all future supply from adaptive epoch emissions
  - Adaptive emission: Max(BaseFloor, Min(HardCap, 1.2 × 7-day-rolling-avg-daily-burn))
  - Multi-source burn: mint (90% of 100 NRG/mint), maintenance (stage-dependent),
    evolution (gameplay), NPC transfer tax (5%)
  - Vesting unlocks: team (12m cliff, 36m linear), investors (6m cliff, 24m linear),
    ecosystem (milestone-gated approximated), treasury (multisig — modeled as stable)
  - Scenarios: Base (2,000 universes at equilibrium), Bear (90% activity drop), Stress (near-zero activity)

Run from agent/ directory:
  python simulations/nrg/emission_nrg.py

Outputs → analysis/nrg/
  supply.png          supply composition + scenario comparison
  dilution.png        monthly dilution events
  nrg_supply_data.csv full monthly breakdown
"""

import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from pathlib import Path

# ── NRG model parameters ───────────────────────────────────────────────────────

PREMINE = 10_000_000          # NRG — total pre-mine at TGE
INITIAL_CIRC = 1_500_000      # NRG — community/TGE liquidity; fully unlocked

# Vesting (of pre-mine)
TEAM_ALLOC = 2_000_000        # 20% of pre-mine
TEAM_CLIFF = 12               # months
TEAM_DUR = 36                 # linear vesting months after cliff

INV_ALLOC = 1_500_000         # 15% of pre-mine
INV_CLIFF = 6                 # months
INV_DUR = 24                  # linear vesting months after cliff

ECO_ALLOC = 2_500_000         # 25% — milestone-gated; model as 12-month cliff, 48-month linear
ECO_CLIFF = 12
ECO_DUR = 48

TREASURY_ALLOC = 2_500_000    # 25% — multisig-governed; modeled as gradually deployed
# Treasury allocation treated as non-circulating for baseline (used for operations)
# Model: 5% released per year (conservative operational deployment)

# Adaptive emission parameters
BASE_FLOOR_DAY = 5_000        # NRG/day
HARD_CAP_DAY = 50_000         # NRG/day
ADAPTIVE_MULT = 1.2           # 7-day-rolling-avg-burn multiplier

# Scenario universe counts and activity levels
# These drive burn rates which feed the adaptive emission formula
SCENARIOS = {
    'base': {
        'label': 'Base',
        'color': '#2563eb',
        'universe_count': 2000,
        'activity_pct': 1.0,   # 100% of equilibrium burn rate
    },
    'bear': {
        'label': 'Bear',
        'color': '#dc2626',
        'universe_count': 200,
        'activity_pct': 0.10,  # 90% activity drop
    },
    'stress': {
        'label': 'Stress',
        'color': '#7c3aed',
        'universe_count': 50,
        'activity_pct': 0.02,  # Near-zero: 50 universes, minimal activity
    },
}

# Equilibrium burn breakdown at 2,000 active universes (per submission)
# Stage distribution at equilibrium (1k Cosmic, 600 Bio, 350 Social, 50 Transcendent)
EQUIL_DAILY_BURN = 12_300  # NRG/day total burn at equilibrium (from submission data)

N_STEPS = 120  # months (10 years)


# ── Helper functions ────────────────────────────────────────────────────────────

def vesting_monthly(total_alloc, cliff_m, dur_m, n_steps):
    """Monthly unlock amounts. Linear vesting starts at cliff_m, over dur_m months."""
    schedule = np.zeros(n_steps)
    if dur_m > 0 and total_alloc > 0:
        start = int(cliff_m)
        end = min(start + int(dur_m), n_steps)
        if end > start:
            schedule[start:end] = total_alloc / dur_m
    return schedule


def adaptive_daily_emission(daily_burn_7d_avg):
    """NRG adaptive emission formula: Max(BaseFloor, Min(HardCap, 1.2 × 7-day-avg-burn))"""
    adaptive = ADAPTIVE_MULT * daily_burn_7d_avg
    return max(BASE_FLOOR_DAY, min(HARD_CAP_DAY, adaptive))


def scenario_daily_burn(month, scenario):
    """
    Approximate daily burn for the given scenario and month.
    Scale linearly from ~0 at month 1 (ramp-up) to equilibrium by month 12.
    For bear/stress: applied to a fraction of full activity.
    """
    activity = scenario['activity_pct']
    ramp_factor = min(1.0, month / 12.0)  # ramp up to full activity over year 1
    return EQUIL_DAILY_BURN * activity * ramp_factor


def fmt_tokens(x):
    if x >= 1e9:
        return f'{x/1e9:.2f}B'
    if x >= 1e6:
        return f'{x/1e6:.2f}M'
    if x >= 1e3:
        return f'{x/1e3:.0f}K'
    return f'{x:.0f}'


# ── Simulation ──────────────────────────────────────────────────────────────────

def run_simulation():
    n = N_STEPS

    # Vesting schedules (monthly unlock amounts)
    team_vest = vesting_monthly(TEAM_ALLOC, TEAM_CLIFF, TEAM_DUR, n)
    inv_vest = vesting_monthly(INV_ALLOC, INV_CLIFF, INV_DUR, n)
    eco_vest = vesting_monthly(ECO_ALLOC, ECO_CLIFF, ECO_DUR, n)
    tsy_vest = vesting_monthly(TREASURY_ALLOC, 0, 240, n)  # 5%/yr operational deploy

    total_vesting = team_vest + inv_vest + eco_vest  # Treasury kept separate

    results = {}

    for scen_name, scen in SCENARIOS.items():
        circ = np.zeros(n)
        locked = np.zeros(n)
        total_supply_arr = np.zeros(n)
        emission_arr = np.zeros(n)
        burn_arr = np.zeros(n)
        new_tokens = np.zeros(n)

        circ[0] = INITIAL_CIRC
        locked[0] = PREMINE - INITIAL_CIRC  # includes team, investors, eco, treasury locked
        total_supply_arr[0] = PREMINE

        # Simulate 7-day burn rolling average (simplified: daily burn ~ constant within month)
        burn_7d_avg = EQUIL_DAILY_BURN * scen['activity_pct'] * (1.0 / 12.0)  # month-1 ramp

        for t in range(1, n):
            # Current month's daily burn
            daily_burn = scenario_daily_burn(t, scen)
            burn_7d_avg = 0.85 * burn_7d_avg + 0.15 * daily_burn  # EWMA approximation

            # Adaptive emission this month
            daily_emit = adaptive_daily_emission(burn_7d_avg)
            monthly_emit = daily_emit * 30.44  # avg days per month

            # Monthly burn (from 30 days of gameplay)
            monthly_burn = daily_burn * 30.44

            # Vesting unlocks this month
            vest_unlock = total_vesting[t]
            tsy_deploy = tsy_vest[t]

            # Circulating: previous + vesting unlocks + emissions - burns
            new_circ_tokens = vest_unlock + monthly_emit
            circ[t] = max(0.0, circ[t-1] + new_circ_tokens - monthly_burn)
            locked[t] = max(0.0, locked[t-1] - vest_unlock - tsy_deploy)
            total_supply_arr[t] = max(0.0, total_supply_arr[t-1] + monthly_emit - monthly_burn)
            emission_arr[t] = monthly_emit
            burn_arr[t] = monthly_burn
            new_tokens[t] = new_circ_tokens

        dilution = np.where(circ > 0, new_tokens / circ, 0.0)

        results[scen_name] = {
            'circulating': circ,
            'locked': locked,
            'total_supply': total_supply_arr,
            'emission': emission_arr,
            'burned': burn_arr,
            'new_tokens': new_tokens,
            'dilution': dilution,
        }

    results['_vesting'] = {
        'total': total_vesting,
        'team': team_vest,
        'investors': inv_vest,
        'ecosystem': eco_vest,
    }

    return results


# ── Output ──────────────────────────────────────────────────────────────────────

def save_outputs(results, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    n = N_STEPS
    months = np.arange(n)
    threshold = 0.05  # 5% dilution event threshold

    # ── supply.png ─────────────────────────────────────────────────────────────
    fig, (ax_top, ax_bot) = plt.subplots(2, 1, figsize=(12, 8))
    fig.suptitle('NRG (Holoverse) — Supply Dynamics', fontsize=13, fontweight='bold')

    base = results['base']
    vest = results['_vesting']
    freely_circ = np.maximum(0.0, base['circulating'])

    ax_top.stackplot(
        months,
        base['locked'], freely_circ,
        labels=['Locked/Unvested (pre-mine)', 'Freely Circulating'],
        colors=['#f59e0b', '#10b981'],
        alpha=0.8,
    )
    ax_top.plot(months, base['total_supply'], 'k--', linewidth=1.5, label='Total Supply', zorder=5)
    ax_top.axvline(12, color='#6366f1', linestyle=':', linewidth=1.5, label='Team cliff (m12)')
    ax_top.axvline(6, color='#f97316', linestyle=':', linewidth=1.5, label='Investor cliff (m6)')
    ax_top.set_title('Base Scenario — Supply Composition', fontsize=11)
    ax_top.set_ylabel('NRG Tokens')
    ax_top.legend(loc='upper left', fontsize=9)
    ax_top.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: fmt_tokens(x)))
    ax_top.set_xlim(0, n-1)
    ax_top.grid(axis='y', alpha=0.3)

    for scen_name, scen in SCENARIOS.items():
        ax_bot.plot(months, results[scen_name]['circulating'],
                    color=scen['color'], label=scen['label'], linewidth=2)
    ax_bot.set_title('Circulating Supply — Base / Bear / Stress Scenario Comparison', fontsize=11)
    ax_bot.set_xlabel('Month')
    ax_bot.set_ylabel('Circulating Supply (NRG)')
    ax_bot.legend(fontsize=9)
    ax_bot.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: fmt_tokens(x)))
    ax_bot.set_xlim(0, n-1)
    ax_bot.grid(axis='y', alpha=0.3)

    plt.tight_layout()
    plt.savefig(out / 'supply.png', dpi=100, bbox_inches='tight')
    plt.close()
    print('  supply.png saved')

    # ── dilution.png ───────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(12, 5))
    dilution_pct = results['base']['dilution'] * 100
    bar_colors = ['#dc2626' if d > threshold * 100 else '#3b82f6' for d in dilution_pct]
    ax.bar(months, dilution_pct, color=bar_colors, alpha=0.8, width=0.9)
    ax.axhline(threshold * 100, color='#dc2626', linestyle='--', linewidth=1.5,
               label=f'Dilution event threshold ({threshold*100:.0f}%)')
    events = np.where(dilution_pct > threshold * 100)[0]
    if len(events):
        ax.text(0.98, 0.96, f'{len(events)} dilution event{"s" if len(events) > 1 else ""}',
                transform=ax.transAxes, ha='right', va='top',
                color='#dc2626', fontweight='bold', fontsize=10)
    ax.set_xlabel('Month')
    ax.set_ylabel('New Supply / Circulating (%)')
    ax.set_title('NRG (Holoverse) — Monthly Dilution Events (Base Scenario)', fontsize=11)
    ax.legend(fontsize=9)
    ax.set_xlim(-0.5, n-0.5)
    ax.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.savefig(out / 'dilution.png', dpi=100, bbox_inches='tight')
    plt.close()
    print('  dilution.png saved')

    # ── nrg_supply_data.csv ────────────────────────────────────────────────────
    vest = results['_vesting']
    rows = []
    for scen_name in ('base', 'bear', 'stress'):
        r = results[scen_name]
        for t in range(n):
            rows.append({
                'scenario': scen_name,
                'month': t,
                'total_supply': round(r['total_supply'][t], 0),
                'circulating': round(r['circulating'][t], 0),
                'locked': round(r['locked'][t], 0),
                'team_unlock': round(vest['team'][t], 0),
                'investor_unlock': round(vest['investors'][t], 0),
                'ecosystem_unlock': round(vest['ecosystem'][t], 0),
                'monthly_emission': round(r['emission'][t], 0),
                'monthly_burn': round(r['burned'][t], 0),
                'net_monthly': round(r['emission'][t] - r['burned'][t], 0),
                'monthly_dilution_pct': round(r['dilution'][t] * 100, 4),
            })
    df = pd.DataFrame(rows)
    df.to_csv(out / 'nrg_supply_data.csv', index=False)
    print('  nrg_supply_data.csv saved')

    # ── Print summary ──────────────────────────────────────────────────────────
    b = results['base']
    print('\n── Emission Summary (Base Scenario) ────────────────────────────────────')
    for m in (0, 6, 12, 24, 36, 60, 120):
        if m < n:
            print(f'  Month {m:3d}: circulating = {fmt_tokens(b["circulating"][m])}'
                  f'  total = {fmt_tokens(b["total_supply"][m])}'
                  f'  locked = {fmt_tokens(b["locked"][m])}')

    print('\n── Net inflation analysis (Base / Bear / Stress) ───────────────────────')
    for scen_name in ('base', 'bear', 'stress'):
        r = results[scen_name]
        net_y1 = sum(r['emission'][1:13] - r['burned'][1:13])
        net_y2 = sum(r['emission'][13:25] - r['burned'][13:25])
        print(f'  {scen_name.capitalize():7s}: net Y1 = {fmt_tokens(net_y1)}  net Y2 = {fmt_tokens(net_y2)}')

    print(f'\n  Dilution events (base, >5%/month): {len(events)} in first 120 months')
    if len(events):
        print(f'    First event: month {events[0]}, last: month {events[-1]}')

    return df


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print('\n── Running NRG Emission Simulation ────────────────────────────────────')
    print(f'  Pre-mine: {fmt_tokens(PREMINE)} NRG')
    print(f'  Initial circulating: {fmt_tokens(INITIAL_CIRC)} NRG ({INITIAL_CIRC/PREMINE*100:.1f}% of pre-mine)')
    print(f'  BaseFloor: {fmt_tokens(BASE_FLOOR_DAY)} NRG/day  HardCap: {fmt_tokens(HARD_CAP_DAY)} NRG/day')
    print(f'  Equilibrium burn (2,000 universes): {fmt_tokens(EQUIL_DAILY_BURN)} NRG/day')
    print(f'  Scenarios: Base (100% activity), Bear (10%), Stress (2%)')
    print()

    results = run_simulation()
    out_dir = 'analysis/nrg'
    print(f'── Saving outputs → {out_dir}/ ─────────────────────────────────────────')
    save_outputs(results, out_dir)
    print('\nDone.\n')
