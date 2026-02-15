package autopilot

import (
	"os"
	"path/filepath"
)

type Paths struct {
	Root string
}

func (p Paths) StopFile() string {
	return filepath.Join(p.Root, ".usagi", "STOP")
}

func (p Paths) StateFile() string {
	return filepath.Join(p.Root, ".usagi", "state.json")
}

func RequestStop(root string) (string, error) {
	p := Paths{Root: root}
	if err := os.MkdirAll(filepath.Dir(p.StopFile()), 0o755); err != nil {
		return "", err
	}
	if err := os.WriteFile(p.StopFile(), []byte("stop"), 0o644); err != nil {
		return "", err
	}
	return p.StopFile(), nil
}

func ClearStop(root string) error {
	p := Paths{Root: root}
	if _, err := os.Stat(p.StopFile()); err != nil {
		if os.IsNotExist(err) {
			return nil
		}
		return err
	}
	return os.Remove(p.StopFile())
}

func StopRequested(root string) bool {
	p := Paths{Root: root}
	_, err := os.Stat(p.StopFile())
	return err == nil
}
