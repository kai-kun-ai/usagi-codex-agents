package watch

import (
	"sync"
	"time"
)

type Debouncer struct {
	Delay time.Duration
	mu    sync.Mutex
	t     map[string]*time.Timer
	out   chan string
}

func NewDebouncer(delay time.Duration, out chan string) *Debouncer {
	return &Debouncer{Delay: delay, t: map[string]*time.Timer{}, out: out}
}

func (d *Debouncer) Enqueue(path string) {
	d.mu.Lock()
	defer d.mu.Unlock()
	if old := d.t[path]; old != nil {
		old.Stop()
	}
	t := time.AfterFunc(d.Delay, func() {
		d.mu.Lock()
		delete(d.t, path)
		d.mu.Unlock()
		d.out <- path
	})
	d.t[path] = t
}
