// Go config: three-level fallback - CLI flag > env (via godotenv) > default - collapsed into one helper.
// From polymarket-quant/apps/collect-data/cmd/root.go:95-113 (read 2026-10-05).
// Every config field goes through this helper; calling os.Getenv directly in business code is forbidden.
	resolved.CollectorHTTPAddr = valueFromFlagOrEnv(cmd, "collector-http-addr", resolved.CollectorHTTPAddr, "COLLECTOR_HTTP_ADDR")
	resolved.DashboardHTTPAddr = valueFromFlagOrEnv(cmd, "dashboard-http-addr", resolved.DashboardHTTPAddr, "DASHBOARD_HTTP_ADDR")
	resolved.DashboardStaticDir = valueFromFlagOrEnv(cmd, "dashboard-static-dir", resolved.DashboardStaticDir, "DASHBOARD_STATIC_DIR")

	return resolved, nil
}

// valueFromFlagOrEnv preserves Cobra's parsed flag value when the user passed
// the flag explicitly; otherwise it falls back to the environment.
func valueFromFlagOrEnv(cmd *cobra.Command, flagName, currentValue, envKey string) string {
	if cmd.Flags().Changed(flagName) {
		return currentValue
	}
	if v := os.Getenv(envKey); v != "" {
		return v
	}
	return currentValue
}
