package watch

import "testing"

func TestStateRoundTrip(t *testing.T) {
	p := t.TempDir() + "/state.json"
	s, err := LoadState(p)
	if err != nil {
		t.Fatal(err)
	}
	if s.LastMtimeNS("x") != 0 {
		t.Fatal("expected default 0")
	}
	s.SetMtimeNS("x", 123)
	if err := s.Save(); err != nil {
		t.Fatal(err)
	}
	s2, err := LoadState(p)
	if err != nil {
		t.Fatal(err)
	}
	if s2.LastMtimeNS("x") != 123 {
		t.Fatalf("expected 123 got %d", s2.LastMtimeNS("x"))
	}
}
