#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Event-driven Producer–Consumer State Machine (OOP, Tkinter)

- UI (Tkinter) posts START/STOP events.
- Controller (state machine) coordinates Producer (thread) and Consumer (UI).
- Producer generates random values -> Queue.
- Consumer polls queue in UI loop and updates the label.

Run: python app.py
"""

import threading
import queue
import time
import random
from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional
import tkinter as tk
from tkinter import ttk


# ----------- Messages passed from Producer to Consumer -----------

@dataclass(frozen=True)
class RandomValueMsg:
    timestamp: float
    value: float


# ----------- Finite State Machine (FSM) definitions -----------

class State(Enum):
    IDLE = auto()
    RUNNING = auto()
    STOPPING = auto()


class Event(Enum):
    START = auto()
    STOP = auto()
    SHUTDOWN = auto()


# ----------- Producer (background thread) -----------

class RandomProducer(threading.Thread):
    """
    Background producer that pushes RandomValueMsg into a Queue at a fixed rate.
    Starts 'lazy': the thread runs, but emission occurs only when run_event is set.
    """
    def __init__(self, outbox: queue.Queue, hz: float = 10.0, name: str = "RandomProducer"):
        super().__init__(name=name, daemon=True)
        self.outbox = outbox
        self.period = 1.0 / max(hz, 1e-6)
        self._run_event = threading.Event()
        self._shutdown = threading.Event()

    # ---- control API called by Controller (FSM) ----
    def enable(self) -> None:
        self._run_event.set()

    def disable(self) -> None:
        self._run_event.clear()

    def shutdown(self) -> None:
        self._shutdown.set()
        # also stop producing immediately
        self._run_event.clear()

    # ---- thread loop ----
    def run(self) -> None:
        rng = random.Random()
        next_tick = time.perf_counter()
        while not self._shutdown.is_set():
            # pacing tick
            now = time.perf_counter()
            if now < next_tick:
                time.sleep(min(0.005, next_tick - now))
                continue
            next_tick += self.period

            # only produce when enabled
            if self._run_event.is_set():
                value = rng.random()
                try:
                    self.outbox.put_nowait(RandomValueMsg(timestamp=time.time(), value=value))
                except queue.Full:
                    # If UI is momentarily busy, drop oldest to stay real-time
                    try:
                        _ = self.outbox.get_nowait()
                    except queue.Empty:
                        pass
                    # best effort re-queue
                    try:
                        self.outbox.put_nowait(RandomValueMsg(timestamp=time.time(), value=value))
                    except queue.Full:
                        pass


# ----------- Controller (FSM) -----------

class Controller:
    """
    Event-driven FSM coordinating Producer and UI Consumer.
    """
    def __init__(self, producer: RandomProducer):
        self._producer = producer
        self._state = State.IDLE

    @property
    def state(self) -> State:
        return self._state

    def handle(self, event: Event) -> None:
        if self._state == State.IDLE:
            if event == Event.START:
                self._producer.enable()
                self._state = State.RUNNING
            elif event == Event.SHUTDOWN:
                self._producer.shutdown()
                self._state = State.STOPPING

        elif self._state == State.RUNNING:
            if event == Event.STOP:
                self._producer.disable()
                self._state = State.IDLE
            elif event == Event.SHUTDOWN:
                self._producer.shutdown()
                self._state = State.STOPPING

        elif self._state == State.STOPPING:
            # Terminal-ish state; nothing to do here besides allow exit.
            pass


# ----------- Consumer (UI: Tkinter) -----------

class RandomApp(tk.Tk):
    """
    Tkinter UI that consumes messages and renders them.
    """
    POLL_MS = 50  # consumer poll period

    def __init__(self):
        super().__init__()
        self.title("Event-Driven Producer–Consumer (Random Value)")
        self.geometry("420x220")
        self.minsize(360, 200)

        # Queue from Producer -> Consumer
        self._inbox: queue.Queue[RandomValueMsg] = queue.Queue(maxsize=64)

        # Producer & Controller
        self._producer = RandomProducer(self._inbox, hz=20.0)
        self._producer.start()
        self._controller = Controller(self._producer)

        # Build UI
        self._build_ui()
        self._update_controls()

        # Start consumer polling
        self.after(self.POLL_MS, self._poll_inbox)

        # Graceful shutdown
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---- UI creation ----
    def _build_ui(self) -> None:
        pad = 12

        wrapper = ttk.Frame(self, padding=pad)
        wrapper.pack(fill="both", expand=True)

        # Title
        title = ttk.Label(wrapper, text="Random Value Monitor", font=("Segoe UI", 16, "bold"))
        title.pack(pady=(0, pad))

        # Value display
        self._value_var = tk.StringVar(value="—")
        value_label = ttk.Label(wrapper, textvariable=self._value_var, font=("Consolas", 28, "bold"))
        value_label.pack(pady=(0, pad))

        # Status row
        row = ttk.Frame(wrapper)
        row.pack(pady=(0, pad))

        self._state_var = tk.StringVar(value="State: IDLE")
        state_lbl = ttk.Label(row, textvariable=self._state_var)
        state_lbl.pack(side="left", padx=(0, 10))

        self._rate_var = tk.StringVar(value="Rate: 0.0 Hz")
        rate_lbl = ttk.Label(row, textvariable=self._rate_var)
        rate_lbl.pack(side="left")

        # Controls
        controls = ttk.Frame(wrapper)
        controls.pack()

        self._btn_start = ttk.Button(controls, text="Start", command=self._on_start)
        self._btn_stop = ttk.Button(controls, text="Stop", command=self._on_stop)

        self._btn_start.pack(side="left", padx=6)
        self._btn_stop.pack(side="left", padx=6)

        # A thin style
        style = ttk.Style()
        try:
            # On Windows, 'vista' looks nice; fallback otherwise
            style.theme_use("vista")
        except tk.TclError:
            pass

        # Small help text
        help_txt = ttk.Label(
            wrapper,
            text="Click Start to begin streaming random values (Producer ➜ Queue ➜ Consumer/UI).",
            wraplength=380,
            foreground="#666"
        )
        help_txt.pack(pady=(pad, 0))

        # Internal for rate estimation
        self._last_rx_time: Optional[float] = None
        self._ema_rate: float = 0.0  # exponential moving average of Hz

    # ---- UI events ----
    def _on_start(self) -> None:
        self._controller.handle(Event.START)
        self._update_controls()

    def _on_stop(self) -> None:
        self._controller.handle(Event.STOP)
        self._update_controls()

    def _on_close(self) -> None:
        # Transition to shutdown
        self._controller.handle(Event.SHUTDOWN)
        # Give producer a brief moment to stop
        self.after(100, self.destroy)

    # ---- UI helpers ----
    def _update_controls(self) -> None:
        st = self._controller.state
        self._state_var.set(f"State: {st.name}")
        self._btn_start.config(state=("disabled" if st == State.RUNNING else "normal"))
        self._btn_stop.config(state=("normal" if st == State.RUNNING else "disabled"))

    # ---- Consumer polling ----
    def _poll_inbox(self) -> None:
        processed = 0
        # Drain a small batch to keep UI snappy
        while processed < 10:
            try:
                msg: RandomValueMsg = self._inbox.get_nowait()
            except queue.Empty:
                break

            self._render_value(msg)
            processed += 1

        self.after(self.POLL_MS, self._poll_inbox)

    def _render_value(self, msg: RandomValueMsg) -> None:
        # Update numeric display
        self._value_var.set(f"{msg.value:0.6f}")

        # Estimate rate (EMA)
        now = time.perf_counter()
        if self._last_rx_time is not None:
            inst_rate = 1.0 / max(now - self._last_rx_time, 1e-6)
            alpha = 0.2
            self._ema_rate = (1 - alpha) * self._ema_rate + alpha * inst_rate
        else:
            self._ema_rate = 0.0
        self._last_rx_time = now
        self._rate_var.set(f"Rate: {self._ema_rate:0.1f} Hz")


# ----------- main -----------

def main():
    app = RandomApp()
    app.mainloop()


if __name__ == "__main__":
    main()
