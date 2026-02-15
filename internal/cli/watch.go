package cli

import (
	"path/filepath"
	"time"

	"github.com/kai-kun-ai/usagi-codex-agents/internal/watch"
	"github.com/spf13/cobra"
)

var watchCmd = &cobra.Command{
	Use:   "watch",
	Short: "Watch inputs/ and write reports to outputs/ until STOP file exists",
	RunE: func(cmd *cobra.Command, args []string) error {
		root, _ := cmd.Flags().GetString("root")
		inputs, _ := cmd.Flags().GetString("inputs")
		outputs, _ := cmd.Flags().GetString("outputs")
		workRoot, _ := cmd.Flags().GetString("work-root")
		statePath, _ := cmd.Flags().GetString("state")
		offline, _ := cmd.Flags().GetBool("offline")
		model, _ := cmd.Flags().GetString("model")
		debounceMs, _ := cmd.Flags().GetInt("debounce-ms")

		cfg := watch.DefaultConfig(root)
		if inputs != "" {
			cfg.InputsDir = inputs
		}
		if outputs != "" {
			cfg.OutputsDir = outputs
		}
		if workRoot != "" {
			cfg.WorkRoot = workRoot
		}
		if statePath != "" {
			cfg.StatePath = statePath
		}
		cfg.Offline = offline
		cfg.Model = model
		cfg.Debounce = time.Duration(debounceMs) * time.Millisecond

		// Normalize to absolute-ish paths for state consistency
		cfg.InputsDir = filepath.Clean(cfg.InputsDir)
		cfg.OutputsDir = filepath.Clean(cfg.OutputsDir)
		cfg.WorkRoot = filepath.Clean(cfg.WorkRoot)
		cfg.StatePath = filepath.Clean(cfg.StatePath)

		return watch.Run(cfg)
	},
}

func init() {
	rootCmd.AddCommand(watchCmd)
	watchCmd.Flags().String("root", ".", "Repository root")
	watchCmd.Flags().String("inputs", "", "Inputs dir (default: <root>/inputs)")
	watchCmd.Flags().String("outputs", "", "Outputs dir (default: <root>/outputs)")
	watchCmd.Flags().String("work-root", "", "Work root (default: <root>/work)")
	watchCmd.Flags().String("state", "", "State json path (default: <root>/.usagi/state.json)")
	watchCmd.Flags().Bool("offline", true, "Offline mode")
	watchCmd.Flags().String("model", "codex", "Model label")
	watchCmd.Flags().Int("debounce-ms", 400, "Debounce milliseconds")
}
