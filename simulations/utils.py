"""
Shared parameter loader for tokenomics-analyzer simulations.

All simulation scripts import load_params() from here. It reads the
TokenModel YAML and fills any missing fields from simulation_baselines.md
defaults. Every parameter is annotated with its source so scripts can
log where each value came from.
"""

import yaml
from pathlib import Path

# ── Defaults from simulation_baselines.md ─────────────────────────────────────
BASELINES = {
    # Simulation config
    'n_steps': 120,
    'n_runs': 1000,
    'seed': 42,

    # Price / demand
    'initial_price_usd': 1.00,
    'price_vol_annual': 1.20,
    'demand_price_correlation': 0.70,
    'tail_event_prob_annual': 0.05,
    'tail_event_magnitude': 0.90,

    # Staking
    'initial_staking_rate': 0.20,
    'target_staking_rate': 0.50,
    'opportunity_cost': 0.05,
    'staking_sensitivity': 0.02,
    'mass_unstaking_trigger': 0.40,
    'mass_unstaking_pct': 0.20,

    # Emission
    'emission_decay_factor': 0.99,
    'halving_interval_months': 48,

    # Treasury / burn
    'dilution_event_threshold': 0.05,

    # Scenario demand growth (annual rates)
    'base_demand_growth_y1_y3': 0.20,
    'base_demand_growth_y4plus': 0.10,
    'bear_demand_y1': 0.00,
    'bear_demand_y2': -0.30,
    'bear_demand_y3': -0.50,
    'stress_shock_month': 12,
    'stress_shock_duration_months': 6,
    'stress_shock_price_drop': 0.80,

    # Vesting fallbacks
    'vesting_cliff_default': 12,
    'vesting_duration_default': 36,
}


def _get(d, *keys, default=None):
    """Safely navigate a nested dict; return default if any key is missing or value is 'unknown'."""
    for key in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(key)
        if d is None or d == 'unknown':
            return default
    return d


def load_params(token_slug, model_path=None):
    """
    Load simulation parameters for a token.

    Returns:
        params  (dict): flat parameter dict ready for simulation scripts
        sources (dict): per-parameter source annotation ('model' | 'baseline' | 'derived')
    """
    if model_path is None:
        model_path = Path(f'models/{token_slug}.yaml')

    raw = {}
    if Path(model_path).exists():
        with open(model_path) as f:
            raw = yaml.safe_load(f) or {}
    else:
        print(f"WARNING: model file not found at {model_path} — using baseline defaults only")

    p = {}
    s = {}

    def from_model(key, *yaml_path, cast=None):
        val = _get(raw, *yaml_path)
        if val is not None:
            p[key] = cast(val) if cast else val
            s[key] = 'model'
        else:
            baseline = BASELINES.get(key)
            p[key] = baseline
            s[key] = 'baseline'

    def from_baseline(key):
        p[key] = BASELINES[key]
        s[key] = 'baseline'

    # ── Token identity ─────────────────────────────────────────────────────────
    p['token_name'] = _get(raw, 'token', 'name') or token_slug
    p['token_symbol'] = _get(raw, 'token', 'symbol') or token_slug.upper()
    p['archetypes'] = _get(raw, 'token', 'archetypes') or []
    s['token_name'] = s['token_symbol'] = s['archetypes'] = 'model'

    # ── Supply ─────────────────────────────────────────────────────────────────
    from_model('total_supply', 'supply', 'total_supply', cast=float)
    from_model('initial_circulating', 'supply', 'initial_circulating', cast=float)
    from_model('emission_schedule', 'supply', 'emission_schedule')
    from_model('emission_rate_annual_pct', 'supply', 'emission_rate_annual_pct', cast=float)
    from_model('burn_mechanism', 'supply', 'burn_mechanism')

    # Derive initial_circulating_pct for sensitivity sweeps
    if p.get('total_supply') and p.get('initial_circulating'):
        p['initial_circulating_pct'] = p['initial_circulating'] / p['total_supply']
        s['initial_circulating_pct'] = 'derived'
    else:
        p['initial_circulating_pct'] = 0.15
        s['initial_circulating_pct'] = 'baseline'

    # ── Distribution (store as fractions 0–1) ─────────────────────────────────
    for cat in ('team', 'investors', 'ecosystem', 'community', 'treasury', 'other'):
        raw_pct = _get(raw, 'distribution', f'{cat}_pct')
        if raw_pct is not None:
            p[f'dist_{cat}'] = float(raw_pct) / 100.0
            s[f'dist_{cat}'] = 'model'
        else:
            p[f'dist_{cat}'] = 0.0
            s[f'dist_{cat}'] = 'baseline'

    # ── Vesting ────────────────────────────────────────────────────────────────
    for cat in ('team', 'investors', 'ecosystem'):
        cliff = _get(raw, 'vesting', cat, 'cliff_months')
        duration = _get(raw, 'vesting', cat, 'duration_months')
        p[f'vest_{cat}_cliff'] = int(cliff) if cliff is not None else BASELINES['vesting_cliff_default']
        p[f'vest_{cat}_dur'] = int(duration) if duration is not None else BASELINES['vesting_duration_default']
        s[f'vest_{cat}_cliff'] = 'model' if cliff is not None else 'baseline'
        s[f'vest_{cat}_dur'] = 'model' if duration is not None else 'baseline'

    # ── Staking ────────────────────────────────────────────────────────────────
    staking_on = _get(raw, 'utility', 'staking', 'enabled')
    p['staking_enabled'] = bool(staking_on) if staking_on is not None else False
    s['staking_enabled'] = 'model' if staking_on is not None else 'baseline'

    unbonding = _get(raw, 'utility', 'staking', 'unbonding_period_days')
    p['unbonding_days'] = int(unbonding) if unbonding else 14
    s['unbonding_days'] = 'model' if unbonding else 'baseline'

    for key in ('initial_staking_rate', 'target_staking_rate', 'opportunity_cost',
                'staking_sensitivity', 'mass_unstaking_trigger', 'mass_unstaking_pct'):
        from_baseline(key)

    # ── Economics / Treasury ───────────────────────────────────────────────────
    from_model('treasury_usd', 'economics', 'treasury', 'size_usd', cast=float)
    from_model('monthly_burn_usd', 'economics', 'treasury', 'monthly_burn_usd', cast=float)
    from_model('annual_revenue_usd', 'economics', 'annual_revenue_usd', cast=float)

    if p.get('monthly_burn_usd') and p.get('treasury_usd'):
        monthly_rev = (p.get('annual_revenue_usd') or 0) / 12
        net_burn = p['monthly_burn_usd'] - monthly_rev
        p['treasury_runway_months'] = p['treasury_usd'] / net_burn if net_burn > 0 else 999
        s['treasury_runway_months'] = 'derived'
    else:
        p['treasury_runway_months'] = None
        s['treasury_runway_months'] = 'baseline'

    # ── Simulation constants (always from baselines) ───────────────────────────
    for key in ('n_steps', 'n_runs', 'seed', 'initial_price_usd', 'price_vol_annual',
                'demand_price_correlation', 'tail_event_prob_annual', 'tail_event_magnitude',
                'dilution_event_threshold', 'emission_decay_factor', 'halving_interval_months',
                'base_demand_growth_y1_y3', 'base_demand_growth_y4plus',
                'bear_demand_y1', 'bear_demand_y2', 'bear_demand_y3',
                'stress_shock_month', 'stress_shock_duration_months', 'stress_shock_price_drop'):
        from_baseline(key)

    return p, s


def log_params(params, sources):
    """Print a sourced parameter summary."""
    model_params = [(k, v) for k, v in sorted(params.items()) if sources.get(k) == 'model']
    derived = [(k, v) for k, v in sorted(params.items()) if sources.get(k) == 'derived']
    baseline_params = [(k, v) for k, v in sorted(params.items()) if sources.get(k) == 'baseline']

    if model_params:
        print(f"  From model ({len(model_params)}):")
        for k, v in model_params:
            print(f"    {k}: {v}")
    if derived:
        print(f"  Derived ({len(derived)}):")
        for k, v in derived:
            print(f"    {k}: {v}")
    print(f"  From baselines ({len(baseline_params)}): {', '.join(k for k, _ in baseline_params)}")
    print()


def fmt_tokens(x):
    """Format a token count for display."""
    if x is None:
        return 'N/A'
    if x >= 1e9:
        return f'{x/1e9:.2f}B'
    if x >= 1e6:
        return f'{x/1e6:.2f}M'
    if x >= 1e3:
        return f'{x/1e3:.0f}K'
    return f'{x:.0f}'
