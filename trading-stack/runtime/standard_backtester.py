from __future__ import annotations

import csv
import heapq
import json
import math
from collections import deque
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from statistics import pstdev
from typing import Deque, Dict, Iterable, List, Mapping, Optional, Protocol, Sequence, Tuple

from .base_strategy import BaseStrategy
from .contracts import ExecutionRules, RiskFilters, SignalLogic


@dataclass(frozen=True, slots=True)
class Candle:
    timestamp_utc: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class HistoricalDataProvider(Protocol):
    def get_candles(
        self, symbol: str, timeframe: str, start_utc: datetime, end_utc: datetime
    ) -> Iterable[Candle]:
        ...


@dataclass(frozen=True, slots=True)
class TradeResult:
    symbol: str
    direction: str
    entry_utc: datetime
    exit_utc: datetime
    entry_price: float
    exit_price: float
    risk_pct: float
    risk_amount: float
    r_multiple: float
    pnl: float
    equity_before: float
    equity_after: float
    close_reason: str


@dataclass(frozen=True, slots=True)
class StressWindowReport:
    symbol: str
    start_date_utc: str
    end_date_utc: str
    volatility_score: float
    trade_count: int
    max_drawdown_pct: float
    profit_factor: float


@dataclass(frozen=True, slots=True)
class BacktestReport:
    Strategy_Name: str
    Strategy_Id: str
    Strategy_Version: str
    Assets: Tuple[str, ...]
    Start_Date_Utc: str
    End_Date_Utc: str
    Net_Return_Pct: float
    Max_Drawdown_Pct: float
    Profit_Factor: float
    Recovery_Factor: float
    Win_Rate_Pct: float
    Expectancy_R: float
    Institutional_Gate_Pass: bool
    Total_Trades: int
    Winners: int
    Losers: int
    Stress_Test: Tuple[StressWindowReport, ...]

    def to_dict(self) -> Dict[str, object]:
        payload = asdict(self)
        payload["Stress_Test"] = [asdict(item) for item in self.Stress_Test]
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True, default=str)


@dataclass(slots=True)
class _Position:
    symbol: str
    direction: str
    entry_utc: datetime
    entry_price: float
    stop_price: float
    take_profit_price: float
    risk_distance: float
    risk_pct: float
    risk_amount: float
    equity_at_entry: float
    breakeven_moved: bool = False


@dataclass(slots=True)
class _H1Indicators:
    ema_fast: List[float]
    ema_slow: List[float]
    atr: List[float]
    slope_deg: List[float]
    adx_proxy: List[float]


@dataclass(slots=True)
class _SymbolState:
    tr_window: Deque[float]
    volume_window: Deque[float]
    atr_history: Deque[float]
    current_day: Optional[date] = None
    day_high: Optional[float] = None
    day_low: Optional[float] = None
    day_close: Optional[float] = None
    previous_day_ohlc: Optional[Tuple[float, float, float]] = None
    cumulative_pv: float = 0.0
    cumulative_volume: float = 0.0
    vwap: Optional[float] = None
    previous_close: Optional[float] = None
    volume_zscore: float = 0.0


@dataclass(frozen=True, slots=True)
class _SignalEvaluation:
    passed: bool
    direction: Optional[str]
    reasons: Tuple[str, ...]


class InMemoryDataProvider:
    """
    Data provider for direct runtime injection in VPS jobs.
    """

    def __init__(self, candles_by_symbol: Mapping[str, Mapping[str, Sequence[Candle]]]) -> None:
        self._candles: Dict[str, Dict[str, Tuple[Candle, ...]]] = {}
        for symbol, tf_map in candles_by_symbol.items():
            self._candles[symbol.upper()] = {
                timeframe.upper(): tuple(
                    sorted(
                        (
                            Candle(
                                timestamp_utc=self._to_utc(c.timestamp_utc),
                                open=float(c.open),
                                high=float(c.high),
                                low=float(c.low),
                                close=float(c.close),
                                volume=float(c.volume),
                            )
                            for c in tf_candles
                        ),
                        key=lambda candle: candle.timestamp_utc,
                    )
                )
                for timeframe, tf_candles in tf_map.items()
            }

    def get_candles(
        self, symbol: str, timeframe: str, start_utc: datetime, end_utc: datetime
    ) -> Iterable[Candle]:
        symbol_map = self._candles.get(symbol.upper(), {})
        rows = symbol_map.get(timeframe.upper(), ())
        start = self._to_utc(start_utc)
        end = self._to_utc(end_utc)
        return (row for row in rows if start <= row.timestamp_utc <= end)

    @staticmethod
    def _to_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class CSVDirectoryDataProvider:
    """
    CSV loader with line iteration.

    File naming:
      {symbol}_{timeframe}.csv
    """

    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)

    def get_candles(
        self, symbol: str, timeframe: str, start_utc: datetime, end_utc: datetime
    ) -> Iterable[Candle]:
        file_path = self.base_dir / f"{symbol.upper()}_{timeframe.upper()}.csv"
        if not file_path.exists():
            return ()

        start = self._to_utc(start_utc)
        end = self._to_utc(end_utc)
        out: List[Candle] = []
        with file_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts = self._parse_timestamp(row["timestamp"])
                if ts < start or ts > end:
                    continue
                out.append(
                    Candle(
                        timestamp_utc=ts,
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=float(row.get("volume", 0.0)),
                    )
                )
        out.sort(key=lambda candle: candle.timestamp_utc)
        return out

    @staticmethod
    def _to_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _parse_timestamp(raw: str) -> datetime:
        value = raw.strip()
        if value.endswith("Z"):
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        else:
            try:
                parsed = datetime.fromisoformat(value)
            except ValueError:
                parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)


class StandardBacktester:
    """
    Strategy-aligned dynamic backtester.

    Key properties:
    - Symbol list discovered from strategy.get_assets() at runtime.
    - Dynamic window: now - 24 months to now.
    - Candle-by-candle M15 simulation with H1 trend context.
    - Monday-Thursday entries only, 12:00-14:30 UTC entry window.
    - Mandatory force flatten at 19:55 UTC.
    """

    def __init__(
        self,
        strategy_skill: BaseStrategy,
        data_provider: HistoricalDataProvider,
        *,
        initial_equity: float = 10_000.0,
        lookback_months: int = 24,
        slippage_pips: float = 0.3,
        entry_start_utc: time = time(12, 0),
        entry_end_utc: time = time(14, 30),
        force_flatten_utc: time = time(19, 55),
        trade_days: Tuple[int, ...] = (0, 1, 2, 3),
    ) -> None:
        self.strategy_skill = strategy_skill
        self.data_provider = data_provider
        self.initial_equity = float(initial_equity)
        self.lookback_months = int(lookback_months)
        self.slippage_pips = float(slippage_pips)
        self.entry_start_utc = entry_start_utc
        self.entry_end_utc = entry_end_utc
        self.force_flatten_utc = force_flatten_utc
        self.trade_days = trade_days

        assets = tuple(str(symbol).upper() for symbol in strategy_skill.get_assets())
        if not assets:
            raise ValueError("strategy_skill.get_assets() returned empty symbol list.")
        self.assets = assets
        self.signal_logic = strategy_skill.get_signal_logic()
        self.risk_filters = strategy_skill.get_risk_filters()
        self.execution_rules = strategy_skill.get_execution_rules()

    def run(self, now_utc: Optional[datetime] = None) -> BacktestReport:
        end_utc = self._normalize_utc(now_utc or datetime.now(timezone.utc)).replace(second=0, microsecond=0)
        start_utc = self._subtract_months(end_utc, self.lookback_months)

        symbol_m15: Dict[str, Tuple[Candle, ...]] = {}
        symbol_h1: Dict[str, Tuple[Candle, ...]] = {}
        h1_indicators: Dict[str, _H1Indicators] = {}
        symbol_state: Dict[str, _SymbolState] = {}
        h1_index: Dict[str, int] = {}

        fast_period = int(self.signal_logic.parameters.get("emaFast", 20))
        slow_period = int(self.signal_logic.parameters.get("emaSlow", 50))
        atr_period = int(self.signal_logic.parameters.get("atrPeriod", 14))
        volume_lookback = int(self.signal_logic.parameters.get("volumeLookbackBars", 50))

        for symbol in self.assets:
            m15_rows = tuple(self._normalize_and_sort(self.data_provider.get_candles(symbol, "M15", start_utc, end_utc)))
            h1_rows = tuple(self._normalize_and_sort(self.data_provider.get_candles(symbol, "H1", start_utc, end_utc)))
            if len(m15_rows) < 4 or len(h1_rows) < 4:
                continue

            symbol_m15[symbol] = m15_rows
            symbol_h1[symbol] = h1_rows
            h1_indicators[symbol] = self._build_h1_indicators(h1_rows, fast_period, slow_period, atr_period)
            symbol_state[symbol] = _SymbolState(
                tr_window=deque(maxlen=max(atr_period, 2)),
                volume_window=deque(maxlen=max(volume_lookback, 10)),
                atr_history=deque(maxlen=4),
            )
            h1_index[symbol] = 0

        if not symbol_m15:
            raise ValueError("No historical candles found for strategy assets/timeframes.")

        open_positions: Dict[str, _Position] = {}
        closed_trades: List[TradeResult] = []

        equity = self.initial_equity
        peak_equity = self.initial_equity
        max_drawdown_pct = 0.0
        consecutive_losses = 0

        m15_cursor: Dict[str, int] = {}
        min_heap: List[Tuple[datetime, str, int]] = []
        for symbol, rows in symbol_m15.items():
            m15_cursor[symbol] = 1
            heapq.heappush(min_heap, (rows[0].timestamp_utc, symbol, 0))

        while min_heap:
            _, symbol, candle_idx = heapq.heappop(min_heap)
            candle = symbol_m15[symbol][candle_idx]
            state = symbol_state[symbol]
            state = self._update_symbol_state(state, candle)
            symbol_state[symbol] = state

            h1_idx = self._advance_h1_index(symbol_h1[symbol], h1_index[symbol], candle.timestamp_utc)
            h1_index[symbol] = h1_idx

            if symbol in open_positions:
                closed = self._process_open_position(
                    position=open_positions[symbol],
                    candle=candle,
                    symbol=symbol,
                    state=state,
                    execution_rules=self.execution_rules,
                )
                if closed is not None:
                    trade = self._finalize_trade(closed, equity)
                    equity = trade.equity_after
                    peak_equity = max(peak_equity, equity)
                    max_drawdown_pct = max(max_drawdown_pct, self._drawdown_pct(peak_equity, equity))
                    closed_trades.append(trade)
                    if trade.r_multiple < 0:
                        consecutive_losses += 1
                    else:
                        consecutive_losses = 0
                    del open_positions[symbol]

            if (
                symbol not in open_positions
                and len(open_positions) < self.execution_rules.max_concurrent_positions
                and self._is_trade_day(candle.timestamp_utc)
                and self._is_entry_window(candle.timestamp_utc.time())
                and candle.timestamp_utc.time() < self.force_flatten_utc
            ):
                signal_eval = self._evaluate_signal_gate(
                    symbol=symbol,
                    candle=candle,
                    state=state,
                    h1_rows=symbol_h1[symbol],
                    h1_idx=h1_idx,
                    h1_indicators=h1_indicators[symbol],
                    signal_logic=self.signal_logic,
                )
                if signal_eval.passed and signal_eval.direction:
                    maybe_position = self._build_position_if_allowed(
                        symbol=symbol,
                        direction=signal_eval.direction,
                        candle=candle,
                        state=state,
                        h1_indicators=h1_indicators[symbol],
                        h1_idx=h1_idx,
                        current_open_positions=open_positions,
                        consecutive_losses=consecutive_losses,
                        equity=equity,
                    )
                    if maybe_position is not None:
                        open_positions[symbol] = maybe_position

            next_idx = m15_cursor[symbol]
            if next_idx < len(symbol_m15[symbol]):
                next_candle = symbol_m15[symbol][next_idx]
                heapq.heappush(min_heap, (next_candle.timestamp_utc, symbol, next_idx))
                m15_cursor[symbol] = next_idx + 1

        for symbol, position in list(open_positions.items()):
            last_candle = symbol_m15[symbol][-1]
            closed = self._close_position_market(position, last_candle, reason="end_of_data")
            trade = self._finalize_trade(closed, equity)
            equity = trade.equity_after
            peak_equity = max(peak_equity, equity)
            max_drawdown_pct = max(max_drawdown_pct, self._drawdown_pct(peak_equity, equity))
            closed_trades.append(trade)
            del open_positions[symbol]

        gross_profit = sum(t.pnl for t in closed_trades if t.pnl > 0)
        gross_loss_abs = abs(sum(t.pnl for t in closed_trades if t.pnl < 0))
        net_return_pct = ((equity / self.initial_equity) - 1.0) * 100.0
        profit_factor = gross_profit / gross_loss_abs if gross_loss_abs > 0 else float("inf")
        recovery_factor = net_return_pct / max_drawdown_pct if max_drawdown_pct > 0 else float("inf")
        winners = sum(1 for t in closed_trades if t.pnl > 0)
        losers = sum(1 for t in closed_trades if t.pnl < 0)
        win_rate_pct = (winners / len(closed_trades) * 100.0) if closed_trades else 0.0
        expectancy_r = (
            sum(trade.r_multiple for trade in closed_trades) / len(closed_trades) if closed_trades else 0.0
        )
        institutional_gate_pass = (
            net_return_pct > 100.0 and max_drawdown_pct < 10.0 and profit_factor > 1.2
        )

        stress_windows = self._compute_stress_windows(
            candles_by_symbol=symbol_m15,
            trades=closed_trades,
            window_days=30,
            top_n=3,
        )

        return BacktestReport(
            Strategy_Name=self.strategy_skill.strategy_name or self.strategy_skill.__class__.__name__,
            Strategy_Id=self.strategy_skill.strategy_id,
            Strategy_Version=self.strategy_skill.strategy_version,
            Assets=tuple(sorted(symbol_m15.keys())),
            Start_Date_Utc=start_utc.isoformat(),
            End_Date_Utc=end_utc.isoformat(),
            Net_Return_Pct=round(net_return_pct, 6),
            Max_Drawdown_Pct=round(max_drawdown_pct, 6),
            Profit_Factor=round(profit_factor, 6) if math.isfinite(profit_factor) else float("inf"),
            Recovery_Factor=round(recovery_factor, 6) if math.isfinite(recovery_factor) else float("inf"),
            Win_Rate_Pct=round(win_rate_pct, 6),
            Expectancy_R=round(expectancy_r, 6),
            Institutional_Gate_Pass=institutional_gate_pass,
            Total_Trades=len(closed_trades),
            Winners=winners,
            Losers=losers,
            Stress_Test=tuple(stress_windows),
        )

    def _evaluate_signal_gate(
        self,
        *,
        symbol: str,
        candle: Candle,
        state: _SymbolState,
        h1_rows: Sequence[Candle],
        h1_idx: int,
        h1_indicators: _H1Indicators,
        signal_logic: SignalLogic,
    ) -> _SignalEvaluation:
        reasons: List[str] = []
        checks = tuple(check.lower() for check in signal_logic.required_checks)
        trigger = signal_logic.trigger.lower()

        ema_fast = h1_indicators.ema_fast[h1_idx]
        ema_slow = h1_indicators.ema_slow[h1_idx]
        direction_hint = 1 if ema_fast > ema_slow else -1 if ema_fast < ema_slow else 0
        direction: Optional[str] = "long" if direction_hint > 0 else "short" if direction_hint < 0 else None

        if direction is None:
            reasons.append("no_h1_direction")

        min_volume_z = float(signal_logic.parameters.get("volumeZScoreMin", 0.0))
        if any("volume" in check for check in checks) and state.volume_zscore < min_volume_z:
            reasons.append("volume_filter_failed")

        atr_rising_required = any("atr" in check and "rising" in check for check in checks)
        atr_now = self._current_atr(state)
        atr_prev = state.atr_history[-2] if len(state.atr_history) > 1 else atr_now
        if atr_rising_required and atr_now <= atr_prev:
            reasons.append("atr_not_rising")

        breakout_required = any("breakout" in check for check in checks) or "breakout" in trigger
        r3, s3 = self._camarilla_r3_s3(state)
        if breakout_required:
            breakout_long = r3 is not None and candle.close > r3
            breakout_short = s3 is not None and candle.close < s3
            if direction == "long" and not breakout_long:
                reasons.append("breakout_not_confirmed_long")
            elif direction == "short" and not breakout_short:
                reasons.append("breakout_not_confirmed_short")
            elif direction is None and not (breakout_long or breakout_short):
                reasons.append("breakout_not_confirmed")

        if "pullback" in trigger and state.vwap is not None and direction is not None:
            if direction == "long" and candle.close < state.vwap:
                reasons.append("pullback_condition_failed_long")
            if direction == "short" and candle.close > state.vwap:
                reasons.append("pullback_condition_failed_short")

        if reasons:
            return _SignalEvaluation(False, None, tuple(reasons))
        return _SignalEvaluation(True, direction, ())

    def _build_position_if_allowed(
        self,
        *,
        symbol: str,
        direction: str,
        candle: Candle,
        state: _SymbolState,
        h1_indicators: _H1Indicators,
        h1_idx: int,
        current_open_positions: Mapping[str, _Position],
        consecutive_losses: int,
        equity: float,
    ) -> Optional[_Position]:
        momentum_tier2 = (
            h1_indicators.slope_deg[h1_idx] >= self.risk_filters.min_tdi_slope_deg
            and h1_indicators.adx_proxy[h1_idx] >= self.risk_filters.min_h1_adx
        )

        tier_risk = self.risk_filters.tier2_risk_pct if momentum_tier2 else self.risk_filters.tier1_risk_pct
        if consecutive_losses >= self.risk_filters.dynamic_throttle_trigger_losses:
            tier_risk = min(tier_risk, self.risk_filters.dynamic_throttle_risk_pct)

        if (self._open_heat_pct(current_open_positions) + tier_risk) > self.risk_filters.global_heat_cap_pct:
            return None

        usd_exposure_after = self._net_usd_exposure_pct(current_open_positions) + self._usd_exposure_delta(
            symbol, direction, tier_risk
        )
        if abs(usd_exposure_after) > self.risk_filters.usd_correlation_cap_pct:
            return None

        if state.vwap is None:
            return None

        pivot_ok = self._pivot_gate(direction, candle.close, state)
        vwap_ok = candle.close >= state.vwap if direction == "long" else candle.close <= state.vwap
        atr_now = self._current_atr(state)
        atr_prev = state.atr_history[-2] if len(state.atr_history) > 1 else atr_now
        volatility_ok = atr_now > atr_prev and atr_now > 0
        if not (pivot_ok and vwap_ok and volatility_ok):
            return None

        spread_pips = self._spread_pips(candle.timestamp_utc)
        entry_price = self._entry_price(candle.close, direction, spread_pips, symbol)

        atr_stop_multiplier = float(self.signal_logic.parameters.get("atrStopMultiplier", 1.0))
        min_stop_distance = self._pips_to_price(3.0, symbol)
        stop_distance = max(atr_now * atr_stop_multiplier, min_stop_distance)
        if stop_distance <= 0:
            return None

        take_profit_r = float(
            self.signal_logic.parameters.get(
                "takeProfitR",
                self.signal_logic.parameters.get("tpR", 1.1),
            )
        )
        take_profit_r = max(0.1, take_profit_r)

        if direction == "long":
            stop_price = entry_price - stop_distance
            take_profit_price = entry_price + (take_profit_r * stop_distance)
        else:
            stop_price = entry_price + stop_distance
            take_profit_price = entry_price - (take_profit_r * stop_distance)

        risk_amount = equity * (tier_risk / 100.0)
        if risk_amount <= 0:
            return None

        return _Position(
            symbol=symbol,
            direction=direction,
            entry_utc=candle.timestamp_utc,
            entry_price=entry_price,
            stop_price=stop_price,
            take_profit_price=take_profit_price,
            risk_distance=stop_distance,
            risk_pct=tier_risk,
            risk_amount=risk_amount,
            equity_at_entry=equity,
        )

    def _process_open_position(
        self,
        *,
        position: _Position,
        candle: Candle,
        symbol: str,
        state: _SymbolState,
        execution_rules: ExecutionRules,
    ) -> Optional[TradeResult]:
        if candle.timestamp_utc.time() >= self.force_flatten_utc:
            return self._close_position_market(position, candle, "daily_force_flatten")

        if not position.breakeven_moved and self._breakeven_triggered(position, candle, execution_rules.breakeven_trigger_r):
            position.stop_price = position.entry_price
            position.breakeven_moved = True

        if candle.timestamp_utc.time() >= self._parse_hhmm(execution_rules.sunset_rule_utc):
            unrealized_r = self._unrealized_r(position, candle.close)
            if unrealized_r > 0:
                return self._close_position_market(position, candle, "sunset_rule_lock")

        if position.direction == "long":
            stop_hit = candle.low <= position.stop_price
            target_hit = candle.high >= position.take_profit_price
            if stop_hit and target_hit:
                return self._close_position_fixed(position, candle, position.stop_price, "intrabar_stop_then_target")
            if stop_hit:
                return self._close_position_fixed(position, candle, position.stop_price, "stop_loss")
            if target_hit:
                return self._close_position_fixed(position, candle, position.take_profit_price, "take_profit")
        else:
            stop_hit = candle.high >= position.stop_price
            target_hit = candle.low <= position.take_profit_price
            if stop_hit and target_hit:
                return self._close_position_fixed(position, candle, position.stop_price, "intrabar_stop_then_target")
            if stop_hit:
                return self._close_position_fixed(position, candle, position.stop_price, "stop_loss")
            if target_hit:
                return self._close_position_fixed(position, candle, position.take_profit_price, "take_profit")
        return None

    def _close_position_fixed(
        self,
        position: _Position,
        candle: Candle,
        exit_price: float,
        reason: str,
    ) -> TradeResult:
        r_multiple = self._calculate_r_multiple(position, exit_price)
        pnl = r_multiple * position.risk_amount
        return TradeResult(
            symbol=position.symbol,
            direction=position.direction,
            entry_utc=position.entry_utc,
            exit_utc=candle.timestamp_utc,
            entry_price=position.entry_price,
            exit_price=exit_price,
            risk_pct=position.risk_pct,
            risk_amount=position.risk_amount,
            r_multiple=r_multiple,
            pnl=pnl,
            equity_before=0.0,
            equity_after=0.0,
            close_reason=reason,
        )

    def _close_position_market(
        self,
        position: _Position,
        candle: Candle,
        reason: str,
    ) -> TradeResult:
        spread_pips = self._spread_pips(candle.timestamp_utc)
        exit_price = self._exit_market_price(candle.close, position.direction, spread_pips, position.symbol)
        return self._close_position_fixed(position, candle, exit_price, reason)

    def _finalize_trade(self, trade: TradeResult, equity_before: float) -> TradeResult:
        equity_after = equity_before + trade.pnl
        return TradeResult(
            symbol=trade.symbol,
            direction=trade.direction,
            entry_utc=trade.entry_utc,
            exit_utc=trade.exit_utc,
            entry_price=trade.entry_price,
            exit_price=trade.exit_price,
            risk_pct=trade.risk_pct,
            risk_amount=trade.risk_amount,
            r_multiple=trade.r_multiple,
            pnl=trade.pnl,
            equity_before=equity_before,
            equity_after=equity_after,
            close_reason=trade.close_reason,
        )

    def _compute_stress_windows(
        self,
        *,
        candles_by_symbol: Mapping[str, Sequence[Candle]],
        trades: Sequence[TradeResult],
        window_days: int,
        top_n: int,
    ) -> List[StressWindowReport]:
        candidates: List[Tuple[float, str, date, date]] = []
        for symbol, candles in candles_by_symbol.items():
            daily = self._daily_close_series(candles)
            if len(daily) < window_days + 1:
                continue
            for idx in range(0, len(daily) - window_days):
                window = daily[idx : idx + window_days + 1]
                closes = [price for _, price in window]
                returns = []
                for i in range(1, len(closes)):
                    prev = closes[i - 1]
                    cur = closes[i]
                    if prev <= 0 or cur <= 0:
                        continue
                    returns.append(math.log(cur / prev))
                if not returns:
                    continue
                vol = pstdev(returns) * math.sqrt(len(returns))
                start_day = window[0][0]
                end_day = window[-1][0]
                candidates.append((vol, symbol, start_day, end_day))

        candidates.sort(key=lambda item: item[0], reverse=True)
        top = candidates[:top_n]

        reports: List[StressWindowReport] = []
        for vol, symbol, start_day, end_day in top:
            scoped = [
                trade
                for trade in trades
                if trade.symbol == symbol and start_day <= trade.entry_utc.date() <= end_day
            ]
            metrics = self._trade_metrics(scoped)
            reports.append(
                StressWindowReport(
                    symbol=symbol,
                    start_date_utc=start_day.isoformat(),
                    end_date_utc=end_day.isoformat(),
                    volatility_score=round(vol, 8),
                    trade_count=len(scoped),
                    max_drawdown_pct=round(metrics["max_drawdown_pct"], 6),
                    profit_factor=round(metrics["profit_factor"], 6)
                    if math.isfinite(metrics["profit_factor"])
                    else float("inf"),
                )
            )
        return reports

    def _trade_metrics(self, trades: Sequence[TradeResult]) -> Dict[str, float]:
        if not trades:
            return {"max_drawdown_pct": 0.0, "profit_factor": 0.0}

        gross_profit = sum(t.pnl for t in trades if t.pnl > 0)
        gross_loss_abs = abs(sum(t.pnl for t in trades if t.pnl < 0))
        profit_factor = gross_profit / gross_loss_abs if gross_loss_abs > 0 else float("inf")

        equity = trades[0].equity_before
        peak = equity
        max_dd = 0.0
        for trade in trades:
            equity += trade.pnl
            peak = max(peak, equity)
            max_dd = max(max_dd, self._drawdown_pct(peak, equity))
        return {"max_drawdown_pct": max_dd, "profit_factor": profit_factor}

    @staticmethod
    def _daily_close_series(candles: Sequence[Candle]) -> List[Tuple[date, float]]:
        out: List[Tuple[date, float]] = []
        current_day: Optional[date] = None
        last_close = 0.0
        for candle in candles:
            day = candle.timestamp_utc.date()
            if current_day is None:
                current_day = day
            if day != current_day:
                out.append((current_day, last_close))
                current_day = day
            last_close = candle.close
        if current_day is not None:
            out.append((current_day, last_close))
        return out

    @staticmethod
    def _advance_h1_index(h1_rows: Sequence[Candle], current_index: int, target_ts: datetime) -> int:
        idx = current_index
        while idx + 1 < len(h1_rows) and h1_rows[idx + 1].timestamp_utc <= target_ts:
            idx += 1
        return idx

    @staticmethod
    def _normalize_and_sort(candles: Iterable[Candle]) -> List[Candle]:
        out: List[Candle] = []
        for candle in candles:
            ts = candle.timestamp_utc
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            else:
                ts = ts.astimezone(timezone.utc)
            out.append(
                Candle(
                    timestamp_utc=ts,
                    open=float(candle.open),
                    high=float(candle.high),
                    low=float(candle.low),
                    close=float(candle.close),
                    volume=float(candle.volume),
                )
            )
        out.sort(key=lambda item: item.timestamp_utc)
        return out

    @staticmethod
    def _normalize_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _subtract_months(value: datetime, months: int) -> datetime:
        year = value.year
        month = value.month - months
        while month <= 0:
            month += 12
            year -= 1

        day = min(value.day, StandardBacktester._days_in_month(year, month))
        return value.replace(year=year, month=month, day=day)

    @staticmethod
    def _days_in_month(year: int, month: int) -> int:
        if month == 12:
            next_month = date(year + 1, 1, 1)
        else:
            next_month = date(year, month + 1, 1)
        return (next_month - timedelta(days=1)).day

    def _is_trade_day(self, ts: datetime) -> bool:
        return ts.weekday() in self.trade_days

    def _is_entry_window(self, ts_time: time) -> bool:
        return self.entry_start_utc <= ts_time <= self.entry_end_utc

    @staticmethod
    def _parse_hhmm(raw: str) -> time:
        hour, minute = raw.split(":")
        return time(int(hour), int(minute))

    def _spread_pips(self, ts: datetime) -> float:
        hour = ts.hour
        if 0 <= hour < 6:
            return 1.5
        if 6 <= hour < 12:
            return 1.0
        if 12 <= hour < 16:
            return 0.5
        if 16 <= hour < 20:
            return 0.8
        return 1.2

    @staticmethod
    def _pip_size(symbol: str) -> float:
        upper = symbol.upper()
        if "JPY" in upper:
            return 0.01
        if upper.startswith("XAU"):
            return 0.1
        if upper.startswith("BTC"):
            return 1.0
        return 0.0001

    def _pips_to_price(self, pips: float, symbol: str) -> float:
        return pips * self._pip_size(symbol)

    def _entry_price(self, mid: float, direction: str, spread_pips: float, symbol: str) -> float:
        spread_px = self._pips_to_price(spread_pips, symbol)
        slippage_px = self._pips_to_price(self.slippage_pips, symbol)
        if direction == "long":
            return mid + (spread_px / 2.0) + slippage_px
        return mid - (spread_px / 2.0) - slippage_px

    def _exit_market_price(self, mid: float, direction: str, spread_pips: float, symbol: str) -> float:
        spread_px = self._pips_to_price(spread_pips, symbol)
        slippage_px = self._pips_to_price(self.slippage_pips, symbol)
        if direction == "long":
            return mid - (spread_px / 2.0) - slippage_px
        return mid + (spread_px / 2.0) + slippage_px

    @staticmethod
    def _drawdown_pct(peak: float, value: float) -> float:
        if peak <= 0:
            return 0.0
        return max(0.0, ((peak - value) / peak) * 100.0)

    @staticmethod
    def _calculate_r_multiple(position: _Position, exit_price: float) -> float:
        if position.risk_distance <= 0:
            return 0.0
        if position.direction == "long":
            return (exit_price - position.entry_price) / position.risk_distance
        return (position.entry_price - exit_price) / position.risk_distance

    @staticmethod
    def _unrealized_r(position: _Position, mid_price: float) -> float:
        if position.risk_distance <= 0:
            return 0.0
        if position.direction == "long":
            return (mid_price - position.entry_price) / position.risk_distance
        return (position.entry_price - mid_price) / position.risk_distance

    @staticmethod
    def _breakeven_triggered(position: _Position, candle: Candle, breakeven_r: float) -> bool:
        if position.risk_distance <= 0:
            return False
        threshold = breakeven_r * position.risk_distance
        if position.direction == "long":
            return candle.high >= (position.entry_price + threshold)
        return candle.low <= (position.entry_price - threshold)

    @staticmethod
    def _open_heat_pct(positions: Mapping[str, _Position]) -> float:
        return sum(position.risk_pct for position in positions.values())

    @staticmethod
    def _usd_exposure_delta(symbol: str, direction: str, risk_pct: float) -> float:
        upper = symbol.upper()
        if not upper.endswith("USD"):
            return 0.0
        return -risk_pct if direction == "long" else risk_pct

    def _net_usd_exposure_pct(self, positions: Mapping[str, _Position]) -> float:
        return sum(
            self._usd_exposure_delta(position.symbol, position.direction, position.risk_pct)
            for position in positions.values()
        )

    @staticmethod
    def _current_atr(state: _SymbolState) -> float:
        if not state.atr_history:
            return 0.0
        return state.atr_history[-1]

    @staticmethod
    def _pivot_gate(direction: str, close_price: float, state: _SymbolState) -> bool:
        r3, s3 = StandardBacktester._camarilla_r3_s3(state)
        if r3 is None or s3 is None:
            return False
        if direction == "long":
            return close_price > r3
        return close_price < s3

    @staticmethod
    def _camarilla_r3_s3(state: _SymbolState) -> Tuple[Optional[float], Optional[float]]:
        if state.previous_day_ohlc is None:
            return None, None
        high, low, close = state.previous_day_ohlc
        range_ = max(0.0, high - low)
        r3 = close + (range_ * 1.1 / 4.0)
        s3 = close - (range_ * 1.1 / 4.0)
        return r3, s3

    @staticmethod
    def _true_range(current: Candle, previous_close: Optional[float]) -> float:
        if previous_close is None:
            return max(0.0, current.high - current.low)
        return max(
            current.high - current.low,
            abs(current.high - previous_close),
            abs(current.low - previous_close),
        )

    def _update_symbol_state(self, state: _SymbolState, candle: Candle) -> _SymbolState:
        day = candle.timestamp_utc.date()
        if state.current_day is None:
            state.current_day = day
            state.day_high = candle.high
            state.day_low = candle.low
            state.day_close = candle.close
            state.cumulative_pv = candle.close * max(candle.volume, 0.0)
            state.cumulative_volume = max(candle.volume, 0.0)
        elif day != state.current_day:
            if state.day_high is not None and state.day_low is not None and state.day_close is not None:
                state.previous_day_ohlc = (state.day_high, state.day_low, state.day_close)
            state.current_day = day
            state.day_high = candle.high
            state.day_low = candle.low
            state.day_close = candle.close
            state.cumulative_pv = candle.close * max(candle.volume, 0.0)
            state.cumulative_volume = max(candle.volume, 0.0)
        else:
            state.day_high = max(state.day_high or candle.high, candle.high)
            state.day_low = min(state.day_low or candle.low, candle.low)
            state.day_close = candle.close
            state.cumulative_pv += candle.close * max(candle.volume, 0.0)
            state.cumulative_volume += max(candle.volume, 0.0)

        if state.cumulative_volume > 0:
            state.vwap = state.cumulative_pv / state.cumulative_volume

        tr = self._true_range(candle, state.previous_close)
        state.tr_window.append(tr)
        if state.tr_window:
            atr = sum(state.tr_window) / len(state.tr_window)
            state.atr_history.append(atr)

        state.volume_window.append(max(candle.volume, 0.0))
        if len(state.volume_window) >= 2:
            vol_mean = sum(state.volume_window) / len(state.volume_window)
            vol_std = pstdev(state.volume_window)
            state.volume_zscore = (
                (state.volume_window[-1] - vol_mean) / vol_std if vol_std > 0 else 0.0
            )
        else:
            state.volume_zscore = 0.0

        state.previous_close = candle.close
        return state

    @staticmethod
    def _build_h1_indicators(
        h1_rows: Sequence[Candle], fast_period: int, slow_period: int, atr_period: int
    ) -> _H1Indicators:
        closes = [row.close for row in h1_rows]
        tr_values: List[float] = []
        prev_close: Optional[float] = None
        for row in h1_rows:
            tr = StandardBacktester._true_range(row, prev_close)
            tr_values.append(tr)
            prev_close = row.close

        ema_fast = StandardBacktester._ema_series(closes, max(2, fast_period))
        ema_slow = StandardBacktester._ema_series(closes, max(2, slow_period))
        atr = StandardBacktester._rolling_mean(tr_values, max(2, atr_period))

        slope_deg: List[float] = []
        adx_proxy: List[float] = []
        lookback = 3
        for idx in range(len(h1_rows)):
            base_atr = atr[idx] if atr[idx] > 0 else 1e-9
            if idx >= lookback:
                delta = closes[idx] - closes[idx - lookback]
            else:
                delta = closes[idx] - closes[0]
            slope = math.degrees(math.atan(delta / base_atr))
            slope_deg.append(abs(slope))
            adx = min(100.0, abs(ema_fast[idx] - ema_slow[idx]) / base_atr * 100.0)
            adx_proxy.append(adx)

        return _H1Indicators(
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            atr=atr,
            slope_deg=slope_deg,
            adx_proxy=adx_proxy,
        )

    @staticmethod
    def _ema_series(values: Sequence[float], period: int) -> List[float]:
        out: List[float] = []
        if not values:
            return out
        alpha = 2.0 / (period + 1.0)
        ema = values[0]
        out.append(ema)
        for value in values[1:]:
            ema = (value * alpha) + (ema * (1.0 - alpha))
            out.append(ema)
        return out

    @staticmethod
    def _rolling_mean(values: Sequence[float], period: int) -> List[float]:
        out: List[float] = []
        window: Deque[float] = deque(maxlen=max(2, period))
        running_sum = 0.0
        for value in values:
            if len(window) == window.maxlen:
                running_sum -= window[0]
            window.append(value)
            running_sum += value
            out.append(running_sum / len(window))
        return out
