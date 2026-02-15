package autopilot

import (
	"os"
	"path/filepath"
	"testing"
)

func TestStopLifecycle(t *testing.T) {
	root := t.TempDir()
	if StopRequested(root) {
		t.Fatal("expected stop false")
	}
	p, err := RequestStop(root)
	if err != nil {
		t.Fatal(err)
	}
	if p != filepath.Join(root, ".usagi", "STOP") {
		t.Fatalf("unexpected path: %s", p)
	}
	if !StopRequested(root) {
		t.Fatal("expected stop true")
	}
	if err := ClearStop(root); err != nil {
		t.Fatal(err)
	}
	if StopRequested(root) {
		t.Fatal("expected stop false")
	}
	// clear when missing
	_ = os.Remove(filepath.Join(root, ".usagi", "STOP"))
	if err := ClearStop(root); err != nil {
		t.Fatal(err)
	}
}
