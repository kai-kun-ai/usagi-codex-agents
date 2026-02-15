package main

import (
	"fmt"
	"os"
	"path/filepath"
	"time"

	"github.com/kai-kun-ai/usagi-codex-agents/internal/autopilot"
	"github.com/kai-kun-ai/usagi-codex-agents/internal/watch"
)

var (
	Version = "dev"
	Commit  = "none"
	Date    = "unknown"
)

func main() {
	args := os.Args[1:]
	if len(args) == 0 {
		usage()
		os.Exit(2)
	}

	switch args[0] {
	case "version":
		fmt.Printf("usagi-corp %s (%s) %s\n", Version, Commit, Date)
		return
	case "autopilot-start":
		root := rootFrom(args[1:])
		if err := autopilot.ClearStop(root); err != nil {
			fatal(err)
		}
		return
	case "autopilot-stop":
		root := rootFrom(args[1:])
		p, err := autopilot.RequestStop(root)
		if err != nil {
			fatal(err)
		}
		fmt.Println(p)
		return
	case "autopilot-status":
		root := rootFrom(args[1:])
		if autopilot.StopRequested(root) {
			fmt.Println("STOP_REQUESTED")
			return
		}
		fmt.Println("RUNNING")
		return
	case "watch":
		root := rootFrom(args[1:])
		cfg := watch.DefaultConfig(root)
		// minimal flags: --inputs/--outputs/--state
		for i := 1; i < len(args); i++ {
			if args[i] == "--inputs" && i+1 < len(args) {
				cfg.InputsDir = args[i+1]
				i++
				continue
			}
			if args[i] == "--outputs" && i+1 < len(args) {
				cfg.OutputsDir = args[i+1]
				i++
				continue
			}
			if args[i] == "--state" && i+1 < len(args) {
				cfg.StatePath = args[i+1]
				i++
				continue
			}
			if args[i] == "--debounce-ms" && i+1 < len(args) {
				// deprecated in polling mode (kept for compatibility)
				i++
				continue
			}
		}
		cfg.InputsDir = filepath.Clean(cfg.InputsDir)
		cfg.OutputsDir = filepath.Clean(cfg.OutputsDir)
		cfg.WorkRoot = filepath.Clean(cfg.WorkRoot)
		cfg.StatePath = filepath.Clean(cfg.StatePath)
		cfg.PollStopInterval = 500 * time.Millisecond

		if err := watch.Run(cfg); err != nil {
			fatal(err)
		}
		return
	default:
		usage()
		os.Exit(2)
	}
}

func usage() {
	fmt.Fprintln(os.Stderr, "usagi-corp <command> [--root PATH]")
	fmt.Fprintln(os.Stderr, "commands: version | watch | autopilot-start | autopilot-stop | autopilot-status")
}

func rootFrom(args []string) string {
	root := "."
	for i := 0; i < len(args); i++ {
		if args[i] == "--root" && i+1 < len(args) {
			root = args[i+1]
			break
		}
	}
	return root
}

func fatal(err error) {
	fmt.Fprintln(os.Stderr, err)
	os.Exit(1)
}
