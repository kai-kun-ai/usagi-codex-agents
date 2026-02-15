package cli

import (
	"fmt"

	"github.com/kai-kun-ai/usagi-codex-agents/internal/autopilot"
	"github.com/spf13/cobra"
)

var autopilotStartCmd = &cobra.Command{
	Use:   "autopilot-start",
	Short: "Clear STOP file (watch will keep running)",
	RunE: func(cmd *cobra.Command, args []string) error {
		root, _ := cmd.Flags().GetString("root")
		return autopilot.ClearStop(root)
	},
}

var autopilotStopCmd = &cobra.Command{
	Use:   "autopilot-stop",
	Short: "Create STOP file (watch will stop)",
	RunE: func(cmd *cobra.Command, args []string) error {
		root, _ := cmd.Flags().GetString("root")
		p, err := autopilot.RequestStop(root)
		if err != nil {
			return err
		}
		fmt.Println(p)
		return nil
	},
}

var autopilotStatusCmd = &cobra.Command{
	Use:   "autopilot-status",
	Short: "Show whether STOP is requested",
	RunE: func(cmd *cobra.Command, args []string) error {
		root, _ := cmd.Flags().GetString("root")
		if autopilot.StopRequested(root) {
			fmt.Println("STOP_REQUESTED")
			return nil
		}
		fmt.Println("RUNNING")
		return nil
	},
}

func init() {
	rootCmd.AddCommand(autopilotStartCmd)
	rootCmd.AddCommand(autopilotStopCmd)
	rootCmd.AddCommand(autopilotStatusCmd)

	for _, c := range []*cobra.Command{autopilotStartCmd, autopilotStopCmd, autopilotStatusCmd} {
		c.Flags().String("root", ".", "Repository root")
	}
}
