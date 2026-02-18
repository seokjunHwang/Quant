"""Stage 5: Strategy Combiner — Role-based indicator composition.

Generates composite strategies by combining indicators based on their roles:
- primary_signal (1, required): Main entry signal
- confirmation (0-2): Additional entry confirmation
- market_filter (0-1): Allow/deny trading based on market state
- exit_signal (0-1): Override exit timing
"""

import itertools
import json
import uuid
import pandas as pd
import numpy as np

from ai.pipeline.analyzer import get_indicators_by_role
from ai.pipeline.converter import load_converted_module
from ai.pipeline.utils.db import PipelineDB
from ai.pipeline.utils.logger import get_logger

logger = get_logger("combiner")


class CompositeStrategy:
    """A strategy composed of multiple indicators with defined roles."""

    def __init__(
        self,
        strategy_id: str,
        primary: dict,
        confirmations: list[dict] | None = None,
        market_filter: dict | None = None,
        exit_signal: dict | None = None,
    ):
        self.strategy_id = strategy_id
        self.primary = primary
        self.confirmations = confirmations or []
        self.market_filter = market_filter
        self.exit_signal = exit_signal

        # Load modules
        self._primary_mod = load_converted_module(primary["id"])
        self._confirm_mods = [load_converted_module(c["id"]) for c in self.confirmations]
        self._filter_mod = load_converted_module(market_filter["id"]) if market_filter else None
        self._exit_mod = load_converted_module(exit_signal["id"]) if exit_signal else None

    @property
    def description(self) -> str:
        parts = [self.primary["id"]]
        for c in self.confirmations:
            parts.append(f"+ {c['id']}(confirm)")
        if self.market_filter:
            parts.append(f"+ {self.market_filter['id']}(filter)")
        if self.exit_signal:
            parts.append(f"+ {self.exit_signal['id']}(exit)")
        return " ".join(parts)

    @property
    def component_ids(self) -> list[str]:
        ids = [self.primary["id"]]
        ids.extend(c["id"] for c in self.confirmations)
        if self.market_filter:
            ids.append(self.market_filter["id"])
        if self.exit_signal:
            ids.append(self.exit_signal["id"])
        return ids

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate composite signals by combining all indicator roles.

        Logic:
        - Entry LONG: primary=buy AND all confirmations=buy AND filter allows
        - Exit LONG: exit_signal=sell OR primary=sell
        """
        result = df.copy()
        result["signal"] = 0

        # Primary signal
        if self._primary_mod is None:
            return result
        primary_params = self.primary.get("params", {})
        try:
            primary_df = self._primary_mod.generate_signals(df, **primary_params)
            primary_sig = primary_df["signal"]
        except Exception as e:
            logger.warning(f"Primary signal error ({self.primary['id']}): {e}")
            return result

        # Confirmation signals (AND logic)
        confirm_mask = pd.Series(True, index=df.index)
        for mod, conf in zip(self._confirm_mods, self.confirmations):
            if mod is None:
                continue
            try:
                conf_params = conf.get("params", {})
                conf_df = mod.generate_signals(df, **conf_params)
                # Confirmation: buy signal must agree for entry
                confirm_mask = confirm_mask & (conf_df["signal"] >= 0)  # Not selling = OK
            except Exception as e:
                logger.warning(f"Confirmation error ({conf['id']}): {e}")

        # Market filter (must allow trading)
        filter_mask = pd.Series(True, index=df.index)
        if self._filter_mod is not None:
            try:
                filter_params = self.market_filter.get("params", {})
                filter_df = self._filter_mod.generate_signals(df, **filter_params)
                # Filter: signal != -1 means trading is allowed
                filter_mask = filter_df["signal"] != -1
            except Exception as e:
                logger.warning(f"Filter error ({self.market_filter['id']}): {e}")

        # Exit signal
        exit_sig = pd.Series(0, index=df.index)
        if self._exit_mod is not None:
            try:
                exit_params = self.exit_signal.get("params", {})
                exit_df = self._exit_mod.generate_signals(df, **exit_params)
                exit_sig = exit_df["signal"]
            except Exception as e:
                logger.warning(f"Exit error ({self.exit_signal['id']}): {e}")

        # Combine: entry when primary=buy + confirmed + filter allows
        entry_mask = (primary_sig == 1) & confirm_mask & filter_mask
        # Exit: exit_signal=sell or primary=sell
        exit_mask = (exit_sig == -1) | (primary_sig == -1)

        result.loc[entry_mask, "signal"] = 1
        result.loc[exit_mask, "signal"] = -1

        # Exit takes priority over entry on same bar
        both = entry_mask & exit_mask
        result.loc[both, "signal"] = -1

        return result


def generate_combinations(
    db: PipelineDB | None = None,
    max_strategies: int = 1000,
) -> list[CompositeStrategy]:
    """Generate strategy combinations from analyzed indicators.

    Rules:
    - 1 primary (required)
    - 0-2 confirmations
    - 0-1 market_filter
    - 0-1 exit_signal
    - Same indicator_type cannot appear in primary + confirmation
    - Min 2, max 4 indicators per strategy

    Returns:
        List of CompositeStrategy objects.
    """
    db = db or PipelineDB()
    by_role = get_indicators_by_role(db)

    primaries = by_role["primary_signal"]
    confirms = by_role["confirmation"]
    filters = by_role["market_filter"]
    exits = by_role["exit_signal"]

    if not primaries:
        logger.warning("No primary_signal indicators found — cannot generate strategies")
        return []

    logger.info(
        f"Indicator pool: {len(primaries)} primary, {len(confirms)} confirmation, "
        f"{len(filters)} filter, {len(exits)} exit"
    )

    strategies = []

    for primary in primaries:
        primary_type = primary.get("indicator_type", "")
        primary_dict = {"id": primary["id"], "params": _parse_params(primary)}

        # Generate confirmation combinations (0, 1, or 2)
        valid_confirms = [c for c in confirms if c.get("indicator_type", "") != primary_type]
        confirm_combos = [[]]
        confirm_combos += [[c] for c in valid_confirms]
        if len(valid_confirms) >= 2:
            confirm_combos += [list(c) for c in itertools.combinations(valid_confirms, 2)]

        # Filter options (None or one)
        filter_options = [None] + [f for f in filters]

        # Exit options (None or one)
        exit_options = [None] + [e for e in exits]

        for conf_combo in confirm_combos:
            for filt in filter_options:
                for exit_ind in exit_options:
                    # Count total indicators
                    n = 1 + len(conf_combo) + (1 if filt else 0) + (1 if exit_ind else 0)
                    if n < 2 or n > 4:
                        continue

                    # Check for duplicate indicators
                    all_ids = [primary["id"]]
                    all_ids.extend(c["id"] for c in conf_combo)
                    if filt:
                        all_ids.append(filt["id"])
                    if exit_ind:
                        all_ids.append(exit_ind["id"])
                    if len(set(all_ids)) != len(all_ids):
                        continue

                    sid = f"STR_{uuid.uuid4().hex[:8].upper()}"
                    strategy = CompositeStrategy(
                        strategy_id=sid,
                        primary=primary_dict,
                        confirmations=[
                            {"id": c["id"], "params": _parse_params(c)}
                            for c in conf_combo
                        ],
                        market_filter=(
                            {"id": filt["id"], "params": _parse_params(filt)}
                            if filt else None
                        ),
                        exit_signal=(
                            {"id": exit_ind["id"], "params": _parse_params(exit_ind)}
                            if exit_ind else None
                        ),
                    )
                    strategies.append(strategy)

                    if len(strategies) >= max_strategies:
                        logger.info(f"Reached max strategies limit: {max_strategies}")
                        return strategies

    logger.info(f"Generated {len(strategies)} strategy combinations")

    # Save to DB
    for s in strategies:
        db.insert_strategy({
            "id": s.strategy_id,
            "primary_indicator_id": s.primary["id"],
            "primary_params": json.dumps(s.primary.get("params", {})),
            "confirmation_ids": json.dumps([c["id"] for c in s.confirmations]),
            "confirmation_params": json.dumps([c.get("params", {}) for c in s.confirmations]),
            "filter_indicator_id": s.market_filter["id"] if s.market_filter else None,
            "filter_params": json.dumps(s.market_filter.get("params", {})) if s.market_filter else None,
            "exit_indicator_id": s.exit_signal["id"] if s.exit_signal else None,
            "exit_params": json.dumps(s.exit_signal.get("params", {})) if s.exit_signal else None,
            "template_type": "auto",
            "description": s.description,
        })

    return strategies


def _parse_params(ind: dict) -> dict:
    """Parse default_params from indicator data."""
    params_str = ind.get("default_params", "{}")
    if isinstance(params_str, str):
        try:
            return json.loads(params_str)
        except json.JSONDecodeError:
            return {}
    return params_str if isinstance(params_str, dict) else {}
