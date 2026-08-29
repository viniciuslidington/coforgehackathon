/**
 * Reads the server's server-sent event stream.
 *
 * Hand-rolled rather than `EventSource` because every streaming endpoint here
 * is a POST with a JSON body and needs to be abortable — neither of which
 * `EventSource` supports. The wire format is bare `data: {json}` frames
 * separated by a blank line, matching `app/services/sse.py` on the server.
 */
export async function readSseStream<Event>(
  response: Response,
  onEvent: (event: Event) => void,
  isTerminal: (event: Event) => boolean,
  terminalError: string,
): Promise<void> {
  if (!response.body) {
    throw new Error('Streaming is unavailable in this browser.');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let sawTerminalEvent = false;

  const emitFrames = (flush = false) => {
    buffer = buffer.replaceAll('\r\n', '\n');
    const frames = buffer.split('\n\n');
    buffer = flush ? '' : (frames.pop() ?? '');
    for (const frame of frames) {
      const payload = frame
        .split('\n')
        .filter(line => line.startsWith('data:'))
        .map(line => line.slice(5).trimStart())
        .join('\n');
      if (!payload) continue;
      const event = JSON.parse(payload) as Event;
      if (isTerminal(event)) sawTerminalEvent = true;
      onEvent(event);
    }
  };

  for (;;) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    emitFrames(done);
    if (done) break;
  }

  // A stream that ends without a terminal frame means the server died
  // mid-answer; surfacing that beats leaving the UI spinning forever.
  if (!sawTerminalEvent) {
    throw new Error(terminalError);
  }
}
