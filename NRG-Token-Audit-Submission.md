# $NRG Token — Audit Submission

**Project:** Holoverse  
**Chain:** Arbitrum One (testnet: Arbitrum Sepolia)  
**Status:** Pre-launch. Contracts written and passing tests; testnet deploy pending. No mainnet activity.  
**Note:** All economic parameters in this document are provisional starting points. The primary goal of this audit is to validate the structural model and stress-test these numbers.

---

## 1. What the Protocol Does

Holoverse is a Web3 game where players own, evolve, and sustain unique universes as living NFT assets. Each universe is an ERC-721 NFT that progresses through four sequential stages of development:

1. **Cosmic** — Players optimize fundamental physical constants, generating Exotic Matter (Stardust, Dark Matter, Antimatter) that is sold to higher-stage universes.
2. **Biological** — Players direct species evolution and engineer traits; they can patent species as NFTs and sell genetic blueprints cross-universe.
3. **Social / Technological** — The universe becomes an open multi-player world with player-to-player commerce, civilizations, and economic conflict.
4. **Transcendent** — Owners gain cross-universe privileges ("quantum interference"), entering other universes and seeding them with unique items or species.

**What a typical owner does:**
- Mints a universe NFT by spending $NRG (burned) and a fixed USDC fee (sent to treasury).
- Plays actively to grow the universe's complexity, earning $NRG from the global epoch emissions pool.
- Pays a periodic maintenance burn to hold the universe's current stage; missing a payment causes immediate regression by one stage.
- Opens the universe to other players (NPCs) who contribute labor in exchange for a share of the owner's epoch earnings.

**Key participants:**

| Participant | Role |
|---|---|
| Universe Owner | Mints and manages the NFT; earns epoch emissions proportional to universe complexity; sets NPC split and access rules |
| NPC Player | Incarnates into an existing NPC creature; contributes meaningful activity; earns a share of the owner's emissions |
| Holoverse Protocol | Issues $NRG via the epoch emissions engine; enforces all economic rules on-chain; receives treasury fees |

**How the protocol generates activity:** Owners are economically motivated to attract NPC players to maximize their Complexity Score (the primary driver of emission share). NPC players are motivated to play in universes that offer fair revenue splits. This creates a two-sided labor market. Separately, the maintenance burn forces all owners to remain engaged — idling a high-level universe is expensive.

**Protocol status:** Not live. All smart contracts written and tested (12/12 unit tests passing). Testnet deploy is the immediate next step.

---

## 2. The Token's Role

**Token:** $NRG — ERC-20, symbol NRG, deployed on Arbitrum One.

**What $NRG enables:**
- **Minting** a Universe NFT — required; no alternative path exists.
- **Maintaining** a universe's current stage — required; non-payment causes regression and loss of earnings power.
- **Evolving** a universe — $NRG is burned continuously through the gameplay actions that advance complexity (tuning physical constants, directing mutation, building infrastructure, conducting trade). There is no single stage-advance fee; cost is distributed across the journey.
- **Cross-universe trade and NPC labor payments** — $NRG is the universal medium of exchange across all universes.

**Is the token optional?** No for core functions. Minting and maintenance are mandatory. Evolution and trade require it by design.

**Behaviors the token incentivizes:**
- Owners to mint (burn) and remain active (maintenance burn and evolution costs).
- Owners to attract quality NPC players (NPC contribution drives Complexity Score and emission share).
- NPC players to contribute meaningful labor (they earn a share of epoch emissions).
- No incentive to hold passively — holding $NRG earns nothing.

**Activity-to-demand link:** Mechanically direct. Each new universe minted burns 90% of its $NRG cost. Maintenance burns are daily and scale with stage. Evolution burns are continuous. More universes at higher stages = higher daily burn pressure. Token demand scales with active universe count and player engagement, not with speculation.

---

## 3. Supply and Distribution

### Total Supply

Uncapped. $NRG enters circulation exclusively through the daily epoch emission engine. There is no fixed ceiling on total supply; the Hard Cap constrains the daily emission rate, not the lifetime total.

### Pre-mine at TGE: 10,000,000 NRG

The pre-mine is the only non-emission source of $NRG. All future supply comes from the epoch engine.

| Category | % | NRG | Cliff | Vesting |
|---|---|---|---|---|
| Team | 20% | 2,000,000 | 12 months | 36 months linear |
| Investors | 15% | 1,500,000 | 6 months | 24 months linear |
| Ecosystem / Grants | 25% | 2,500,000 | None | Milestone-gated releases |
| Treasury | 25% | 2,500,000 | None | Multisig-governed |
| Community / TGE liquidity | 15% | 1,500,000 | None | Fully unlocked at TGE |

**TGE unlock:** 1,500,000 NRG (15% of pre-mine). No launch date is set; this is a provisional structure ahead of fundraising.

### Supply Dilution Trajectory

At maximum emission (Hard Cap every day — an upper bound):

| Timeframe | Cumulative emissions | Total supply | Pre-mine share |
|---|---|---|---|
| TGE | 0 | 10,000,000 | 100% |
| Year 1 | 18,250,000 | 28,250,000 | 35.4% |
| Year 2 | 36,500,000 | 46,500,000 | 21.5% |
| Year 5 | 91,250,000 | 101,250,000 | 9.9% |

In practice, early emissions will run below Hard Cap, so dilution will be slower than these figures suggest.

### Burn Mechanisms

1. **Mint burn:** 90% of $NRG paid at universe mint is permanently burned; 10% goes to treasury.
2. **Maintenance burn:** Owners burn $NRG each epoch to hold their universe's stage. Rates by stage: Cosmic 1 NRG/day, Biological 4 NRG/day, Social 12 NRG/day, Transcendent 30 NRG/day.
3. **Evolution burn (continuous):** Every meaningful gameplay action that grows the universe's complexity costs $NRG proportional to its significance — approximate ranges: minor actions 0.1–1 NRG, moderate 1–10 NRG, major 10–50 NRG, Transcendent-tier 50–200 NRG. Cost is embedded in the action, not in a stage-advance transaction.
4. **NPC transfer tax:** 5% of all $NRG transferred from universe owners to NPC players is permanently burned by the protocol.

---

## 4. Emission Mechanics

### Epoch

One epoch = one calendar day (86,400 seconds). Unused emission capacity is discarded at epoch end — it does not roll over.

### Emission Formula

```
DailyEmission = Max(BaseFloor, AdaptiveWeight)

AdaptiveWeight = Min(HardCap, 1.2 × 7-day-rolling-average-daily-burn)
```

| Parameter | Value |
|---|---|
| BaseFloor | 5,000 NRG/day |
| Hard Cap | 50,000 NRG/day |
| Adaptive multiplier | 1.2× (targets mild net inflation during growth) |
| Lookback window | 7 days |
| Per-universe cap | 3% of epoch emissions |

**Counter-cyclical design:** When burn activity falls, AdaptiveWeight falls, but BaseFloor prevents emissions from dropping to zero — protecting against the pro-cyclical death spiral where low rewards drive away players, further reducing burns. When burns are high, emissions rise toward Hard Cap to support the growing economy.

**Per-universe cap:** No single universe can claim more than 3% of the epoch pool (150 NRG/day at BaseFloor; 1,500 NRG/day at Hard Cap), preventing whale dominance.

### Illustrative Equilibrium (2,000 active universes)

| Burn source | Estimated daily burn |
|---|---|
| 10 new mints/day × 90 NRG | 900 NRG |
| Maintenance (1,000 Cosmic × 1) | 1,000 NRG |
| Maintenance (600 Biological × 4) | 2,400 NRG |
| Maintenance (350 Social × 12) | 4,200 NRG |
| Maintenance (50 Transcendent × 30) | 1,500 NRG |
| NPC transfer tax (estimated) | 800 NRG |
| Evolution actions (estimated) | 1,500 NRG |
| **Total** | **~12,300 NRG/day** |

At 12,300 NRG/day in burns: `AdaptiveWeight = min(50,000, 1.2 × 12,300) = 14,760`. Net daily inflation: ~2,460 NRG — the intended mild-inflationary growth-phase regime.

---

## 5. Proof of Activity — Emission Distribution

### Composite Share Formula

Each universe's raw score for the epoch:

```
RawScore = (0.40 × PM_norm) + (0.25 × UMI_norm) + (0.35 × CS_norm)
```

Where `_norm` is the universe's share of the epoch total for that signal:
`PM_norm_i = PM_i / Σ(PM_j)`, and similarly for UMI and CS.

Universe epoch share = `min(0.03, RawScore_i / Σ(RawScore_j))`, then renormalized to sum to 1 across all universes.

### Signal 1 — Player Minutes (PM, weight 40%)

A **player-minute** is credited when a player performs at least one meaningful action within a 60-second window while incarnated in the universe.

**Meaningful action:** Any action that produces a measurable change in a tracked universe state variable — resource balances, species population counts, infrastructure counts, trade ledger entries. Connection without action, movement without state change, and repetitive identical interactions with the same entity within the same minute yield no credit.

**Caps:** Maximum 960 PM per player per universe per day (16 active hours). Minimum session: 5 consecutive credited minutes before any PM is recorded.

### Signal 2 — Unique Meaningful Interactions (UMI, weight 25%)

A **unique meaningful interaction** is a state-changing event involving at least two distinct entities (player ↔ NPC, player ↔ resource node, player ↔ player).

**Uniqueness window:** The same actor + same target entity pair counts at most once per 30 minutes, regardless of how many interactions occur between them.

### Signal 3 — Complexity Score (CS, weight 35%)

A persistent property of the universe, snapshotted at the end of each epoch by the simulation service. It does not reset between epochs.

```
CS = Stage_base
     × (1 + 0.10 × ln(max(1, ActiveSpecies)))
     × (1 + 0.05 × TechNodes)
     × IEV_factor
```

| Component | Description |
|---|---|
| `Stage_base` | Cosmic: 1.0 / Biological: 2.0 / Social: 4.0 / Transcendent: 8.0 |
| `ActiveSpecies` | Distinct species with ≥100 living members this epoch; natural log dampens runaway growth |
| `TechNodes` | Distinct technologies, structures, or infrastructure items; capped at 200 |
| `IEV_factor` | Social/Transcendent only: `1 + min(0.50, epoch_NRG_commerce_volume / 1,000)`. Cosmic/Biological: 1.0 |

### Sybil Resistance

Resistance is structural rather than rule-based. NPC slots within a universe are finite and determined by the universe's own evolutionary state — a newly minted Cosmic universe may support 2–5 NPC incarnations; a mature Social universe may support hundreds. Players incarnate into existing creatures generated naturally by the simulation; they cannot spawn new NPCs. Capacity scales with genuine universe complexity.

Meaningful activity is required for any emission credit. Automation (bots, AI agents) is explicitly tolerated — if automated activity genuinely advances the universe's state, it earns. Hollow activity (being online, random movement, non-state-changing interactions) yields zero PM and zero UMI. The simulation service validates all actions against the current universe state.

---

## 6. NPC Labor Market

- **Incarnation:** Players join a universe by owner invite or open access, incarnating into an existing NPC creature.
- **Revenue sharing:** The owner sets an NPC split percentage (minimum 10%, enforced on-chain). That share of the universe's epoch earnings is distributed to active NPCs proportionally by their measured contribution.
- **Holoverse tax:** 5% of all owner-to-NPC $NRG transfers is permanently burned.
- **Owner fee rails:** Owners may charge participation fees in any asset ($NRG, USDC, or other ERC-20). No Holoverse-enforced denomination requirement.

---

## 7. Economics

### Protocol Revenue

| Source | Type | Rate |
|---|---|---|
| Universe mint — $NRG leg | Non-burned NRG to treasury | 10% of NRG paid at mint |
| Universe mint — stablecoin leg | USDC to treasury | $10 USDC per mint |
| NPC transfer tax | Permanently burned (not treasury) | 5% of owner-to-NPC transfers |

### Staking

None. There is no staking mechanism. Epoch emissions are distributed to active participants only — passive token holders earn nothing.

### Emission Funding

Epoch rewards are funded exclusively by new $NRG issuance, not by protocol revenue. Protocol revenue (10% NRG + USDC from mints) accumulates in the treasury for operations.

### Revenue Projections (⚠ highly uncertain, pre-launch)

Assumptions: 500 universe mints in Year 1 (conservative), ~1.5 mints/day.

| Source | Annual inflow |
|---|---|
| USDC mint fees | 500 × $10 = $5,000 |
| NRG to treasury (10% of mints) | 500 × 10 NRG = 5,000 NRG |

Early treasury inflow is modest. The pre-mine treasury allocation is the primary operational reserve.

---

## 8. Treasury

**Current value:** $0. Pre-launch; no mainnet activity.

**Composition at TGE:**

| Asset | Amount | Source |
|---|---|---|
| NRG (governed) | 2,500,000 NRG | Pre-mine allocation |
| USDC | $0 | Accumulates from mint fees post-TGE |

**Monthly operational costs:** ~$19,000/month (team and contractors $15,000; infrastructure $500; legal/compliance $1,500; audits amortized $2,000).

**Runway:** The 2,500,000 NRG treasury allocation provides approximately 12–24 months of operations depending on $NRG market price, supplemented by USDC mint fee accumulation.

**Treasury contract:** `HoloverseTreasury.sol` — simple Ownable vault with `withdraw(token, to, amount)` restricted to owner. No timelock or multisig in Phase I. See weaknesses below.

---

## 9. Governance

| Phase | Period | Mechanism |
|---|---|---|
| I (now) | Months 1–2 | Deployer EOA — all parameters |
| II–III | Months 2–4 | 3-of-5 Gnosis Safe, no timelock — treasury and parameter updates |
| IV–V | Months 4–5 | Snapshot off-chain proposals (72-hour discussion), 3-of-5 Safe execution |
| VI (pre-mainnet) | Month 6+ | OpenZeppelin Governor on-chain, 48-hour timelock |

**Quorum (Phase VI):** 4% of circulating supply for parameter changes; 10% for treasury withdrawals >10% of treasury value.

**Emergency controls (Phase VI):** 3-of-5 Safe multisig can pause without a vote.

**Contract upgradeability:** Contracts are not upgradeable (no proxy pattern). Bug fixes require deploying new contracts and migrating users.

---

## 10. Known Weaknesses

**W1 — Deployer holds MINTER_ROLE**  
Until the emissions engine is built and MINTER_ROLE is transferred (Phase IV, Month 4), the deployer can mint unlimited $NRG. This is an accepted trust assumption for testnet; it is a critical pre-mainnet fix. The audit should verify that the handoff path is clean and practically irreversible.

**W2 — Emission numbers are provisional**  
BaseFloor (5,000 NRG/day), Hard Cap (50,000 NRG/day), the 1.2× adaptive multiplier, and the 7-day lookback window have not been stress-tested against simulated player populations. The audit should model whether these parameters produce stable dynamics across a range of player counts and activity levels, and whether the 10:1 cap-to-floor ratio provides adequate headroom.

**W3 — Treasury is a single-owner vault with no timelock**  
`HoloverseTreasury.sol` has no multisig or timelock. A compromised deployer key drains the treasury instantly. Acceptable for testnet; must be replaced with Gnosis Safe before mainnet.

**W4 — Proof of Activity oracle is off-chain and not yet built**  
Emission distribution relies on play signals computed by an off-chain simulation service and submitted on-chain via merkle roots and proofs. The oracle is controlled by the deployer. The emissions engine is Month 4 scope. The audit should evaluate whether the described architecture provides adequate trust minimization and identify oracle manipulation vectors.

**W5 — NPC split floor is not yet implemented**  
The 10% minimum NPC split is a design decision; it is not yet in the contracts. `Universe.sol` currently allows a 0% split. Implementation is required before mainnet.

**W6 — Evolution burn sink is defined but not implemented on-chain**  
Evolution costs are continuous and embedded in simulation-service-enforced gameplay actions, not in smart contract transactions. The `advanceStage()` function in `Universe.sol` is a no-cost stub. The audit should evaluate whether continuous off-chain cost embedding creates weaker deflationary pressure than an on-chain discrete fee would, and what the exploit surface is if the simulation service is compromised.

**W7 — Supply allocation and vesting are provisional**  
No fundraise has occurred. The allocation table (20% team / 15% investors / 25% ecosystem / 25% treasury / 15% community) is a proposed starting point. The audit should evaluate whether these ratios and vesting schedules fall within normal ranges for a Web3 game at this stage.

---

## 11. Contracts

| Contract | Standard | Purpose |
|---|---|---|
| `NrgToken.sol` | ERC-20 (OpenZeppelin v5) | $NRG token; burnable; MINTER_ROLE gated |
| `Universe.sol` | ERC-721 (OpenZeppelin v5) | Universe NFTs; `mintUniverse()` with 90/10 burn/treasury split; `advanceStage()` stub |
| `HoloverseTreasury.sol` | — | Simple vault; `withdraw()` onlyOwner |
| `MockUSDC.sol` | ERC-20 (6 decimal) | Testnet-only USDC stand-in |

**Toolchain:** Hardhat + TypeScript, OpenZeppelin v5, pnpm workspaces.
