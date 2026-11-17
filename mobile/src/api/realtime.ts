import { API_ORIGIN } from './client';

export type RealtimeEvent = {
  type: string;
  data?: unknown;
  lobby_id?: string;
  code?: string;
};

type Listener = (event: RealtimeEvent) => void;

const listeners = new Set<Listener>();
const lobbies = new Set<string>();
let socket: WebSocket | null = null;
let currentToken: string | null = null;
let heartbeat: ReturnType<typeof setInterval> | null = null;
let reconnect: ReturnType<typeof setTimeout> | null = null;
let closedByUser = false;

function dispatch(event: RealtimeEvent) {
  for (const listener of listeners) {
    try {
      listener(event);
    } catch {
      // Um listener com defeito não derruba os demais.
    }
  }
}

function connect() {
  if (!currentToken || socket) {
    return;
  }
  closedByUser = false;
  const url = `${API_ORIGIN.replace(/^http/i, 'ws')}/api/v1/ws`;
  // O React Native aceita headers no terceiro argumento, mas a tipagem pública
  // do WebSocket declara apenas dois. O cast mantém o comportamento nativo.
  const Socket = WebSocket as unknown as new (
    target: string,
    protocols?: string | string[],
    options?: { headers?: Record<string, string> },
  ) => WebSocket;
  const ws = new Socket(url, undefined, {
    headers: { Authorization: `Bearer ${currentToken}` },
  });
  socket = ws;

  ws.onopen = () => {
    for (const lobbyId of lobbies) {
      ws.send(JSON.stringify({ type: 'subscribe', lobby_id: lobbyId }));
    }
    if (heartbeat) {
      clearInterval(heartbeat);
    }
    heartbeat = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, 25_000);
  };

  ws.onmessage = (message) => {
    try {
      const event = JSON.parse(String(message.data)) as RealtimeEvent;
      if (event.type === 'ping') {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'pong' }));
        }
        return;
      }
      dispatch(event);
    } catch {
      // Evento inválido é ignorado; o histórico continua na API.
    }
  };

  ws.onclose = () => {
    if (heartbeat) {
      clearInterval(heartbeat);
      heartbeat = null;
    }
    socket = null;
    if (!closedByUser && currentToken) {
      reconnect = setTimeout(connect, 3_000);
    }
  };

  ws.onerror = () => {
    ws.close();
  };
}

export function subscribeRealtime(listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function subscribeLobby(lobbyId: string): () => void {
  lobbies.add(lobbyId);
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: 'subscribe', lobby_id: lobbyId }));
  }
  return () => {
    lobbies.delete(lobbyId);
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: 'unsubscribe', lobby_id: lobbyId }));
    }
  };
}

export function startRealtime(token: string): void {
  if (currentToken === token && socket) {
    return;
  }
  // Preserva as assinaturas de lobby quando só o token foi renovado.
  const previous = new Set(lobbies);
  stopRealtime();
  for (const lobbyId of previous) {
    lobbies.add(lobbyId);
  }
  currentToken = token;
  connect();
}

export function stopRealtime(): void {
  closedByUser = true;
  currentToken = null;
  lobbies.clear();
  if (reconnect) {
    clearTimeout(reconnect);
    reconnect = null;
  }
  if (heartbeat) {
    clearInterval(heartbeat);
    heartbeat = null;
  }
  if (socket) {
    const active = socket;
    socket = null;
    active.close();
  }
}
