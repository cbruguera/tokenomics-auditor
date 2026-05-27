# Skill: weakness-scanner

**Layer:** 1 (Analytical — active during Step 4: Scan)

**Purpose:** Governs the systematic execution of the red flags checklist. Prevents shortcuts, omissions, and severity miscalibration.

---

## Scanner Protocol

The weakness scanner is not a creative task — it is a systematic pass through a defined checklist. Its value is in coverage, not novelty. Your job is to check every item, in order, and produce findings that a peer auditor could independently verify from the same TokenModel YAML.

**Run in this exact order:**
1. Critical checks (C-01 through C-08) — check all 8
2. High checks (H-01 through H-14) — check all 14
3. Medium checks (M-01 through M-14) — check all 14
4. Low checks (L-01 through L-10) — check all 10
5. Informational checks (I-01 through I-05) — check all 5
6. Death spiral checklist (10 conditions from `failure_postmortems.md`)
7. Grade assignment (from `scoring_rubric.md`)

Do not reorder. Do not skip ahead to "obvious" findings. The checklist exists precisely because non-obvious findings are the ones that get missed.

---

## For Each Check

For every check in `red_flags_master.md`, do this:

1. **Look up the YAML Fields column** in the `red_flags_master.md` table for that check
2. **Retrieve the value** from the parsed TokenModel
3. **Apply the threshold** from the table
4. **Decision:** triggered or not triggered
5. If triggered: create a finding. If not triggered: record a silent pass (no output needed unless helpful for transparency)

For checks where the YAML field is `unknown`:
- If the check could plausibly be triggered by a reasonable interpretation of the description → create the finding with an I-05 caveat
- If the check definitely cannot be triggered regardless of the unknown value → record silent pass
- If the check result is entirely dependent on the unknown value → create I-05 finding requesting the data

---

## Double-Trigger Prevention

Several check pairs cover different severity bands of the same issue. Do not trigger both:
- H-03 and M-02 (insider concentration): only one applies based on the exact percentage
- H-06 and M-07 (treasury runway): only one applies based on months of runway
- H-10 and M-06 (emission frontload): only one applies based on year-1 emission %
- H-14 and M-12 (subsidized yield): only one applies based on the subsidy fraction
- C-05 and H-07 (governance timelock): C-05 if no timelock AND no snapshot delay; H-07 if timelock absent or <24h but snapshot delay exists

---

## Severity Discipline

**Do not upgrade severity because multiple lower-severity findings compound.** Compounding is addressed in the grade (death spiral count + finding totals), not in individual severities. A Low finding is Low even if there are 5 other Low findings.

**Do not downgrade severity because the team "seems trustworthy."** Severity reflects the design flaw, not the team. A 3-month team cliff is H-01 regardless of how credible the founders are.

**Do not omit a finding because the fix seems obvious.** An obvious fix still needs to be documented so the team cannot claim they were unaware.

---

## Findings to Always Check Manually (Not in Checklist)

These findings can only be detected by reading the full description carefully — they are not derivable from a single YAML field:

1. **Circular revenue (L-09):** Read `economics.protocol_revenue_sources`. If fees are paid and distributed in the same native token, the protocol's "revenue" is self-referential. Note: `fee_sink = "burned"` is NOT circular revenue. Only circular if fees are denominated in native token AND distributed to stakers as native token yield.

2. **Governance flash loan eligibility (C-05):** Requires checking both `timelock_days` AND whether snapshot delay is described anywhere in the model. A protocol with `timelock_days = 0` but an explicit Snapshot.org off-chain vote that counts balances at proposal creation is NOT automatically C-05 — but it is H-07 unless the off-chain vote result is enforced by an on-chain timelock.

3. **Death spiral condition 10 (single demand driver):** Read `economics.demand_drivers`. If only one demand driver exists and it is the staking yield itself (circular), condition 10 is triggered. If demand drivers include external utility (e.g., required for protocol access, commodity collateral, DEX trading), condition 10 may not trigger.

---

## Death Spiral Scoring

After completing the red flags scan, run the death spiral checklist separately:

For each of the 10 conditions:
- State clearly: triggered / not triggered / unknown
- For unknown: note what information would resolve it
- Count triggered conditions

Interpretation:
- 0–2: Pass
- 3–5: Note in findings (contributes to grade)
- 6–10: C-04 Critical finding; contributes to Grade F if ≥6

---

## Completeness Check

Before finalizing findings, verify:
- [ ] Checked all 8 Critical flags
- [ ] Checked all 14 High flags
- [ ] Checked all 14 Medium flags
- [ ] Checked all 10 Low flags
- [ ] Checked all 5 Informational flags
- [ ] Completed death spiral checklist (10 conditions)
- [ ] Assigned grade per scoring_rubric.md
- [ ] Every Critical and High finding has a Fix Proposal
- [ ] No double-triggered severity pairs
