// Small browser-independent boundaries for cancellable turns and speech input.
// A cancelled HTTP request can still finish on the server. This gate only
// prevents obsolete browser results from changing the current conversation.
export class TurnGate {
  active = null;
  begin(workspace) {
    this.cancel();
    const controller = new AbortController();
    const turn = Object.freeze({workspace, signal: controller.signal});
    this.active = {turn, controller};
    return turn;
  }
  get current() { return this.active?.turn || null; }
  isCurrent(turn) { return Boolean(turn && this.current === turn && !turn.signal.aborted); }
  finish(turn) {
    if (!this.isCurrent(turn)) return false;
    this.active = null;
    return true;
  }
  cancel() {
    const previous = this.active;
    this.active = null;
    previous?.controller.abort();
    return Boolean(previous);
  }
}

export function speechParts(event) {
  const results = Array.from(event?.results || []);
  const text = results.map(result => typeof result?.[0]?.transcript === 'string' ? result[0].transcript : '').join(' ').replace(/\s+/g, ' ').trim().slice(0, 3000);
  // Never dispatch interim words or a mixture of final and unfinished words.
  return {text, final: Boolean(text && results.length && results.every(result => result && result.isFinal !== false))};
}

export function voiceStopCommand(input) {
  const text = String(input || '').trim().replace(/^(?:(?:hey|hi|halo)\s+)?nexus\b[,\s:]*/i, '').replace(/[.!?]+$/, '').trim();
  return /^(?:stop|bye|goodbye|cancel|stop (?:talking|speaking|listening|nexus)|cancel (?:the )?(?:reply|response)|berhenti|diam|batalkan|berhenti (?:bicara|berbicara|mendengarkan))$/i.test(text);
}
