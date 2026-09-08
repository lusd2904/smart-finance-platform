package tradeexec

// Position is the flattened Longbridge stock_positions row used by Python.
type Position struct {
	Symbol            string
	SymbolName        string
	Quantity          float64
	AvailableQuantity float64
	CostPrice         float64
	Currency          string
	MarketValue       float64
	LastPrice         float64
}

// Balance is one currency slice from account_balance.
type Balance struct {
	Currency          string
	TotalCash         float64
	AvailableCash     float64
	NetAssets         float64
	MaxFinanceAmount  float64
}

// Account is the Python get_account_balance payload.
type Account struct {
	Configured bool
	Message    string
	Reason     string
	Balances   []Balance
}

// Order is a mapped today/history order.
type Order struct {
	OrderID          string
	Symbol           string
	StockName        string
	Side             string
	Status           string
	StatusLabel      string
	OrderType        string
	Quantity         float64
	Price            float64
	ExecutedQuantity float64
	ExecutedPrice    float64
	Currency         string
	SubmittedAt      string
	UpdatedAt        string
	Remark           string
	Filled           bool
	Open             bool
}

// Quote is a realtime quote row (lastDone).
type Quote struct {
	Symbol    string
	LastDone  float64
	Last      float64
	PrevClose float64
}

// SubmitReq is a validated order to send to Longbridge.
type SubmitReq struct {
	Symbol      string
	Side        string
	Quantity    float64
	OrderType   string
	Price       float64
	TimeInForce string
	Market      string
}

// SubmitResult matches Python submit_order return shape.
type SubmitResult struct {
	Configured bool   `json:"configured"`
	OK         bool   `json:"ok"`
	OrderID    string `json:"orderId,omitempty"`
	Symbol     string `json:"symbol,omitempty"`
	OutsideRTH string `json:"outsideRth,omitempty"`
	Message    string `json:"message"`
}

// UserSettings comes from quant_longbridge_config.
type UserSettings struct {
	UserID               int
	AutoTradeEnabled     bool
	DailyBuyRatio        float64
	MaxSymbolPositionPct float64
	HasKeys              bool
}

// Creds are decrypted Longbridge API keys for one user.
type Creds struct {
	UserID      int
	AppKey      string
	AppSecret   string
	AccessToken string
	Region      string
	Source      string
}

func (c Creds) Configured() bool {
	return c.AppKey != "" && c.AppSecret != "" && c.AccessToken != ""
}

func (c Creds) Signature() string {
	return itoa(c.UserID) + ":" + c.AppKey + ":" + c.AppSecret + ":" + c.AccessToken + ":" + c.Region
}

func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	neg := n < 0
	if neg {
		n = -n
	}
	var b [20]byte
	i := len(b)
	for n > 0 {
		i--
		b[i] = byte('0' + n%10)
		n /= 10
	}
	if neg {
		i--
		b[i] = '-'
	}
	return string(b[i:])
}
