// What the library/app split looks like in Go: pkg/ explicitly declares it holds no persistence opinions.
// From polymarket-quant/pkg/collector/doc.go (full 19 lines, read 2026-10-05).
// This file is the design's self-description - the library exposes typed handler registration; IO opinions stay in the apps' internal/.
// Package collector exposes a high-level, persistence-free Polymarket data
// collector.
//
// Internally it wires:
//   - the Gamma metadata resolver,
//   - the market WebSocket client (orderbook + price-change + trade events),
//   - the Polymarket Real-Time Data Service (chainlink/binance price stream),
//   - the Binance kline WebSocket client,
//   - and the in-memory health tracker.
//
// The collector has no opinions about how messages are persisted. Consumers
// register typed handlers (OnQuote, OnTrade, OnBook, OnPrice, OnKline,
// OnLifecycle, OnHealth) and decide whether to publish to NATS, write to a
// database, drop into a ring buffer, or any combination of those.
//
// The cmd/polymarket.go CLI in this same module wires the same primitives
// together with file-based persistence (JSONL, parquet, S3); see it as a
// reference consumer.
package collector
