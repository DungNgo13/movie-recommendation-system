/**
 * Minimal XMLHttpRequest stand-in for upload tests. No network is ever used:
 * tests drive progress/load/error/abort events manually.
 */
type Listener = (event: ProgressEvent) => void;

class FakeEventTarget {
  private listeners = new Map<string, Listener[]>();

  addEventListener(type: string, listener: Listener): void {
    const list = this.listeners.get(type) ?? [];
    list.push(listener);
    this.listeners.set(type, list);
  }

  dispatch(type: string, init: { loaded?: number; total?: number; lengthComputable?: boolean } = {}): void {
    const event = {
      type,
      loaded: init.loaded ?? 0,
      total: init.total ?? 0,
      lengthComputable: init.lengthComputable ?? true,
    } as unknown as ProgressEvent;
    for (const listener of this.listeners.get(type) ?? []) listener(event);
  }
}

export class FakeXHR extends FakeEventTarget {
  static instances: FakeXHR[] = [];

  static reset(): void {
    FakeXHR.instances = [];
  }

  static last(): FakeXHR {
    const xhr = FakeXHR.instances[FakeXHR.instances.length - 1];
    if (!xhr) throw new Error('No XHR was created');
    return xhr;
  }

  readonly upload = new FakeEventTarget();
  method: string | null = null;
  url: string | null = null;
  requestHeaders: Record<string, string> = {};
  body: unknown = undefined;
  status = 0;
  responseText = '';
  aborted = false;

  constructor() {
    super();
    FakeXHR.instances.push(this);
  }

  open(method: string, url: string): void {
    this.method = method;
    this.url = url;
  }

  setRequestHeader(name: string, value: string): void {
    this.requestHeaders[name] = value;
  }

  send(body?: unknown): void {
    this.body = body;
  }

  abort(): void {
    this.aborted = true;
    this.dispatch('abort');
  }

  // ── Test drivers ────────────────────────────────────────────────────────
  progress(loaded: number, total: number): void {
    this.upload.dispatch('progress', { loaded, total, lengthComputable: true });
  }

  respond(status: number, responseText = ''): void {
    this.status = status;
    this.responseText = responseText;
    this.dispatch('load');
  }

  failNetwork(): void {
    this.dispatch('error');
  }
}
