// Go error handling: fmt.Errorf with %w wrapping + package-name prefix + the offending input value.
// From polymarket-quant/apps/collect-data/internal/recorder/recorder.go:44-59 (read 2026-10-05).
// Note: the recorder lives in apps/collect-data/internal/ (persistence opinions belong to the app,
// locked inside the app via Go's internal/ visibility rule), not in pkg/.
func (r *Recorder) OpenAsset(assetID, eventSlug, marketSlug string) error {
	if _, ok := r.files[assetID]; ok {
		return nil
	}

	dir := filepath.Join(r.dataDir, eventSlug, marketSlug)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return fmt.Errorf("recorder: mkdir %s: %w", dir, err)
	}

	path := filepath.Join(dir, assetID+".jsonl")
	f, err := os.OpenFile(path, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o644)
	if err != nil {
		return fmt.Errorf("recorder: open %s: %w", path, err)
	}
