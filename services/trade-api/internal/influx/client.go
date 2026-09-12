package influx

import (
	"context"
	"database/sql"

	"github.com/lusd2904/smart-finance-platform/services/klineread"
	"github.com/lusd2904/smart-finance-platform/services/trade-api/internal/config"
	"github.com/lusd2904/smart-finance-platform/services/trade-api/internal/kline"
)

type barSource interface {
	QueryDaily(ctx context.Context, market, symbol, start, stop string, limit *int) ([]klineread.Bar, error)
	QueryMinute(ctx context.Context, market, symbol, start, stop string, limit *int) ([]klineread.Bar, error)
	LatestDailyDate(ctx context.Context, market, symbol string) (string, error)
}

type mysqlSource struct {
	*klineread.Reader
}

func (s mysqlSource) LatestDailyDate(ctx context.Context, market, symbol string) (string, error) {
	return s.Reader.LatestDailyDate(ctx, market, symbol)
}

type Client struct {
	src barSource
}

func New(_ *config.Config, db *sql.DB) *Client {
	return &Client{src: mysqlSource{Reader: klineread.NewSQL(db)}}
}

func NewWithSource(src barSource) *Client {
	return &Client{src: src}
}

func (c *Client) QueryKlines(ctx context.Context, market, symbol, start, stop string, limit *int) ([]kline.Bar, error) {
	if c == nil || c.src == nil {
		return []kline.Bar{}, nil
	}
	bars, err := c.src.QueryDaily(ctx, market, symbol, start, stop, limit)
	if err != nil {
		return nil, err
	}
	return toKlineBars(bars), nil
}

func (c *Client) QueryMinuteKlines(ctx context.Context, market, symbol, start, stop string, limit *int) ([]kline.Bar, error) {
	if c == nil || c.src == nil {
		return []kline.Bar{}, nil
	}
	bars, err := c.src.QueryMinute(ctx, market, symbol, start, stop, limit)
	if err != nil {
		return nil, err
	}
	return toKlineBars(bars), nil
}

func (c *Client) GetKlineSeries(ctx context.Context, market, symbol, period, start, stop string, limit *int) ([]kline.Bar, error) {
	p := kline.NormalizePeriod(period)
	start = kline.DefaultRangeStart(p, start)
	lim := kline.DefaultLimit(p, limit)
	if kline.IsMinutePeriod(p) {
		bars, err := c.QueryMinuteKlines(ctx, market, symbol, start, stop, lim)
		if err != nil {
			return nil, err
		}
		if how := kline.MinuteResampleRule(p); how != "" && len(bars) > 0 {
			return kline.ResampleMinuteBars(bars, how), nil
		}
		return bars, nil
	}
	bars, err := c.QueryKlines(ctx, market, symbol, start, stop, lim)
	if err != nil {
		return nil, err
	}
	if how := kline.DailyResampleRule(p); how != "" {
		return kline.ResampleDailyBars(bars, how), nil
	}
	return bars, nil
}

func (c *Client) LatestDate(ctx context.Context, market, symbol string) (string, error) {
	if c == nil || c.src == nil {
		return "", nil
	}
	return c.src.LatestDailyDate(ctx, market, symbol)
}

func toKlineBars(in []klineread.Bar) []kline.Bar {
	out := make([]kline.Bar, 0, len(in))
	for _, b := range in {
		out = append(out, kline.Bar{
			Date: b.Date, Open: b.Open, High: b.High, Low: b.Low, Close: b.Close, Volume: b.Volume,
		})
	}
	return out
}
