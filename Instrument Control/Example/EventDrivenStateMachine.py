#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import threading
import queue
import time
import random
from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional, Union
import tkinter as tk
from tkinter import ttk

# ---------------- Messages ----------------

class Command(Enum):
    START = auto()
    STOP = auto()
    SHUTDOWN = auto()

class State(Enum):
    IDLE = auto()
    RUNNING = auto()
    STOPPING = auto()

@dataclass(frozen=True)
class UiRenderValue:
    value: float
    t_wall: float

@dataclass(frozen=True)
class UiRenderState:
    state: State

UiMsg = Union[UiRenderValue, UiRenderState]

# ---------------- Consumer State Machine (all side-effects live here) ----------------

class RandomConsumer(threading.Thread):
    """
    Consumer/State-Machine that:
      - Consumes Commands from cmd_q (UI → Consumer).
      - Produces UiMsg into ui_q (Consumer → UI).
    All side-effects (timers, random generation, device I/O) are confined here.
    """
    def __init__(self, cmd_q: queue.Queue, ui_q: queue.Queue, hz: float = 20.0):
        super().__init__(daemon=True, name="RandomConsumer")
        self.cmd_q = cmd_q
        self.ui_q = ui_q
        self.hz = max(hz, 1e-6)
        self.state = State.IDLE
        self._rng = random.Random()

    def _set_state(self, s: State) -> None:
        self.state = s
        # Notify UI (pure render message, no side-effect in UI except drawing)
        self._post_ui(UiRenderState(s))

    def _post_ui(self, msg: UiMsg) -> None:
        try:
            self.ui_q.put_nowait(msg)
        except queue.Full:
            # If UI is temporarily busy, drop latest render (ok for telemetry)
            pass

    def run(self) -> None:
        period = 1.0 / self.hz
        next_tick = time.perf_counter()
        self._set_state(State.IDLE)

        while True:
            # 1) Handle commands (event-driven)
            try:
                cmd = self.cmd_q.get_nowait()
                if self.state == State.IDLE:
                    if cmd == Command.START:
                        self._set_state(State.RUNNING)
                    elif cmd == Command.SHUTDOWN:
                        self._set_state(State.STOPPING)
                        break

                elif self.state == State.RUNNING:
                    if cmd == Command.STOP:
                        self._set_state(State.IDLE)
                    elif cmd == Command.SHUTDOWN:
                        self._set_state(State.STOPPING)
                        break

            except queue.Empty:
                pass

            # 2) Execute state behavior (side effects live here)
            now = time.perf_counter()
            if self.state == State.RUNNING and now >= next_tick:
                next_tick += period
                # side-effect: generate data (simulate hardware/IO/timing)
                val = self._rng.random()
                self._post_ui(UiRenderValue(value=val, t_wall=time.time()))

            # Cooperative sleep
            time.sleep(0.001)

# ---------------- UI (Producer of commands; Consumer only of render messages) ----------------

class App(tk.Tk):
    POLL_MS = 40

    def __init__(self):
        super().__init__()
        self.title("Event-Driven Producer → Consumer (FSM)")
        self.geometry("460x220")

        # Queues
        self.cmd_q: queue.Queue[Command] = queue.Queue(maxsize=64)  # UI → Consumer
        self.ui_q: queue.Queue[UiMsg] = queue.Queue(maxsize=128)    # Consumer → UI

        # Consumer FSM (owns side effects)
        self.consumer = RandomConsumer(self.cmd_q, self.ui_q, hz=20.0)
        self.consumer.start()

        # UI
        self._build_ui()
        self.after(self.POLL_MS, self._poll_ui_q)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        pad = 12
        frame = ttk.Frame(self, padding=pad)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Random Value Monitor (FSM owns side-effects)",
                  font=("Segoe UI", 14, "bold")).pack(pady=(0, pad))

        self.value_var = tk.StringVar(value="—")
        ttk.Label(frame, textvariable=self.value_var,
                  font=("Consolas", 28, "bold")).pack(pady=(0, pad))

        row = ttk.Frame(frame); row.pack(pady=(0, pad))
        self.state_var = tk.StringVar(value="State: —")
        self.rate_var  = tk.StringVar(value="Rate: 0.0 Hz")
        ttk.Label(row, textvariable=self.state_var).pack(side="left", padx=(0, 10))
        ttk.Label(row, textvariable=self.rate_var).pack(side="left")

        controls = ttk.Frame(frame); controls.pack()
        ttk.Button(controls, text="Start", command=self._on_start).pack(side="left", padx=6)
        ttk.Button(controls, text="Stop",  command=self._on_stop ).pack(side="left", padx=6)

        ttk.Label(frame, foreground="#666",
                  text="UI PRODUCES only Commands ➜ Consumer FSM\n"
                       "Consumer FSM owns all side-effects and emits UiRender messages ➜ UI renders").pack(pady=(pad, 0))

        # internals for rate estimate
        self._last_rx: Optional[float] = None
        self._ema = 0.0

    # --- UI -> Consumer commands (no side-effects here) ---
    def _on_start(self):
        self.cmd_q.put(Command.START)

    def _on_stop(self):
        self.cmd_q.put(Command.STOP)

    def _on_close(self):
        self.cmd_q.put(Command.SHUTDOWN)
        self.after(120, self.destroy)

    # --- UI <- Consumer render messages (pure rendering only) ---
    def _poll_ui_q(self):
        processed = 0
        while processed < 12:
            try:
                msg = self.ui_q.get_nowait()
            except queue.Empty:
                break

            if isinstance(msg, UiRenderState):
                self.state_var.set(f"State: {msg.state.name}")
            elif isinstance(msg, UiRenderValue):
                self.value_var.set(f"{msg.value:0.6f}")
                # rate estimate (UI-side math is not a side-effect on the world)
                now = time.perf_counter()
                if self._last_rx is not None:
                    inst = 1.0 / max(now - self._last_rx, 1e-6)
                    self._ema = 0.2 * inst + 0.8 * self._ema
                self._last_rx = now
                self.rate_var.set(f"Rate: {self._ema:0.1f} Hz")

            processed += 1

        self.after(self.POLL_MS, self._poll_ui_q)

def main():
    App().mainloop()

if __name__ == "__main__":
    main()
