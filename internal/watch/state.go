package watch

import (
	"encoding/json"
	"os"
	"path/filepath"
)

type StateStore struct {
	Path string
	Data map[string]int64 // path -> mtime_ns
}

func LoadState(path string) (*StateStore, error) {
	s := &StateStore{Path: path, Data: map[string]int64{}}
	b, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return s, nil
		}
		return nil, err
	}
	if len(b) == 0 {
		return s, nil
	}
	if err := json.Unmarshal(b, &s.Data); err != nil {
		return nil, err
	}
	return s, nil
}

func (s *StateStore) Save() error {
	if err := os.MkdirAll(filepath.Dir(s.Path), 0o755); err != nil {
		return err
	}
	b, err := json.MarshalIndent(s.Data, "", "  ")
	if err != nil {
		return err
	}
	b = append(b, '\n')
	return os.WriteFile(s.Path, b, 0o644)
}

func (s *StateStore) LastMtimeNS(p string) int64 {
	return s.Data[p]
}

func (s *StateStore) SetMtimeNS(p string, mtime int64) {
	s.Data[p] = mtime
}
