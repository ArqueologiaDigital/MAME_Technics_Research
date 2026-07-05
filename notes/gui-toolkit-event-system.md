# KN7000 GUI toolkit & event system (the "MILK" toolkit)

The KN7000 UI is a small windowing toolkit — the firmware calls it MILK — with a
focus-routed event queue and a set of widget classes. It is almost entirely
self-documented: the firmware's reflection tables (which produce
kn7000_disassembly/kn7000.sym) name hundreds of the functions. This note maps the
architecture, using those names, and connects it to the panel-button work in
panel-button-map.md. **Rule of thumb reinforced here: grep kn7000.sym before
reverse-engineering a UI function — most are already named.**

## Event queue

- The queue lives in work RAM at **0x5000757C**, with **0x38 (56)-byte entries**
  indexed per event slot (InitializeEventQueue at 0x484284B4 walks it as
  `base + id*0x38`; the low-level enqueue/dequeue calls library op 0x4C03C5AF).
- API (all named in kn7000.sym), two layers — a generic set and the "Main"-task
  wrappers that target the main task's queue:

  | generic (0x48429...) | Main-task wrapper | role |
  |---|---|---|
  | SendEvent 0x48429388     | MainSendEvent 0x484297EC   | deliver an event synchronously |
  | PostEvent 0x484293AD     | MainPostEvent 0x48429808   | enqueue an event |
  | GetEvent  0x484293D2     | MainGetEvent  0x48429824   | dequeue next event |
  | DispatchEvent 0x4842936F | MainDispatchEvent 0x484297DA | route an event to its handler |
  | DeleteEvent 0x484293F5, DeleteSpecificEvent 0x48429416 | MainDelete... | remove |
  | Get/SetRootEvent 0x48429631/0x484296A3  |   | the root (top) of the focus chain |
  | Get/SetFocusEvent 0x48429718/0x4842978A |   | the currently focused widget |

  There is also an Ap-task variant (ApDispatchEvent 0x4842986D, ApDeleteEventMmm
  0x48428D79). DispatchEvent/ApDispatchEvent funnel into a common core
  (0x48428C43 -> 0x48428792) that indexes the 0x5000757C queue.

- **Focus routing**: events are dispatched to the *focused* widget (GetFocusEvent)
  and bubble up the root chain (GetRootEvent/SetRootEvent) — a standard
  focus/parent event-routing model.

## Widget classes and their procedures

Naming conventions observed across kn7000.sym (symbol counts):

- **Ac\*...Proc** (288): **action procedures** — the per-widget-class event
  handlers. The widget classes are the "Box" family:
  AcListBoxProc, AcGridBoxProc, AcOnOffBoxProc, AcNumEditBoxProc,
  AcStrRadioBoxProc, AcBitEditBoxProc, AcRamBoxProc, AcMmmBoxProc (+ *EditBox
  variants), AcTitleMenuProc, ... i.e. list box, grid box, on/off toggle,
  numeric-edit box, string radio box, bit-edit box, menu, etc.
- **Iv\*...Proc** (47): **screen / window procedures** — IvScreenProc,
  IvPageControlProc, IvExitProc/IvExitScreenProc/IvExitWindowProc, IvFixWinProc,
  IvTrackSwitchProc, ... the screen- and window-level controllers.
- **Tt\*** (55): **type/template** records for the concrete UI instances
  (TtSdpart, TMidiPart, ...); paired T\* type tags (16).
- **Main\*** (266) and **Ap\*** (59): the **task-layer API** — Main = the main
  UI task, Ap = the application task. E.g. MainGetRhythmName 0x48416204,
  MainGetSoundName 0x48415FDC, MainDispatchEvent.

So a screen is an Iv\*Proc hosting a tree of Ac\*Box widgets; events dispatched to
the focused widget invoke its Ac\*BoxProc.

## How a panel-button press flows through it

1. The panel sub-CPUs report a switch change over the serial link (see
   panel-serial-protocol.md). The main CPU's button dispatcher
   (PanelButtonDispatch 0x484ADB59) reads the per-normSeg descriptor tables
   (0x48614978 bank A) and produces a stable **event code** for the button
   (0x00702020 = START/STOP, 0x00702005 arg = rhythm group, 0x00702010 = sound
   group, 0x00702000/01 = part mute; see panel-button-map.md).
2. That event is posted into the MILK queue (RefreshSwEvent 0x48414C98 is the
   switch-event refresh entry; posting uses PostEvent/SendEvent).
3. MainDispatchEvent routes it to the focused screen/widget, whose Ac\*Proc /
   Iv\*Proc handles it — e.g. pressing a rhythm-group key lands in the rhythm
   screen's handler, which calls MainGetRhythmName to update the display (this is
   why buttons visibly navigate the UI in the emulator).

## Why this matters for the driver / future work

- Any UI behaviour question ("what does event 0x7020xx do?") is answered by
  finding the Ac\*/Iv\*Proc that the focused screen dispatches to — all named.
- The genre/sound-group *name* mapping (long deferred) is a widget-level detail
  inside these procs (MainGetRhythmName / the rhythm screen's list box), not a
  simple table — consistent with why static/empirical attempts kept winding.
- No driver change needed; this is architectural documentation that makes the
  firmware's UI legible and cross-references the panel work.
