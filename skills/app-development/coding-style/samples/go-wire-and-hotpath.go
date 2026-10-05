// Go's equivalent of a discriminated union: typed string constants + struct json tags (no iota).
// Plus hot-path lenient degradation: degradation points are consolidated into named functions.
// From polymarket-quant/pkg/live/types.go:10-16, 52-64, 244-263 (read 2026-10-05).
package live

type TokenSide string

const (
	TokenSideUp   TokenSide = "up"
	TokenSideDown TokenSide = "down"
)

// Wire structs always carry json tags; field names mirror the shared TS/Python contracts.
type QuoteMessage struct {
	Slug        string    `json:"slug"`
	Symbol      string    `json:"symbol"`
	Interval    string    `json:"interval"`
	AssetID     string    `json:"assetId"`
	TokenSide   TokenSide `json:"tokenSide"`
	Outcome     string    `json:"outcome"`
	TimestampMs int64     `json:"timestampMs"`
	BestBid     float64   `json:"bestBid"`
	BestAsk     float64   `json:"bestAsk"`
	Mid         float64   `json:"mid"`
	Spread      float64   `json:"spread"`
}

// ─── Hot-path lenient degradation (explicit tension point): ───
// A long-lived WS collector would rather record one bad message as 0/Down than crash the process; but degradation
// points must be consolidated into named functions (like these two), not scattered if err != nil { continue } blocks.
// The boundary layer (where humans read and decide) stays strict: parseTimestamp above returns an error on failure.
func ParseFloat(raw string) float64 {
	v, err := strconv.ParseFloat(strings.TrimSpace(raw), 64)
	if err != nil {
		return 0
	}
	return v
}

func TokenSideForAsset(upTokenID, downTokenID, assetID string) TokenSide {
	switch assetID {
	case upTokenID:
		return TokenSideUp
	case downTokenID:
		return TokenSideDown
	default:
		return TokenSideDown
	}
}

// ❌ Counterexample (constructed, not repository code): iota integer enums break cross-language wire readability
// type Status int
// const (
// 	StatusUp Status = iota  // serializes to 0/1; the TS/Python side cannot mirror it
// 	StatusDown
// )
