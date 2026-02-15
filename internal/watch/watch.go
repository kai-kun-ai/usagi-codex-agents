package watch

import (
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/fsnotify/fsnotify"

	"github.com/kai-kun-ai/usagi-codex-agents/internal/autopilot"
)

type Config struct {
	InputsDir        string
	OutputsDir       string
	WorkRoot         string
	StatePath        string
	Debounce         time.Duration
	Recursive        bool
	StopFileRoot     string // repository root (contains .usagi/STOP)
	Offline          bool
	DryRun           bool
	Model            string
	PollStopInterval time.Duration
}

func DefaultConfig(root string) Config {
	return Config{
		InputsDir:        filepath.Join(root, "inputs"),
		OutputsDir:       filepath.Join(root, "outputs"),
		WorkRoot:         filepath.Join(root, "work"),
		StatePath:        filepath.Join(root, ".usagi", "state.json"),
		Debounce:         400 * time.Millisecond,
		Recursive:        true,
		StopFileRoot:     root,
		Offline:          true,
		DryRun:           false,
		Model:            "codex",
		PollStopInterval: 500 * time.Millisecond,
	}
}

func Run(cfg Config) error {
	if err := os.MkdirAll(cfg.InputsDir, 0o755); err != nil {
		return err
	}
	if err := os.MkdirAll(cfg.OutputsDir, 0o755); err != nil {
		return err
	}
	if err := os.MkdirAll(cfg.WorkRoot, 0o755); err != nil {
		return err
	}

	state, err := LoadState(cfg.StatePath)
	if err != nil {
		return err
	}

	jobs := make(chan string, 256)
	deb := NewDebouncer(cfg.Debounce, jobs)

	// initial scan
	filepath.WalkDir(cfg.InputsDir, func(p string, d fs.DirEntry, walkErr error) error {
		if walkErr != nil {
			return nil
		}
		if d.IsDir() {
			return nil
		}
		if strings.HasSuffix(strings.ToLower(p), ".md") {
			deb.Enqueue(p)
		}
		return nil
	})

	w, err := fsnotify.NewWatcher()
	if err != nil {
		return err
	}
	defer w.Close()

	addDir := func(dir string) error {
		return w.Add(dir)
	}

	if cfg.Recursive {
		err = filepath.WalkDir(cfg.InputsDir, func(p string, d fs.DirEntry, walkErr error) error {
			if walkErr != nil {
				return nil
			}
			if d.IsDir() {
				_ = addDir(p)
			}
			return nil
		})
	} else {
		err = addDir(cfg.InputsDir)
	}
	if err != nil {
		return err
	}

	// worker
	go func() {
		for p := range jobs {
			_ = processOne(p, cfg, state)
		}
	}()

	// events loop
	stopTick := time.NewTicker(cfg.PollStopInterval)
	defer stopTick.Stop()

	for {
		select {
		case ev := <-w.Events:
			if ev.Op&(fsnotify.Create|fsnotify.Write) == 0 {
				continue
			}
			// add new subdir in recursive mode
			if cfg.Recursive {
				if fi, statErr := os.Stat(ev.Name); statErr == nil && fi.IsDir() {
					_ = w.Add(ev.Name)
					continue
				}
			}
			if strings.HasSuffix(strings.ToLower(ev.Name), ".md") {
				deb.Enqueue(ev.Name)
			}
		case err := <-w.Errors:
			return err
		case <-stopTick.C:
			if autopilot.StopRequested(cfg.StopFileRoot) {
				return nil
			}
		}
	}
}

func processOne(path string, cfg Config, state *StateStore) error {
	fi, err := os.Stat(path)
	if err != nil {
		return nil
	}
	prev := state.LastMtimeNS(path)
	mtime := fi.ModTime().UnixNano()
	if mtime <= prev {
		return nil
	}

	b, err := os.ReadFile(path)
	if err != nil {
		return nil
	}

	// Placeholder report: Go移植の第一段階はwatch/autopilotの骨格確認。
	// 次PRで legacy/python の pipeline 相当を移植する。
	report := fmt.Sprintf("# usagi-corp watch report (stub)\n\n- input: %s\n- bytes: %d\n- offline: %v\n- model: %s\n\n(このレポート生成は暫定。次のPRでパイプラインをGo移植します)\n", filepath.Base(path), len(b), cfg.Offline, cfg.Model)

	out := filepath.Join(cfg.OutputsDir, strings.TrimSuffix(filepath.Base(path), filepath.Ext(path)) + ".report.md")
	if err := os.WriteFile(out, []byte(report), 0o644); err != nil {
		return err
	}

	state.SetMtimeNS(path, mtime)
	return state.Save()
}
