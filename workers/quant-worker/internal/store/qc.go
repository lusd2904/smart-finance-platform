package store

import (
	"context"
	"strings"

	"github.com/lusd2904/smart-finance-platform/workers/quant-worker/internal/factor"
	"github.com/lusd2904/smart-finance-platform/workers/quant-worker/internal/factorqc"
)

func (s *Service) RunFactorQC(ctx context.Context, market string) (map[string]any, error) {
	market = strings.ToUpper(strings.TrimSpace(market))
	if market == "" {
		market = "US"
	}
	insts := factor.UniverseForMarket(market)
	symbols := make([]string, 0, len(insts))
	for _, inst := range insts {
		symbols = append(symbols, inst.Symbol)
	}
	fetched, err := s.reader.QueryKlinesMany(ctx, market, symbols, "-280d", 260)
	if err != nil {
		return map[string]any{
			"ok": false, "engine": factorqc.EngineVersion, "market": market,
			"message": err.Error(), "items": []any{}, "saved": 0,
		}, nil
	}
	raw := map[string][]struct {
		Date   string
		Close  float64
		Volume float64
	}{}
	for sym, bars := range fetched {
		rows := make([]struct {
			Date   string
			Close  float64
			Volume float64
		}, 0, len(bars))
		for _, b := range bars {
			rows = append(rows, struct {
				Date   string
				Close  float64
				Volume float64
			}{b.Date, b.Close, b.Volume})
		}
		raw[sym] = rows
	}
	panel := factorqc.KlinesToPanel(raw)
	report := factorqc.ComputeReport(panel, market)
	saved := 0
	if len(report.Items) > 0 {
		n, err := s.persistQC(ctx, report)
		if err != nil {
			report.Saved = 0
		} else {
			saved = n
			report.Saved = n
		}
	}
	return map[string]any{
		"ok": report.OK, "engine": report.Engine, "market": report.Market,
		"asOf": report.AsOf, "symbolCount": report.SymbolCount,
		"itemCount": report.ItemCount, "okCount": report.OKCount,
		"periods": report.Periods, "message": report.Message,
		"items": report.Items, "saved": saved,
	}, nil
}

func (s *Service) persistQC(ctx context.Context, report factorqc.Report) (int, error) {
	saved := 0
	for _, item := range report.Items {
		payload := map[string]any{
			"engine": report.Engine, "family": item.Family,
			"quantiles": item.Quantiles, "icPositiveRatio": item.ICPositiveRatio, "ok": item.OK,
		}
		var qcID int64
		err := s.db.QueryRowContext(ctx, `
SELECT qc_id FROM quant_factor_qc WHERE factor_key=? AND market=? AND horizon=?`,
			item.FactorKey, report.Market, item.Horizon).Scan(&qcID)
		if err == nil && qcID > 0 {
			_, err = s.db.ExecContext(ctx, `
UPDATE quant_factor_qc
SET factor_label=?, ic_mean=?, ic_std=?, ir=?, spread=?, sample_dates=?, symbol_count=?,
    as_of=?, quantile_json=?, payload_json=?, create_time=NOW()
WHERE qc_id=?`,
				item.FactorLabel, item.ICMean, item.ICStd, item.IR, item.Spread,
				item.SampleDates, item.SymbolCount, report.AsOf,
				mustJSON(item.Quantiles), mustJSON(payload), qcID)
		} else {
			_, err = s.db.ExecContext(ctx, `
INSERT INTO quant_factor_qc
(factor_key, factor_label, market, horizon, ic_mean, ic_std, ir, spread,
 sample_dates, symbol_count, as_of, quantile_json, payload_json, create_time)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NOW())`,
				item.FactorKey, item.FactorLabel, report.Market, item.Horizon,
				item.ICMean, item.ICStd, item.IR, item.Spread,
				item.SampleDates, item.SymbolCount, report.AsOf,
				mustJSON(item.Quantiles), mustJSON(payload))
		}
		if err != nil {
			return saved, err
		}
		saved++
	}
	return saved, nil
}
